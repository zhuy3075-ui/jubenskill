#!/usr/bin/env python3
"""
提示词优化器 - 优化和精炼AI视频生成提示词
提高提示词的效果和一致性
"""

import re
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class OptimizedPrompt:
    """优化后的提示词"""
    original: str
    optimized: str
    added_keywords: List[str]
    removed_keywords: List[str]
    quality_score: float  # 0-1
    suggestions: List[str]


class PromptOptimizer:
    """提示词优化器"""

    # 质量提升关键词
    QUALITY_BOOSTERS = [
        "high quality",
        "cinematic",
        "professional lighting",
        "detailed",
        "sharp focus",
        "8k",
        "masterpiece",
    ]

    # 视频特定关键词
    VIDEO_KEYWORDS = [
        "smooth motion",
        "natural movement",
        "consistent lighting",
        "temporal coherence",
    ]

    # 应该避免的词
    NEGATIVE_KEYWORDS = [
        "blurry",
        "low quality",
        "distorted",
        "artifacts",
        "glitch",
        "noise",
        "grainy",
    ]

    # 冗余词检测
    REDUNDANT_PATTERNS = [
        (r'\b(very|really|extremely)\s+(very|really|extremely)\b', r'\1'),
        (r'\b(beautiful|pretty)\s+(beautiful|pretty)\b', r'\1'),
        (r'\s+', ' '),  # 多余空格
    ]

    # 景别关键词映射 (标准化)
    SHOT_SIZE_MAPPING = {
        "特写": "close-up",
        "大特写": "extreme close-up",
        "近景": "medium close-up",
        "中景": "medium shot",
        "中远景": "medium long shot",
        "远景": "long shot",
        "大远景": "extreme long shot",
        "全景": "wide shot",
    }

    # 运镜关键词映射
    CAMERA_MOVEMENT_MAPPING = {
        "推": "push in",
        "拉": "pull out",
        "摇": "pan",
        "移": "dolly",
        "跟": "tracking",
        "升": "crane up",
        "降": "crane down",
        "手持": "handheld",
        "固定": "static",
    }

    # SCELA 公式要素检查（Seedance 2.0 平台）
    # 所有关键词统一小写存储，检测时 prompt.lower() 后比对
    SCELA_ELEMENTS = {
        "S": {  # Subject 主体
            "keywords": [
                # 英文
                "character", "person", "man", "woman", "girl", "boy",
                "warrior", "dancer", "product", "ninja", "swordsman",
                "robot", "mech", "hero", "heroine", "model", "chef",
                # 中文 — 人物/主体类
                "虚拟", "原创", "女孩", "男孩", "女性", "男性", "女子", "男子",
                "少年", "少女", "武者", "侠客", "女侠", "剑客", "修士",
                "舞者", "角色", "主角", "人物", "机甲", "战士", "特工",
                "产品", "饮料", "食品", "化妆品", "护肤", "马克杯",
            ],
            "label": "Subject（主体）",
        },
        "C": {  # Camera 镜头
            "keywords": [
                # 英文
                "close-up", "medium shot", "wide shot", "tracking",
                "push in", "pull out", "pan", "handheld", "crane",
                "low angle", "high angle", "dolly", "aerial", "pov",
                "first person", "orbit", "steadicam",
                # 中文 — 景别/运镜
                "仰拍", "俯拍", "环绕", "一镜到底", "跟拍", "手持",
                "特写", "近景", "中景", "远景", "全景", "大特写",
                "推镜头", "拉镜头", "摇镜头", "移镜头", "航拍",
                "推进", "拉远", "慢推", "快切", "固定镜头",
                "侧面跟拍", "正面跟拍", "鸟瞰", "鱼眼",
                "镜头", "运镜", "构图",
            ],
            "label": "Camera（镜头）",
        },
        "E": {  # Emotion/Effect 情绪/特效
            "keywords": [
                # 英文
                "particle", "explosion", "glow", "spark", "lightning",
                "slow motion", "bullet time", "shockwave", "fire",
                "smoke", "rain", "snow", "fog", "mist", "blur",
                "flash", "ripple", "dissolve", "transform",
                # 中文 — 特效/情绪
                "粒子", "爆炸", "光效", "电弧", "冲击波", "火焰",
                "烟雾", "雨", "雪", "雾", "闪电", "涟漪",
                "慢动作", "慢镜", "慢放", "定格", "子弹时间",
                "变身", "变形", "转场", "特效", "法术", "魔法",
                "气场", "杀意", "紧张", "压迫", "震撼", "高燃",
                "温馨", "治愈", "感动", "悲伤", "愤怒", "惊恐",
            ],
            "label": "Emotion/Effect（情绪/特效）",
        },
        "L": {  # Light/Look 光影/风格
            "keywords": [
                # 英文（全部小写）
                "cinematic", "lighting", "golden hour", "neon",
                "warm tone", "cold tone", "hdr", "4k", "8k",
                "film grain", "bokeh", "lens flare", "backlight",
                "side light", "rim light", "natural light",
                "dramatic", "moody", "vintage", "retro",
                # 中文 — 光影/风格/色调
                "电影级", "霓虹", "暖色调", "冷色调", "暖色", "冷色",
                "暖光", "冷光", "灯光", "光线", "光影", "逆光",
                "侧光", "顶光", "自然光", "烛光", "月光",
                "色调", "色彩", "高对比", "低饱和", "莫兰迪",
                "赛博朋克", "写实", "水墨", "胶片", "质感",
                "风格", "画质", "高清", "超清",
            ],
            "label": "Light/Look（光影/风格）",
        },
        "A": {  # Audio 声音
            "keywords": [
                # 英文（全部小写）
                "sound", "audio", "music", "sfx", "bgm",
                "ambient", "footstep", "breath", "whisper",
                "thunder", "wind", "rain sound",
                # 中文 — 声音设计
                "音效", "声音", "背景音", "背景音乐", "配乐",
                "脚步声", "剑鸣", "呼吸声", "心跳", "风声",
                "雨声", "雷声", "爆炸声", "金属", "碰撞声",
                "环境音", "白噪音", "鸟鸣", "水声", "琴声",
                "吟唱", "旁白",
            ],
            "label": "Audio（声音设计）",
        },
    }

    # Seedance 违禁词快速检测
    SEEDANCE_FORBIDDEN_PATTERNS = [
        # 真实人名
        re.compile(r'(?:成龙|周杰伦|刘德华|范冰冰|杨幂|赵丽颖|迪丽热巴|肖战|王一博)'),
        # 版权IP
        re.compile(r'(?:钢铁侠|蜘蛛侠|蝙蝠侠|超人|火影|鸣人|原神|迪士尼|漫威|Marvel|Disney|Spider-Man|Iron Man)', re.IGNORECASE),
        # 品牌
        re.compile(r'(?:可口可乐|百事|星巴克|苹果|iPhone|Nike|Adidas|Coca-Cola|Pepsi|Starbucks)', re.IGNORECASE),
        # 暴力/血腥
        re.compile(r'(?:血腥|血浆|断肢|内脏|gore|dismember|entrails)', re.IGNORECASE),
        # 裸露/性暗示
        re.compile(r'(?:裸体|裸露|色情|性感|nude|naked|erotic|nsfw)', re.IGNORECASE),
        # 恐怖/灵异
        re.compile(r'(?:鬼怪|灵异|僵尸|恶灵|zombie|ghost|demon|horror)', re.IGNORECASE),
    ]

    def __init__(self):
        self._reset()

    def _reset(self):
        """重置状态，防止跨调用污染"""
        self.optimization_history: List[OptimizedPrompt] = []

    def optimize(self, prompt: str, context: Dict = None) -> OptimizedPrompt:
        """
        优化单个提示词

        Args:
            prompt: 原始提示词
            context: 上下文信息 (场景、角色等)

        Returns:
            优化后的提示词对象
        """
        original = prompt
        optimized = prompt
        added = []
        removed = []
        suggestions = []

        # 1. 标准化中文术语
        optimized = self._standardize_terms(optimized)

        # 2. 移除冗余
        optimized = self._remove_redundancy(optimized)

        # 3. 检测并移除负面词
        optimized, removed_neg = self._remove_negative_keywords(optimized)
        removed.extend(removed_neg)

        # 4. 添加质量提升词 (如果缺少)
        optimized, added_quality = self._add_quality_boosters(optimized)
        added.extend(added_quality)

        # 5. 添加视频特定关键词 (如果是视频提示词)
        if context and context.get('type') == 'video':
            optimized, added_video = self._add_video_keywords(optimized)
            added.extend(added_video)

        # 5b. Seedance 平台合规检查
        if context and context.get('platform', '').lower() in ('seedance', '即梦'):
            compliance_issues = self._check_seedance_compliance(optimized)
            if compliance_issues:
                suggestions.extend(compliance_issues)

        # 6. 优化结构
        optimized = self._optimize_structure(optimized)

        # 7. 计算质量分数
        quality_score = self._calculate_quality_score(optimized)

        # 8. 生成建议
        suggestions.extend(self._generate_suggestions(original, optimized, quality_score))

        result = OptimizedPrompt(
            original=original,
            optimized=optimized,
            added_keywords=added,
            removed_keywords=removed,
            quality_score=quality_score,
            suggestions=suggestions
        )

        self.optimization_history.append(result)
        return result

    def optimize_batch(self, prompts: List[str], context: Dict = None) -> List[OptimizedPrompt]:
        """批量优化提示词"""
        return [self.optimize(p, context) for p in prompts]

    def optimize_storyboard(self, storyboard: Dict, platform: str = None) -> Dict:
        """优化整个分镜的提示词

        Args:
            storyboard: 分镜数据
            platform: 目标平台（如 'seedance'），透传给合规检查
        """
        shots = storyboard.get('shots', [])

        for shot in shots:
            if 'visual_prompt' in shot:
                ctx = {'type': 'video', 'shot': shot}
                if platform:
                    ctx['platform'] = platform
                result = self.optimize(shot['visual_prompt'], context=ctx)
                shot['visual_prompt_original'] = result.original
                shot['visual_prompt'] = result.optimized
                shot['prompt_quality_score'] = result.quality_score
                # 合规告警写回 shot
                compliance_warnings = [s for s in result.suggestions
                                       if s.startswith("合规警告")]
                if compliance_warnings:
                    shot['compliance_warnings'] = compliance_warnings

        # 添加全局风格一致性提示
        global_style = self._extract_global_style(shots)
        storyboard['global_style_prompt'] = global_style

        return storyboard

    def _standardize_terms(self, prompt: str) -> str:
        """标准化术语 — 使用词边界匹配避免误替换"""
        result = prompt

        # 标准化景别（按长度降序，避免短词误匹配）
        for cn, en in sorted(self.SHOT_SIZE_MAPPING.items(),
                             key=lambda x: len(x[0]), reverse=True):
            # 使用正则确保中文词是独立的（前后不是中文字符）
            pattern = re.compile(
                r'(?<![一-龥])' + re.escape(cn) + r'(?![一-龥])'
            )
            result = pattern.sub(en, result)

        # 标准化运镜（同样按长度降序）
        for cn, en in sorted(self.CAMERA_MOVEMENT_MAPPING.items(),
                             key=lambda x: len(x[0]), reverse=True):
            pattern = re.compile(
                r'(?<![一-龥])' + re.escape(cn) + r'(?![一-龥])'
            )
            result = pattern.sub(en, result)

        return result

    def _remove_redundancy(self, prompt: str) -> str:
        """移除冗余"""
        result = prompt

        for pattern, replacement in self.REDUNDANT_PATTERNS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        # 移除重复的逗号
        result = re.sub(r',\s*,', ',', result)

        # 移除首尾逗号
        result = result.strip(' ,')

        return result

    def _remove_negative_keywords(self, prompt: str) -> Tuple[str, List[str]]:
        """移除负面关键词"""
        result = prompt
        removed = []

        for keyword in self.NEGATIVE_KEYWORDS:
            if keyword.lower() in result.lower():
                result = re.sub(rf'\b{keyword}\b', '', result, flags=re.IGNORECASE)
                removed.append(keyword)

        return self._remove_redundancy(result), removed

    def _add_quality_boosters(self, prompt: str) -> Tuple[str, List[str]]:
        """添加质量提升关键词"""
        added = []

        # 检查是否已包含质量词
        has_quality = any(
            kw.lower() in prompt.lower()
            for kw in self.QUALITY_BOOSTERS
        )

        if not has_quality:
            # 添加基本质量词
            boosters_to_add = ["high quality", "cinematic"]
            prompt = prompt + ", " + ", ".join(boosters_to_add)
            added.extend(boosters_to_add)

        return prompt, added

    def _add_video_keywords(self, prompt: str) -> Tuple[str, List[str]]:
        """添加视频特定关键词"""
        added = []

        has_video_kw = any(
            kw.lower() in prompt.lower()
            for kw in self.VIDEO_KEYWORDS
        )

        if not has_video_kw:
            video_kw = "smooth motion"
            prompt = prompt + f", {video_kw}"
            added.append(video_kw)

        return prompt, added

    def _optimize_structure(self, prompt: str) -> str:
        """优化提示词结构"""
        # 将提示词分割成部分
        parts = [p.strip() for p in prompt.split(',') if p.strip()]

        # 重新排序: 主体 -> 动作 -> 场景 -> 风格 -> 质量
        # (简单实现,可以更复杂)

        # 确保质量词在最后
        quality_parts = []
        other_parts = []

        for part in parts:
            is_quality = any(
                kw.lower() in part.lower()
                for kw in self.QUALITY_BOOSTERS
            )
            if is_quality:
                quality_parts.append(part)
            else:
                other_parts.append(part)

        # 重组
        all_parts = other_parts + quality_parts

        return ", ".join(all_parts)

    def _calculate_quality_score(self, prompt: str) -> float:
        """计算提示词质量分数"""
        score = 0.5  # 基础分

        # 长度检查 (50-200字符最佳)
        length = len(prompt)
        if 50 <= length <= 200:
            score += 0.1
        elif length < 30:
            score -= 0.1
        elif length > 300:
            score -= 0.05

        # 质量词检查
        quality_count = sum(
            1 for kw in self.QUALITY_BOOSTERS
            if kw.lower() in prompt.lower()
        )
        score += min(quality_count * 0.05, 0.15)

        # 负面词检查
        negative_count = sum(
            1 for kw in self.NEGATIVE_KEYWORDS
            if kw.lower() in prompt.lower()
        )
        score -= negative_count * 0.1

        # 结构检查 (逗号分隔的描述)
        comma_count = prompt.count(',')
        if 3 <= comma_count <= 10:
            score += 0.1

        return max(0, min(1, score))

    def _generate_suggestions(
        self,
        original: str,
        optimized: str,
        quality_score: float
    ) -> List[str]:
        """生成改进建议"""
        suggestions = []

        if quality_score < 0.5:
            suggestions.append("提示词质量较低,建议添加更多描述性细节")

        if len(optimized) < 50:
            suggestions.append("提示词较短,建议添加场景、光线、氛围等描述")

        if len(optimized) > 300:
            suggestions.append("提示词较长,建议精简冗余描述")

        if "lighting" not in optimized.lower() and "光" not in optimized:
            suggestions.append("建议添加光线描述 (如 'soft lighting', 'dramatic shadows')")

        if not any(mood in optimized.lower() for mood in ["mood", "atmosphere", "氛围"]):
            suggestions.append("建议添加氛围描述 (如 'tense atmosphere', 'peaceful mood')")

        return suggestions

    def _extract_global_style(self, shots: List[Dict]) -> str:
        """从所有镜头中提取全局风格"""
        all_prompts = [s.get('visual_prompt', '') for s in shots]

        # 找出共同的关键词
        from collections import Counter

        all_words = []
        for prompt in all_prompts:
            words = [w.strip().lower() for w in prompt.split(',')]
            all_words.extend(words)

        word_counts = Counter(all_words)

        # 选择出现频率超过50%的词
        threshold = len(shots) * 0.5
        common_words = [
            word for word, count in word_counts.items()
            if count >= threshold and len(word) > 3
        ]

        if common_words:
            return ", ".join(common_words[:10])
        else:
            return "cinematic, high quality, consistent style"

    def check_scela(self, prompt: str) -> Dict:
        """检查提示词是否覆盖 SCELA 五要素（Seedance 2.0）"""
        result = {}
        prompt_lower = prompt.lower()
        for key, info in self.SCELA_ELEMENTS.items():
            found = any(kw.lower() in prompt_lower for kw in info["keywords"])
            result[key] = {
                "label": info["label"],
                "present": found,
            }
        result["score"] = sum(1 for v in result.values()
                              if isinstance(v, dict) and v.get("present")) / 5.0
        missing = [v["label"] for v in result.values()
                   if isinstance(v, dict) and not v.get("present")]
        result["missing"] = missing
        return result

    def _check_seedance_compliance(self, prompt: str) -> List[str]:
        """检查 Seedance 平台合规性，返回违规提示列表"""
        issues = []
        for pattern in self.SEEDANCE_FORBIDDEN_PATTERNS:
            match = pattern.search(prompt)
            if match:
                issues.append(
                    f"合规警告：检测到可能的违禁词「{match.group()}」，"
                    f"建议替换为合规描述（详见 seedance_compliance.md）"
                )
        return issues


