#!/usr/bin/env python3
"""
分镜提示词生成器 - 根据剧本自动生成逐镜头的AI视频提示词

v2.0 改进:
- 元素驱动: 从 elements 中的 action/dialogue/character 切镜
- 实际使用 ACTION_TO_SHOT_SIZE 和 MOOD_TO_MOVEMENT 映射
- 入口自动 reset，消除跨调用状态污染
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class ShotSize(Enum):
    """景别"""
    ECU = "extreme close-up"
    CU = "close-up"
    MCU = "medium close-up"
    MS = "medium shot"
    MLS = "medium long shot"
    LS = "long shot"
    ELS = "extreme long shot"
    OTS = "over-the-shoulder"
    POV = "point of view"
    TWO_SHOT = "two shot"
    GROUP = "group shot"


class CameraMovement(Enum):
    """运镜方式"""
    STATIC = "static"
    PAN = "pan"
    TILT = "tilt"
    PUSH = "push in"
    PULL = "pull out"
    DOLLY = "dolly"
    TRACK = "tracking"
    CRANE = "crane"
    HANDHELD = "handheld"
    STEADICAM = "steadicam"
    ZOOM = "zoom"
    WHIP_PAN = "whip pan"
    ORBIT = "orbit"


class Transition(Enum):
    """转场方式"""
    CUT = "cut"
    FADE = "fade"
    DISSOLVE = "dissolve"
    WIPE = "wipe"
    MATCH_CUT = "match cut"
    JUMP_CUT = "jump cut"
    L_CUT = "L-cut"
    J_CUT = "J-cut"
    SMASH_CUT = "smash cut"


@dataclass
class Shot:
    """单个镜头"""
    shot_id: str
    scene_number: int
    shot_number: int
    shot_size: str
    camera_movement: str
    subject: str
    action: str
    dialogue: str = ""
    mood: str = ""
    duration: float = 3.0
    transition: str = "cut"
    composition_notes: str = ""
    lighting_notes: str = ""
    audio_notes: str = ""
    visual_prompt: str = ""


@dataclass
class Storyboard:
    """分镜脚本"""
    title: str
    shots: List[Shot] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


class StoryboardGenerator:
    """分镜生成器 — 元素驱动"""

    # 动作关键词到景别的推荐映射
    ACTION_TO_SHOT_SIZE = {
        "表情": ShotSize.CU, "眼神": ShotSize.ECU,
        "微笑": ShotSize.CU, "流泪": ShotSize.ECU, "皱眉": ShotSize.CU,
        "说": ShotSize.MCU, "对话": ShotSize.TWO_SHOT,
        "交谈": ShotSize.TWO_SHOT, "问": ShotSize.MCU, "答": ShotSize.MCU,
        "走": ShotSize.MLS, "跑": ShotSize.LS,
        "坐": ShotSize.MS, "站": ShotSize.MS, "转身": ShotSize.MS,
        "打斗": ShotSize.MLS, "拥抱": ShotSize.MS,
        "进入": ShotSize.LS, "离开": ShotSize.LS,
        "全景": ShotSize.ELS, "环境": ShotSize.ELS,
    }

    # 情绪到运镜的推荐映射
    MOOD_TO_MOVEMENT = {
        "紧张": [CameraMovement.HANDHELD, CameraMovement.PUSH],
        "平静": [CameraMovement.STATIC, CameraMovement.DOLLY],
        "追逐": [CameraMovement.TRACK, CameraMovement.HANDHELD],
        "浪漫": [CameraMovement.DOLLY, CameraMovement.ORBIT],
        "惊讶": [CameraMovement.WHIP_PAN, CameraMovement.PUSH],
        "悲伤": [CameraMovement.STATIC, CameraMovement.PULL],
        "神秘": [CameraMovement.DOLLY, CameraMovement.CRANE],
        "震撼": [CameraMovement.CRANE, CameraMovement.PUSH],
    }

    def _reset(self):
        """重置状态，防止跨调用污染"""
        self.shots: List[Shot] = []
        self.shot_counter: Dict[int, int] = {}

    def generate_from_parsed_script(
        self,
        parsed_script: Dict,
        scene_analyses: List[Dict],
        character_profiles: Dict[str, Dict],
    ) -> Storyboard:
        """从解析后的剧本生成分镜（入口自动 reset）"""
        self._reset()
        title = parsed_script.get("title", "Untitled")

        scene_analysis_map = {
            sa["scene_number"]: sa for sa in scene_analyses
        }

        for scene in parsed_script.get("scenes", []):
            scene_num = scene.get("number", 0)
            scene_analysis = scene_analysis_map.get(scene_num, {})
            self._generate_scene_shots(
                scene=scene,
                scene_analysis=scene_analysis,
                character_profiles=character_profiles,
            )

        return Storyboard(
            title=title,
            shots=self.shots,
            metadata={
                "total_shots": len(self.shots),
                "total_scenes": len(parsed_script.get("scenes", [])),
                "estimated_duration": sum(s.duration for s in self.shots),
            },
        )

    # ── 元素驱动的镜头规划 ──────────────────────────────

    def _generate_scene_shots(
        self,
        scene: Dict,
        scene_analysis: Dict,
        character_profiles: Dict[str, Dict],
    ):
        """从 elements 驱动镜头生成"""
        scene_num = scene.get("number", 0)
        if scene_num not in self.shot_counter:
            self.shot_counter[scene_num] = 0

        env = scene_analysis.get("environment", {})
        visual_base = scene_analysis.get("visual_prompt", "")
        mood_keywords = scene_analysis.get("mood_keywords", [])
        mood_str = ", ".join(mood_keywords[:2]) if mood_keywords else ""

        # 1. 场景建立镜头（始终生成）
        opening_size = (ShotSize.LS.value if env.get("int_ext") == "EXT"
                        else ShotSize.MLS.value)
        self._add_shot(
            scene_num=scene_num,
            shot_size=opening_size,
            camera_movement=CameraMovement.STATIC.value,
            subject=f"establishing shot of {env.get('location_type', 'location')}",
            action="场景建立",
            mood=mood_str,
            duration=3.0,
            visual_prompt=f"establishing shot, {visual_base}, cinematic",
        )

        # 2. 遍历 elements 生成内容镜头
        elements = scene.get("elements", [])
        current_character = None
        pending_dialogue: List[str] = []

        for elem in elements:
            etype = elem.get("type", "")
            content = elem.get("content", "")

            if etype == "character":
                # 先 flush 之前积累的对白
                if current_character and pending_dialogue:
                    self._flush_dialogue(
                        scene_num, current_character, pending_dialogue,
                        visual_base, character_profiles, mood_keywords,
                    )
                    pending_dialogue = []
                current_character = content

            elif etype == "dialogue":
                pending_dialogue.append(content)

            elif etype == "parenthetical":
                # 表演指示附加到下一个对白镜头
                if pending_dialogue:
                    pending_dialogue[-1] += f" ({content})"

            elif etype == "action":
                # 先 flush 对白
                if current_character and pending_dialogue:
                    self._flush_dialogue(
                        scene_num, current_character, pending_dialogue,
                        visual_base, character_profiles, mood_keywords,
                    )
                    pending_dialogue = []
                # 动作描述 → 独立镜头
                self._generate_action_shot(
                    scene_num, content, visual_base,
                    character_profiles, mood_keywords,
                )

            elif etype == "transition":
                # 转场标记：设置上一个镜头的 transition
                if self.shots:
                    transition_type = self._map_transition(content)
                    self.shots[-1].transition = transition_type

        # flush 最后的对白
        if current_character and pending_dialogue:
            self._flush_dialogue(
                scene_num, current_character, pending_dialogue,
                visual_base, character_profiles, mood_keywords,
            )

        # 如果场景没有 elements（旧格式兼容），用模板生成
        if not elements:
            self._generate_template_shots(
                scene_num, scene.get("characters", []),
                visual_base, character_profiles, mood_keywords,
            )

    def _flush_dialogue(
        self, scene_num: int, character: str,
        dialogues: List[str], visual_base: str,
        char_profiles: Dict[str, Dict],
        mood_keywords: List[str],
    ):
        """将积累的对白合并为一个镜头"""
        char_visual = char_profiles.get(
            character, {}
        ).get("prompt_description", character)
        combined = " ".join(dialogues)

        # 对白镜头默认中近景
        shot_size = ShotSize.MCU.value
        movement = self._infer_movement(mood_keywords)

        self._add_shot(
            scene_num=scene_num,
            shot_size=shot_size,
            camera_movement=movement,
            subject=character,
            action=f"{character} 说话",
            dialogue=combined,
            mood=", ".join(mood_keywords[:2]),
            duration=max(2.0, len(combined) * 0.15),
            visual_prompt=(
                f"medium close-up of {char_visual}, speaking, "
                f"{visual_base}, cinematic"
            ),
        )

    def _generate_action_shot(
        self, scene_num: int, action_text: str,
        visual_base: str, char_profiles: Dict[str, Dict],
        mood_keywords: List[str],
    ):
        """从动作描述生成镜头，使用 ACTION_TO_SHOT_SIZE 映射"""
        # 从动作文本推断景别
        shot_size = ShotSize.MS  # 默认中景
        for keyword, size in self.ACTION_TO_SHOT_SIZE.items():
            if keyword in action_text:
                shot_size = size
                break

        # 从动作文本提取主体（尝试匹配已知角色名）
        subject = "scene"
        for char_name in char_profiles:
            if char_name in action_text:
                subject = char_name
                break

        char_visual = ""
        if subject != "scene":
            char_visual = char_profiles.get(
                subject, {}
            ).get("prompt_description", subject)

        movement = self._infer_movement(mood_keywords)

        prompt_parts = [shot_size.value]
        if char_visual:
            prompt_parts.append(f"of {char_visual}")
        prompt_parts.append(action_text[:80])
        prompt_parts.append(visual_base)
        prompt_parts.append("cinematic")

        self._add_shot(
            scene_num=scene_num,
            shot_size=shot_size.value,
            camera_movement=movement,
            subject=subject,
            action=action_text[:100],
            mood=", ".join(mood_keywords[:2]),
            duration=max(2.0, min(5.0, len(action_text) * 0.1)),
            visual_prompt=", ".join(filter(None, prompt_parts)),
        )

    def _generate_template_shots(
        self, scene_num: int, characters: List[str],
        visual_base: str, char_profiles: Dict[str, Dict],
        mood_keywords: List[str],
    ):
        """旧格式兼容：无 elements 时用模板生成"""
        for char_name in characters[:2]:
            char_visual = char_profiles.get(
                char_name, {}
            ).get("prompt_description", char_name)
            self._add_shot(
                scene_num=scene_num,
                shot_size=ShotSize.MS.value,
                camera_movement=CameraMovement.STATIC.value,
                subject=char_name,
                action=f"{char_name} 出场",
                duration=2.0,
                visual_prompt=f"medium shot of {char_visual}, {visual_base}",
            )

        if len(characters) >= 2:
            self._add_shot(
                scene_num=scene_num,
                shot_size=ShotSize.TWO_SHOT.value,
                camera_movement=CameraMovement.STATIC.value,
                subject=f"{characters[0]} and {characters[1]}",
                action="对话",
                duration=4.0,
                visual_prompt=f"two shot, conversation, {visual_base}",
            )

    def _infer_movement(self, mood_keywords: List[str]) -> str:
        """从情绪关键词推断运镜方式"""
        for mood in mood_keywords:
            if mood in self.MOOD_TO_MOVEMENT:
                return self.MOOD_TO_MOVEMENT[mood][0].value
        return CameraMovement.STATIC.value

    @staticmethod
    def _map_transition(text: str) -> str:
        """从转场文本映射转场类型"""
        text_upper = text.upper()
        if "FADE" in text_upper:
            return Transition.FADE.value
        if "DISSOLVE" in text_upper:
            return Transition.DISSOLVE.value
        if "MATCH" in text_upper:
            return Transition.MATCH_CUT.value
        if "SMASH" in text_upper:
            return Transition.SMASH_CUT.value
        return Transition.CUT.value

    def _add_shot(
        self, scene_num: int, shot_size: str, camera_movement: str,
        subject: str, action: str, duration: float, visual_prompt: str,
        dialogue: str = "", mood: str = "", transition: str = "cut",
    ):
        """添加一个镜头"""
        self.shot_counter[scene_num] = self.shot_counter.get(scene_num, 0) + 1
        shot_num = self.shot_counter[scene_num]
        self.shots.append(Shot(
            shot_id=f"{scene_num}-{shot_num}",
            scene_number=scene_num,
            shot_number=shot_num,
            shot_size=shot_size,
            camera_movement=camera_movement,
            subject=subject,
            action=action,
            dialogue=dialogue,
            mood=mood,
            duration=duration,
            transition=transition,
            visual_prompt=visual_prompt,
        ))

    def to_dict(self, storyboard: Storyboard) -> Dict:
        """转换为字典输出"""
        return {
            "title": storyboard.title,
            "metadata": storyboard.metadata,
            "shots": [
                {
                    "shot_id": s.shot_id,
                    "scene_number": s.scene_number,
                    "shot_number": s.shot_number,
                    "shot_size": s.shot_size,
                    "camera_movement": s.camera_movement,
                    "subject": s.subject,
                    "action": s.action,
                    "dialogue": s.dialogue,
                    "mood": s.mood,
                    "duration": s.duration,
                    "transition": s.transition,
                    "composition_notes": s.composition_notes,
                    "lighting_notes": s.lighting_notes,
                    "audio_notes": s.audio_notes,
                    "visual_prompt": s.visual_prompt,
                }
                for s in storyboard.shots
            ],
        }


def generate_storyboard(
    parsed_script: Dict,
    scene_analyses: List[Dict],
    character_profiles: Dict[str, Dict],
) -> Dict:
    """
    生成分镜的便捷函数

    Args:
        parsed_script: parse_script.py 的输出（含 elements）
        scene_analyses: scene_analyzer.py 的输出
        character_profiles: character_extractor.py 的输出

    Returns:
        分镜数据字典
    """
    generator = StoryboardGenerator()
    storyboard = generator.generate_from_parsed_script(
        parsed_script, scene_analyses, character_profiles,
    )
    return generator.to_dict(storyboard)


if __name__ == "__main__":
    # 示例：带 elements 的输入
    sample_script = {
        "title": "示例短剧",
        "scenes": [
            {
                "number": 1,
                "characters": ["张伟", "李娜"],
                "elements": [
                    {"type": "action", "content": "张伟走进办公室，坐在桌前", "line_number": 5},
                    {"type": "character", "content": "张伟", "line_number": 6},
                    {"type": "dialogue", "content": "今天的会议几点开始？", "line_number": 7},
                    {"type": "character", "content": "李娜", "line_number": 8},
                    {"type": "dialogue", "content": "十点，你准备好了吗？", "line_number": 9},
                    {"type": "action", "content": "张伟皱眉看了看手表", "line_number": 10},
                ],
            },
        ],
    }

    sample_scenes = [
        {
            "scene_number": 1,
            "environment": {"location_type": "office", "int_ext": "INT"},
            "visual_prompt": "modern office interior, bright daylight",
            "mood_keywords": ["professional", "busy"],
        },
    ]

    sample_characters = {
        "张伟": {"prompt_description": "young Asian male, short black hair, wearing suit"},
        "李娜": {"prompt_description": "young Asian female, long black hair, casual dress"},
    }

    result = generate_storyboard(sample_script, sample_scenes, sample_characters)
    print(json.dumps(result, ensure_ascii=False, indent=2))
