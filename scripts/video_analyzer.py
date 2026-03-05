#!/usr/bin/env python3
"""
视频理解分析器 - 通过 Gemini 2.5 Pro API 理解视频内容并生成结构化剧本

支持格式: MP4, MOV, AVI, WEBM
API: yunwu.ai 代理的 Gemini 2.5 Pro 视频理解接口

v3.2.0:
- 视频文件 → base64 → Gemini API → 结构化分析 → ParsedScript 兼容 Dict
- 输出与 parse_script() 同构，可直接传入 extract_characters / analyze_scenes
- 4 级 JSON 容错解析
- 使用标准库 urllib.request，不增加额外依赖
"""

import re
import json
import base64
import urllib.request
import urllib.error
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class VideoInfo:
    """视频文件信息"""
    file_path: str
    file_size_bytes: int
    mime_type: str
    base64_data: str = ""


@dataclass
class GeminiConfig:
    """Gemini API 配置"""
    api_key: str
    base_url: str = "https://yunwu.ai"
    model: str = "gemini-2.5-pro"
    timeout_seconds: int = 120


class VideoAnalyzer:
    """
    视频理解分析器

    通过 Gemini 2.5 Pro API 分析视频内容，输出与 parse_script() 同构的
    ParsedScript Dict，可直接传入下游步骤（角色提取→场景分析→分镜→提示词）。
    """

    # 支持的视频格式 → MIME 类型
    SUPPORTED_FORMATS: Dict[str, str] = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".webm": "video/webm",
    }

    # 文件大小限制（MB）
    MAX_FILE_SIZE_MB = 50
    WARN_FILE_SIZE_MB = 20

    # 默认 API 配置
    DEFAULT_BASE_URL = "https://yunwu.ai"
    DEFAULT_MODEL = "gemini-2.5-pro"

    # Gemini 视频分析提示词
    ANALYSIS_PROMPT = """你是一个专业的影视剧本分析师。请仔细观看这个视频，然后按照以下要求输出结构化的剧本拆解。

## 分析要求

对视频中的每一个明显场景（场景切换标志：地点变化、时间跳跃、明显转场），提取以下信息：

### 场景信息
- 场景编号（从1开始）
- 内景/外景（INT./EXT.）
- 具体地点名称（如：咖啡厅、街道、办公室）
- 时间段（DAY/NIGHT/DAWN/DUSK/MORNING/EVENING）

### 角色信息
- 出场角色名称（如果有字幕/对白可获取名称；否则用描述性名称如"红衣女子"、"西装男"）
- 每个角色的详细外貌：年龄段、性别、体型、发型、发色、肤色、服装、标志性配饰
- 角色在该场景中的动作和表情

### 对白
- 逐句转录所有可听清的对白
- 标注说话者

### 视觉分析
- 主要动作描述（按时间顺序）
- 镜头运动方式（推/拉/摇/移/跟/固定/手持 等）
- 景别变化（特写/近景/中景/远景/全景）
- 转场方式（切/溶/淡入淡出）

### 氛围与光线
- 情绪氛围（紧张/温馨/浪漫/悲伤/欢乐/神秘 等）
- 光线类型（自然光/人造光/混合光）
- 光线方向（正面/侧面/逆光/顶光）
- 色温倾向（暖/冷/中性）
- 整体色调

## 输出格式

请严格按照以下 JSON 格式输出，不要添加任何 JSON 之外的文字：

```json
{
  "title": "视频的描述性标题",
  "scenes": [
    {
      "number": 1,
      "heading": "INT. 咖啡厅 - DAY",
      "location": "咖啡厅",
      "time_of_day": "DAY",
      "int_ext": "INT.",
      "characters": ["角色A", "角色B"],
      "elements": [
        {"type": "scene_heading", "content": "INT. 咖啡厅 - DAY"},
        {"type": "action", "content": "角色A走进咖啡厅，环顾四周。镜头：tracking，景别：medium shot"},
        {"type": "character", "content": "角色A"},
        {"type": "dialogue", "content": "你好，好久不见"},
        {"type": "action", "content": "角色B微笑着站起来。镜头：static，景别：medium close-up"}
      ],
      "mood": "温馨",
      "lighting": {"type": "natural", "direction": "side", "color_temperature": "warm"}
    }
  ],
  "all_characters": ["角色A", "角色B"],
  "all_locations": ["咖啡厅"],
  "character_descriptions": {
    "角色A": "青年女性，约25岁，长黑色直发，苗条身材，穿白色衬衫和黑色长裤",
    "角色B": "中年男性，约35岁，短黑发，中等身材，穿深蓝色休闲西装"
  },
  "video_metadata": {
    "estimated_duration_seconds": 30,
    "dominant_style": "cinematic",
    "color_palette": ["warm earth tones"],
    "overall_mood": "温馨"
  }
}
```

## 重要规则
1. elements 中的 type 只能是：scene_heading, action, character, dialogue, parenthetical, transition
2. 每段对白前必须有对应的 character 元素
3. 如果无法确定角色名称，使用外貌特征命名（如"长发女子"、"灰发老人"）
4. action 元素中尽量包含镜头运动和景别信息
5. 所有描述使用中文，技术术语保留英文
6. 确保 all_characters 和 all_locations 汇总了所有场景中的角色和地点"""

    def __init__(self):
        self._reset()

    def _reset(self):
        """重置内部状态，防止跨调用污染"""
        self.warnings: List[str] = []

    # ------------------------------------------------------------------
    # 公共入口
    # ------------------------------------------------------------------

    def analyze_video(
        self,
        file_path: str,
        api_key: str,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        additional_context: str = "",
    ) -> Dict:
        """
        分析视频文件，返回完整结果（含 ParsedScript + 元数据）

        Args:
            file_path: 视频文件路径
            api_key: yunwu.ai Gemini API Key
            base_url: API 基础 URL（默认 https://yunwu.ai）
            model: 模型名称（默认 gemini-2.5-pro）
            additional_context: 额外分析上下文（如"重点关注角色服装变化"）

        Returns:
            {
                "parsed_script": Dict,           # ParsedScript 兼容
                "character_hints": Dict[str, str],# 角色外貌描述
                "video_metadata": Dict,           # 视频元信息
                "analysis_quality": float,        # 分析质量 0-1
                "warnings": List[str],            # 警告信息
            }
        """
        self._reset()

        # 1. 验证视频
        video_info = self._validate_video(file_path)

        # 2. 转 base64
        video_info.base64_data = self._encode_video_base64(video_info)

        # 3. 构建 API 配置
        config = self._build_api_config(api_key, base_url, model)

        # 4. 构建分析提示词
        prompt = self._build_analysis_prompt(additional_context)

        # 5. 调用 Gemini API
        raw_response = self._call_gemini_api(video_info, config, prompt)

        # 6. 解析响应
        analysis = self._parse_gemini_response(raw_response)

        # 7. 映射为 ParsedScript 格式
        parsed_script = self._map_to_parsed_script(analysis)

        # 8. 提取角色外貌提示
        character_hints = analysis.get("character_descriptions", {})

        # 9. 评估质量
        quality = self._assess_quality(parsed_script)

        return {
            "parsed_script": parsed_script,
            "character_hints": character_hints,
            "video_metadata": analysis.get("video_metadata", {}),
            "analysis_quality": quality,
            "warnings": list(self.warnings),
        }

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _validate_video(self, file_path: str) -> VideoInfo:
        """验证视频文件格式和大小"""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"视频文件不存在: {file_path}")

        suffix = path.suffix.lower()
        if suffix not in self.SUPPORTED_FORMATS:
            supported = ", ".join(self.SUPPORTED_FORMATS.keys())
            raise ValueError(
                f"不支持的视频格式 '{suffix}'，支持: {supported}"
            )

        file_size = path.stat().st_size
        if file_size == 0:
            raise ValueError("视频文件为空")

        size_mb = file_size / (1024 * 1024)
        if size_mb > self.MAX_FILE_SIZE_MB:
            raise ValueError(
                f"视频文件超过 {self.MAX_FILE_SIZE_MB}MB 上限"
                f"（当前 {size_mb:.1f}MB），建议压缩后再试"
            )

        if size_mb > self.WARN_FILE_SIZE_MB:
            self.warnings.append(
                f"视频文件较大（{size_mb:.1f}MB），处理可能较慢"
            )

        return VideoInfo(
            file_path=str(path),
            file_size_bytes=file_size,
            mime_type=self.SUPPORTED_FORMATS[suffix],
        )

    def _encode_video_base64(self, video_info: VideoInfo) -> str:
        """将视频文件编码为 base64 字符串"""
        with open(video_info.file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")

    def _build_api_config(
        self,
        api_key: str,
        base_url: Optional[str],
        model: Optional[str],
    ) -> GeminiConfig:
        """构建 API 配置，参数 > 默认值"""
        if not api_key or not api_key.strip():
            raise ValueError(
                "API Key 不能为空，请提供 yunwu.ai Gemini 代理的 API Key"
            )

        return GeminiConfig(
            api_key=api_key.strip(),
            base_url=(base_url or self.DEFAULT_BASE_URL).rstrip("/"),
            model=model or self.DEFAULT_MODEL,
        )

    def _build_analysis_prompt(self, additional_context: str = "") -> str:
        """组合分析提示词"""
        prompt = self.ANALYSIS_PROMPT
        if additional_context.strip():
            prompt += f"\n\n## 额外要求\n{additional_context.strip()}"
        return prompt

    def _call_gemini_api(
        self, video_info: VideoInfo, config: GeminiConfig, prompt: str
    ) -> str:
        """调用 Gemini API，返回原始响应文本"""
        url = (
            f"{config.base_url}/v1beta/models/{config.model}"
            f":generateContent?key={config.api_key}"
        )

        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": video_info.mime_type,
                                "data": video_info.base64_data,
                            }
                        },
                        {"text": prompt},
                    ],
                }
            ]
        }

        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                req, timeout=config.timeout_seconds
            ) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass
            raise RuntimeError(
                f"API 返回错误（{e.code}）: {error_body}"
            ) from e
        except urllib.error.URLError as e:
            raise ConnectionError(
                f"无法连接到 API 服务器 {config.base_url}，"
                f"请检查网络连接: {e.reason}"
            ) from e
        except TimeoutError as e:
            raise TimeoutError(
                f"API 请求超时（{config.timeout_seconds}秒），"
                "请稍后重试或使用更短的视频"
            ) from e

        # 从 Gemini 响应中提取文本
        try:
            text = resp_data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(
                f"API 响应格式异常，无法提取分析结果: "
                f"{json.dumps(resp_data, ensure_ascii=False)[:500]}"
            ) from e

        return text

    def _parse_gemini_response(self, raw_text: str) -> Dict:
        """
        解析 Gemini 返回的文本为 JSON，4 级容错：
        1. 直接 json.loads
        2. 提取 ```json ``` 代码块
        3. 找最外层 {...}
        4. 降级为纯文本模式
        """
        # Level 1: 直接解析
        try:
            return json.loads(raw_text)
        except (json.JSONDecodeError, ValueError):
            pass

        # Level 2: 提取代码块
        code_block = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL
        )
        if code_block:
            try:
                return json.loads(code_block.group(1))
            except (json.JSONDecodeError, ValueError):
                pass

        # Level 3: 找最外层 {...}
        try:
            start = raw_text.index("{")
            end = raw_text.rindex("}") + 1
            return json.loads(raw_text[start:end])
        except (ValueError, json.JSONDecodeError):
            pass

        # Level 4: 降级为纯文本
        self.warnings.append(
            "Gemini 返回的分析结果无法解析为结构化 JSON，已降级为纯文本模式"
        )
        return {
            "title": "视频分析（纯文本降级）",
            "scenes": [
                {
                    "number": 1,
                    "heading": "SCENE 1",
                    "location": "UNKNOWN",
                    "time_of_day": "DAY",
                    "int_ext": "INT.",
                    "characters": [],
                    "elements": [
                        {
                            "type": "action",
                            "content": raw_text[:2000],
                            "line_number": 0,
                            "metadata": {},
                        }
                    ],
                }
            ],
            "all_characters": [],
            "all_locations": [],
            "character_descriptions": {},
            "video_metadata": {},
        }

    def _map_to_parsed_script(self, analysis: Dict) -> Dict:
        """
        将 Gemini 分析结果映射为 ParsedScript 兼容 Dict

        输出结构与 parse_script.py 的 parse_script() 返回值完全一致，
        可直接传入 extract_characters() / analyze_scenes() / generate_storyboard()。
        """
        scenes = []
        for scene_data in analysis.get("scenes", []):
            # 规范化 elements
            elements = []
            for elem in scene_data.get("elements", []):
                elements.append(
                    {
                        "type": elem.get("type", "action"),
                        "content": elem.get("content", ""),
                        "line_number": elem.get("line_number", 0),
                        "metadata": elem.get("metadata", {}),
                    }
                )

            # 估算时长：每个 action 约 3 秒，每段 dialogue 约 4 秒
            action_count = sum(
                1 for e in elements if e["type"] == "action"
            )
            dialogue_count = sum(
                1 for e in elements if e["type"] == "dialogue"
            )
            estimated_duration = action_count * 3.0 + dialogue_count * 4.0

            scene = {
                "number": scene_data.get("number", len(scenes) + 1),
                "heading": scene_data.get("heading", "SCENE"),
                "location": scene_data.get("location", "UNKNOWN"),
                "time_of_day": scene_data.get("time_of_day", "DAY"),
                "int_ext": scene_data.get("int_ext", "INT."),
                "characters": scene_data.get("characters", []),
                "estimated_duration": estimated_duration,
                "element_count": len(elements),
                "elements": elements,
            }
            scenes.append(scene)

        all_characters = analysis.get("all_characters", [])
        all_locations = analysis.get("all_locations", [])

        total_duration = sum(
            s.get("estimated_duration", 0) for s in scenes
        )

        return {
            "title": analysis.get("title", "视频分析"),
            "metadata": {
                "scene_count": len(scenes),
                "character_count": len(all_characters),
                "location_count": len(all_locations),
                "source": "video_analysis",
            },
            "total_duration_seconds": total_duration,
            "total_duration_formatted": (
                f"{int(total_duration // 60)}"
                f":{int(total_duration % 60):02d}"
            ),
            "all_characters": sorted(set(all_characters)),
            "all_locations": sorted(set(all_locations)),
            "scenes": scenes,
        }

    def _assess_quality(self, parsed: Dict) -> float:
        """
        评估分析质量 0-1

        评分维度：场景、角色、地点、元素、对白、氛围
        """
        score = 0.0
        scenes = parsed.get("scenes", [])

        # 有场景 (+0.25)
        if scenes:
            score += 0.25

        # 有角色 (+0.15)
        if parsed.get("all_characters"):
            score += 0.15

        # 有地点 (+0.1)
        if parsed.get("all_locations"):
            score += 0.1

        # 场景有 elements (+0.2)
        if scenes and all(
            len(s.get("elements", [])) > 0 for s in scenes
        ):
            score += 0.2

        # 有对白 (+0.15)
        has_dialogue = any(
            any(
                e.get("type") == "dialogue"
                for e in s.get("elements", [])
            )
            for s in scenes
        )
        if has_dialogue:
            score += 0.15

        # 多个场景 (+0.15)
        if len(scenes) >= 2:
            score += 0.15

        return min(1.0, score)