def optimize_prompt(prompt: str, context: Dict = None) -> Dict:
    """
    优化提示词的便捷函数

    Args:
        prompt: 原始提示词
        context: 上下文信息

    Returns:
        优化结果字典
    """
    optimizer = PromptOptimizer()
    result = optimizer.optimize(prompt, context)

    return {
        "original": result.original,
        "optimized": result.optimized,
        "added_keywords": result.added_keywords,
        "removed_keywords": result.removed_keywords,
        "quality_score": result.quality_score,
        "suggestions": result.suggestions
    }


# 模式B 类型→模板映射
SEEDANCE_GENRE_MAP = {
    "动作": ["A", "B", "C"], "战斗": ["A", "B", "C"], "追逐": ["B"],
    "功夫": ["A"], "格斗": ["A"],
    "仙侠": ["D", "E"], "奇幻": ["D", "E"], "史诗": ["D", "E"],
    "修仙": ["D"], "法术": ["D"], "魔法": ["D"], "神话": ["E"],
    "产品": ["F", "G", "H"], "电商": ["F", "G", "H"], "广告": ["F", "G", "H"],
    "带货": ["F"], "商业": ["F"],
    "短剧": ["I", "J"], "对白": ["I"], "情感": ["I", "J"],
    "霸总": ["I"], "台词": ["I"], "反转": ["I", "J"],
    "变身": ["K", "L"], "变装": ["K"], "转场": ["L"],
    "舞蹈": ["M", "N"], "卡点": ["N"], "MV": ["N"],
    "生活": ["O", "P"], "治愈": ["O"], "Vlog": ["P"], "日常": ["O"],
    "科幻": ["Q", "R"], "机甲": ["Q"], "末日": ["R"], "机器人": ["Q"],
}


