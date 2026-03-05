#!/usr/bin/env python3
"""
剧本解析器 - 支持多格式剧本文件解析
支持格式: TXT, Markdown, DOCX, PDF, Final Draft (.fdx)

v2.0 改进:
- 状态机解析器替代纯正则，解决中文对白/动作误判为角色名
- Scene.to_dict() 输出完整 elements，修复步骤间数据契约断裂
- 编码回退链: utf-8 → utf-8-sig → gb18030
- FDX 解析异常包装为可读错误
- 中文场景标题支持 内景/外景 识别
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class ElementType(Enum):
    """剧本元素类型"""
    SCENE_HEADING = "scene_heading"
    ACTION = "action"
    CHARACTER = "character"
    DIALOGUE = "dialogue"
    PARENTHETICAL = "parenthetical"
    TRANSITION = "transition"
    NOTE = "note"


class ParserState(Enum):
    """解析器状态"""
    IDLE = "idle"                    # 等待场景开始
    SCENE = "scene"                  # 场景内，等待任意元素
    EXPECT_DIALOGUE = "expect_dialogue"  # 刚识别角色名，下一行应为对白


@dataclass
class ScriptElement:
    """剧本元素"""
    type: ElementType
    content: str
    line_number: int
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "content": self.content,
            "line_number": self.line_number,
            "metadata": self.metadata,
        }


@dataclass
class Scene:
    """场景"""
    number: int
    heading: str
    location: str
    time_of_day: str
    int_ext: str  # INT. / EXT.
    elements: List[ScriptElement] = field(default_factory=list)
    characters: List[str] = field(default_factory=list)
    estimated_duration: float = 0.0

    def to_dict(self) -> Dict:
        """输出完整 elements，供下游步骤使用"""
        return {
            "number": self.number,
            "heading": self.heading,
            "location": self.location,
            "time_of_day": self.time_of_day,
            "int_ext": self.int_ext,
            "characters": self.characters,
            "estimated_duration": self.estimated_duration,
            "element_count": len(self.elements),
            "elements": [e.to_dict() for e in self.elements],
        }


@dataclass
class ParsedScript:
    """解析后的剧本"""
    title: str
    scenes: List[Scene] = field(default_factory=list)
    all_characters: List[str] = field(default_factory=list)
    all_locations: List[str] = field(default_factory=list)
    total_duration: float = 0.0
    metadata: Dict = field(default_factory=dict)


class ScriptParser:
    """剧本解析器 — 状态机驱动"""

    # 场景标题正则 - 匹配 INT./EXT. 开头的行
    SCENE_HEADING_PATTERN = re.compile(
        r'^(INT\.|EXT\.|INT/EXT\.|I/E\.)\s*(.+?)(?:\s*[-–—]\s*(.+))?$',
        re.IGNORECASE,
    )

    # 中文场景标题 — 支持 内景/外景 识别
    CN_SCENE_HEADING_PATTERN = re.compile(
        r'^(?:场景|第)\s*(\d+)\s*(?:场|幕)?[：:\s]*'
        r'(?:(内景|外景|室内|室外|INT|EXT)[.．、\s]*)?'
        r'(.+)?$'
    )

    # 中文角色行特征：
    #   "角色名：" / "角色名:" / "【角色名】"
    CN_CHARACTER_LINE = re.compile(
        r'^(?:【([\u4e00-\u9fa5]{1,6})】|'
        r'([\u4e00-\u9fa5]{1,6})\s*[：:])\s*$'
    )

    # 独立角色名行：2-6个中文字符，无标点无动词，单独成行
    CN_STANDALONE_CHARACTER = re.compile(
        r'^([\u4e00-\u9fa5]{2,6})$'
    )

    # 中文动作/描述排除词 — 如果行包含这些，不是角色名
    CN_ACTION_INDICATORS = re.compile(
        r'[，。！？、；""''…—\-\d]|'
        r'[的了着过在从向把被让给对跟比]|'
        r'[走跑坐站看说笑哭打开关拿放拉推转]'
    )

    # 英文角色名 - 全大写
    EN_CHARACTER_PATTERN = re.compile(r'^([A-Z][A-Z\s]{1,25})(?:\s*\(.*\))?$')

    # 括号动作指示
    PARENTHETICAL_PATTERN = re.compile(r'^\s*[\(（](.+)[\)）]\s*$')

    # 转场正则
    TRANSITION_PATTERN = re.compile(
        r'^(FADE IN:|FADE OUT\.|CUT TO:|DISSOLVE TO:|SMASH CUT:|MATCH CUT:)',
        re.IGNORECASE,
    )

    # 中文内景/外景映射
    CN_INT_EXT_MAP = {
        "内景": "INT.", "室内": "INT.", "INT": "INT.",
        "外景": "EXT.", "室外": "EXT.", "EXT": "EXT.",
    }

    def __init__(self):
        self._reset()

    def _reset(self):
        """重置解析器状态"""
        self.scenes: List[Scene] = []
        self.current_scene: Optional[Scene] = None
        self.all_characters: set = set()
        self.all_locations: set = set()
        self.scene_count = 0
        self.state = ParserState.IDLE
        self._known_characters: set = set()  # 已确认的角色名缓存

    def parse_file(self, file_path: str) -> ParsedScript:
        """解析剧本文件"""
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == '.fdx':
            return self._parse_final_draft(path)
        elif suffix == '.docx':
            return self._parse_docx(path)
        elif suffix == '.pdf':
            return self._parse_pdf(path)
        else:
            return self._parse_text_file(path)

    def parse_text(self, text: str, title: str = "Untitled") -> ParsedScript:
        """解析剧本文本"""
        lines = text.split('\n')
        self._reset()

        for i, line in enumerate(lines, 1):
            self._parse_line(line.strip(), i)

        if self.current_scene:
            self._finalize_scene()

        total_duration = sum(s.estimated_duration for s in self.scenes)

        return ParsedScript(
            title=title,
            scenes=self.scenes,
            all_characters=sorted(list(self.all_characters)),
            all_locations=sorted(list(self.all_locations)),
            total_duration=total_duration,
            metadata={
                "scene_count": len(self.scenes),
                "character_count": len(self.all_characters),
                "location_count": len(self.all_locations),
            },
        )

    # ── 状态机核心 ──────────────────────────────────────────

    def _parse_line(self, line: str, line_number: int):
        """状态机驱动的行解析"""
        if not line:
            # 空行：如果在 EXPECT_DIALOGUE 状态，回退到 SCENE
            if self.state == ParserState.EXPECT_DIALOGUE:
                self.state = ParserState.SCENE
            return

        # ── 场景标题检测（任何状态下都优先） ──
        if self._try_scene_heading(line, line_number):
            return

        # 如果还没有场景，创建默认场景
        if not self.current_scene:
            self.scene_count += 1
            self.current_scene = Scene(
                number=self.scene_count,
                heading="SCENE 1",
                location="UNKNOWN",
                time_of_day="DAY",
                int_ext="INT.",
            )
            self.state = ParserState.SCENE

        # ── EXPECT_DIALOGUE 状态：上一行是角色名 ──
        if self.state == ParserState.EXPECT_DIALOGUE:
            # 括号动作指示（对白前的表演指示）
            paren_match = self.PARENTHETICAL_PATTERN.match(line)
            if paren_match:
                self.current_scene.elements.append(ScriptElement(
                    type=ElementType.PARENTHETICAL,
                    content=paren_match.group(1),
                    line_number=line_number,
                ))
                return  # 保持 EXPECT_DIALOGUE 状态

            # 否则这一行就是对白
            self.current_scene.elements.append(ScriptElement(
                type=ElementType.DIALOGUE,
                content=line,
                line_number=line_number,
            ))
            self.state = ParserState.SCENE
            return

        # ── SCENE 状态：正常解析 ──

        # 转场
        if self.TRANSITION_PATTERN.match(line):
            self.current_scene.elements.append(ScriptElement(
                type=ElementType.TRANSITION,
                content=line,
                line_number=line_number,
            ))
            return

        # 括号动作指示
        paren_match = self.PARENTHETICAL_PATTERN.match(line)
        if paren_match:
            self.current_scene.elements.append(ScriptElement(
                type=ElementType.PARENTHETICAL,
                content=paren_match.group(1),
                line_number=line_number,
            ))
            return

        # 角色名检测
        char_name = self._detect_character(line)
        if char_name:
            self.current_scene.elements.append(ScriptElement(
                type=ElementType.CHARACTER,
                content=char_name,
                line_number=line_number,
            ))
            self.all_characters.add(char_name)
            self._known_characters.add(char_name)
            if char_name not in self.current_scene.characters:
                self.current_scene.characters.append(char_name)
            self.state = ParserState.EXPECT_DIALOGUE
            return

        # 默认：动作描述
        self.current_scene.elements.append(ScriptElement(
            type=ElementType.ACTION,
            content=line,
            line_number=line_number,
        ))

    def _detect_character(self, line: str) -> Optional[str]:
        """
        角色名检测 — 多规则收敛，减少误判

        优先级:
        1. 中文带标记格式: 【角色名】 / 角色名：
        2. 英文全大写格式: JOHN SMITH
        3. 已知角色名复现（独立成行）
        4. 中文独立短行（2-6字，无动词/标点）— 仅作为候选
        """
        # 规则1: 中文带标记格式（最可靠）
        m = self.CN_CHARACTER_LINE.match(line)
        if m:
            name = m.group(1) or m.group(2)
            return name.strip()

        # 规则2: 英文全大写
        m = self.EN_CHARACTER_PATTERN.match(line)
        if m and len(line) < 30:
            return m.group(1).strip()

        # 规则3: 已知角色名复现
        m = self.CN_STANDALONE_CHARACTER.match(line)
        if m and m.group(1) in self._known_characters:
            return m.group(1)

        # 规则4: 中文独立短行（严格过滤）
        if m and not self.CN_ACTION_INDICATORS.search(line):
            candidate = m.group(1)
            # 额外过滤：不能是常见非角色词
            if len(candidate) >= 2 and len(candidate) <= 4:
                return candidate

        return None

    def _try_scene_heading(self, line: str, line_number: int) -> bool:
        """尝试匹配场景标题，成功则切换场景并返回 True"""
        # 英文场景标题
        scene_match = self.SCENE_HEADING_PATTERN.match(line)
        if scene_match:
            self._start_new_scene(
                heading=line,
                int_ext=scene_match.group(1).upper(),
                location=scene_match.group(2).strip(),
                time_of_day=(scene_match.group(3).strip()
                             if scene_match.group(3) else "DAY"),
            )
            return True

        # 中文场景标题
        cn_match = self.CN_SCENE_HEADING_PATTERN.match(line)
        if cn_match:
            cn_int_ext = cn_match.group(2) or ""
            int_ext = self.CN_INT_EXT_MAP.get(cn_int_ext, "INT.")
            location = cn_match.group(3) or f"场景{cn_match.group(1)}"
            self._start_new_scene(
                heading=line,
                int_ext=int_ext,
                location=location.strip(),
                time_of_day="DAY",
            )
            return True

        return False

    def _start_new_scene(self, heading: str, int_ext: str,
                         location: str, time_of_day: str):
        """完成上一个场景并开始新场景"""
        if self.current_scene:
            self._finalize_scene()
        self.scene_count += 1
        self.current_scene = Scene(
            number=self.scene_count,
            heading=heading,
            location=location,
            time_of_day=time_of_day,
            int_ext=int_ext,
        )
        self.all_locations.add(location)
        self.state = ParserState.SCENE

    def _finalize_scene(self):
        """完成当前场景的处理"""
        if self.current_scene:
            dialogue_count = sum(
                1 for e in self.current_scene.elements
                if e.type == ElementType.DIALOGUE
            )
            action_count = sum(
                1 for e in self.current_scene.elements
                if e.type == ElementType.ACTION
            )
            self.current_scene.estimated_duration = (
                dialogue_count * 3 + action_count * 5
            )
            self.scenes.append(self.current_scene)

    # ── 文件格式解析 ──────────────────────────────────────

    @staticmethod
    def _read_text_with_fallback(path: Path) -> str:
        """编码回退链: utf-8 → utf-8-sig → gb18030"""
        for encoding in ("utf-8", "utf-8-sig", "gb18030"):
            try:
                return path.read_text(encoding=encoding)
            except (UnicodeDecodeError, UnicodeError):
                continue
        # 最后兜底：忽略错误字符
        return path.read_text(encoding="utf-8", errors="replace")

    def _parse_text_file(self, path: Path) -> ParsedScript:
        """解析纯文本文件"""
        text = self._read_text_with_fallback(path)
        return self.parse_text(text, title=path.stem)

    def _parse_docx(self, path: Path) -> ParsedScript:
        """解析 DOCX 文件"""
        try:
            from docx import Document
            doc = Document(str(path))
            text = '\n'.join(para.text for para in doc.paragraphs)
            return self.parse_text(text, title=path.stem)
        except ImportError:
            raise ImportError("请安装 python-docx: pip install python-docx")

    def _parse_pdf(self, path: Path) -> ParsedScript:
        """解析 PDF 文件"""
        try:
            import pdfplumber
            text_parts = []
            with pdfplumber.open(str(path)) as pdf:
                for page in pdf.pages:
                    text_parts.append(page.extract_text() or '')
            text = '\n'.join(text_parts)
            return self.parse_text(text, title=path.stem)
        except ImportError:
            raise ImportError("请安装 pdfplumber: pip install pdfplumber")

    def _parse_final_draft(self, path: Path) -> ParsedScript:
        """解析 Final Draft (.fdx) 文件，带异常包装"""
        import xml.etree.ElementTree as ET

        try:
            tree = ET.parse(str(path))
        except ET.ParseError as e:
            raise ValueError(
                f"FDX 文件解析失败（文件可能损坏或格式异常）: {path.name}\n"
                f"XML 错误详情: {e}"
            )

        root = tree.getroot()
        self._reset()
        title = path.stem

        title_page = root.find('.//TitlePage')
        if title_page is not None:
            content = title_page.find('.//Content')
            if content is not None and content.text:
                title = content.text.strip()

        # FDX 有明确的元素类型标注，直接映射
        type_map = {
            'Dialogue': ElementType.DIALOGUE,
            'Parenthetical': ElementType.PARENTHETICAL,
            'Action': ElementType.ACTION,
            'Transition': ElementType.TRANSITION,
        }

        for para in root.findall('.//Paragraph'):
            para_type = para.get('Type', '')
            # 合并多个 Text 子元素
            texts = [t.text for t in para.findall('Text')
                     if t is not None and t.text]
            text = ' '.join(texts)
            if not text:
                continue

            if para_type == 'Scene Heading':
                self._try_scene_heading(text, 0)
            elif para_type == 'Character':
                if not self.current_scene:
                    self._start_new_scene(
                        heading="SCENE 1", int_ext="INT.",
                        location="UNKNOWN", time_of_day="DAY",
                    )
                char_name = text.strip()
                self.current_scene.elements.append(ScriptElement(
                    type=ElementType.CHARACTER,
                    content=char_name,
                    line_number=0,
                ))
                self.all_characters.add(char_name)
                self._known_characters.add(char_name)
                if char_name not in self.current_scene.characters:
                    self.current_scene.characters.append(char_name)
                self.state = ParserState.EXPECT_DIALOGUE
            elif para_type in type_map:
                if self.current_scene:
                    self.current_scene.elements.append(ScriptElement(
                        type=type_map[para_type],
                        content=text,
                        line_number=0,
                    ))
                    if para_type == 'Dialogue':
                        self.state = ParserState.SCENE

        if self.current_scene:
            self._finalize_scene()

        total_duration = sum(s.estimated_duration for s in self.scenes)

        return ParsedScript(
            title=title,
            scenes=self.scenes,
            all_characters=sorted(list(self.all_characters)),
            all_locations=sorted(list(self.all_locations)),
            total_duration=total_duration,
            metadata={
                "scene_count": len(self.scenes),
                "character_count": len(self.all_characters),
                "location_count": len(self.all_locations),
                "format": "Final Draft",
            },
        )


def parse_script(file_path: str) -> Dict:
    """
    解析剧本文件的便捷函数

    Args:
        file_path: 剧本文件路径

    Returns:
        解析结果字典，scenes 中包含完整 elements
    """
    parser = ScriptParser()
    result = parser.parse_file(file_path)

    return {
        "title": result.title,
        "metadata": result.metadata,
        "total_duration_seconds": result.total_duration,
        "total_duration_formatted": (
            f"{int(result.total_duration // 60)}"
            f":{int(result.total_duration % 60):02d}"
        ),
        "all_characters": result.all_characters,
        "all_locations": result.all_locations,
        "scenes": [scene.to_dict() for scene in result.scenes],
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python parse_script.py <script_file>")
        print("Supported formats: .txt, .md, .docx, .pdf, .fdx")
        sys.exit(1)

    result = parse_script(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