# ======================================================================
# 模块级便捷函数
# ======================================================================


def analyze_video(
    file_path: str,
    api_key: str,
    base_url: Optional[str] = None,
) -> Dict:
    """
    分析视频文件的便捷函数

    Args:
        file_path: 视频文件路径
        api_key: yunwu.ai Gemini API Key

    Returns:
        ParsedScript 兼容的字典，可直接传入 extract_characters / analyze_scenes
    """
    analyzer = VideoAnalyzer()
    result = analyzer.analyze_video(file_path, api_key, base_url=base_url)
    return result["parsed_script"]


def analyze_video_full(
    file_path: str,
    api_key: str,
    base_url: Optional[str] = None,
) -> Dict:
    """
    视频分析完整结果（含角色提示、视频元数据、质量评分）

    Args:
        file_path: 视频文件路径
        api_key: yunwu.ai Gemini API Key

    Returns:
        完整分析结果字典
    """
    analyzer = VideoAnalyzer()
    return analyzer.analyze_video(file_path, api_key, base_url=base_url)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python video_analyzer.py <video_file> <api_key> [base_url]")
        print("Supported formats: .mp4, .mov, .avi, .webm")
        print("API key: yunwu.ai Gemini proxy key")
        sys.exit(1)

    video_file = sys.argv[1]
    api_key_arg = sys.argv[2]
    base_url_arg = sys.argv[3] if len(sys.argv) > 3 else None

    result = analyze_video_full(video_file, api_key_arg, base_url=base_url_arg)

    print(f"\n分析质量: {result['analysis_quality']:.2f}")
    if result["warnings"]:
        print(f"警告: {', '.join(result['warnings'])}")
    print(f"\n角色提示:")
    for name, desc in result["character_hints"].items():
        print(f"  {name}: {desc}")
    print(f"\nParsedScript JSON:")
    print(json.dumps(result["parsed_script"], ensure_ascii=False, indent=2))