def generate_seedance_prompt(
    intent: str,
    duration: int = 10,
    genre: str = None,
    aspect_ratio: str = "16:9",
) -> Dict:
    """
    模式B 执行入口：根据一句话意图生成 Seedance 2.0 提示词结构

    Args:
        intent: 用户的一句话创意意图
        duration: 视频时长（秒），4-15
        genre: 风格类型（如 "仙侠"、"产品"），为 None 时自动从 intent 推断
        aspect_ratio: 画面比例，"16:9" 或 "9:16"

    Returns:
        {
            "intent": str,
            "duration": int,
            "aspect_ratio": str,
            "matched_genre": str,
            "matched_templates": List[str],
            "scela_analysis": Dict,
            "compliance_issues": List[str],
            "optimization": Dict,
            "suggestions": List[str],
        }
    """
    optimizer = PromptOptimizer()

    # 1. 推断类型 → 匹配模板
    matched_genre = genre or ""
    matched_templates = []
    if not genre:
        for keyword, templates in SEEDANCE_GENRE_MAP.items():
            if keyword in intent:
                matched_genre = keyword
                matched_templates = templates
                break
    else:
        matched_templates = SEEDANCE_GENRE_MAP.get(genre, [])

    # 2. SCELA 要素分析
    scela = optimizer.check_scela(intent)

    # 3. 优化提示词
    opt_result = optimizer.optimize(
        intent,
        context={"type": "video", "platform": "seedance"}
    )

    # 4. 合规检查（已在 optimize 中执行，提取结果）
    compliance_issues = [s for s in opt_result.suggestions if s.startswith("合规警告")]
    other_suggestions = [s for s in opt_result.suggestions if not s.startswith("合规警告")]

    # 5. 基于 SCELA 缺失要素生成补充建议
    if scela["missing"]:
        other_suggestions.insert(
            0,
            f"SCELA 缺失要素：{', '.join(scela['missing'])}，建议补充以提升提示词质量"
        )

    return {
        "intent": intent,
        "duration": max(4, min(15, duration)),
        "aspect_ratio": aspect_ratio,
        "matched_genre": matched_genre,
        "matched_templates": matched_templates,
        "scela_analysis": scela,
        "compliance_issues": compliance_issues,
        "optimization": {
            "original": opt_result.original,
            "optimized": opt_result.optimized,
            "quality_score": opt_result.quality_score,
        },
        "suggestions": other_suggestions,
    }


if __name__ == "__main__":
    # 示例用法
    test_prompts = [
        "一个女孩在咖啡厅喝咖啡",
        "close-up of man, angry expression, dark room",
        "beautiful beautiful sunset, very very nice, low quality scene"
    ]

    optimizer = PromptOptimizer()

    for prompt in test_prompts:
        result = optimizer.optimize(prompt, context={'type': 'video'})
        print(f"\n原始: {result.original}")
        print(f"优化: {result.optimized}")
        print(f"质量分: {result.quality_score:.2f}")
        print(f"建议: {result.suggestions}")
