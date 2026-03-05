#!/usr/bin/env python3
"""
回归测试集 — 覆盖 Codex 审查中的关键修复点

运行: python -m pytest tests/test_regression.py -v
或:   python tests/test_regression.py
"""

import sys
import os
import tempfile
from pathlib import Path

# 将 scripts 目录加入 path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from parse_script import ScriptParser, parse_script
from character_extractor import CharacterExtractor, extract_characters
from storyboard_generator import StoryboardGenerator, generate_storyboard
from scene_analyzer import SceneAnalyzer, analyze_scenes
from prompt_optimizer import PromptOptimizer, generate_seedance_prompt
from consistency_checker import ConsistencyChecker
from export_utils import (
    _sanitize_filename, _sanitize_cell, _esc, _validate_output_path,
)

import pytest


# ═══════════════════════════════════════════════════════
# 1. parse_script: 状态机 + elements 输出 + 编码回退
# ═══════════════════════════════════════════════════════

class TestParseScript:
    def test_scene_parsing(self):
        parser = ScriptParser()
        script = "场景1 内景 咖啡厅\n林晓薇：\n你好啊，今天天气真好。\n陈宇走进咖啡厅，坐在对面。\n陈宇：\n好久不见。\n"
        result = parser.parse_text(script, "测试")
        assert len(result.scenes) == 1

    def test_dialogue_not_misidentified_as_character(self):
        parser = ScriptParser()
        script = "场景1 内景 咖啡厅\n林晓薇：\n你好啊，今天天气真好。\n陈宇：\n好久不见。\n"
        result = parser.parse_text(script, "测试")
        elements = result.scenes[0].elements
        char_contents = [e.content for e in elements if e.type.value == "character"]
        assert "你好啊" not in char_contents

    def test_character_names_extracted(self):
        parser = ScriptParser()
        script = "场景1 内景 咖啡厅\n林晓薇：\n你好啊。\n陈宇：\n好久不见。\n"
        result = parser.parse_text(script, "测试")
        elements = result.scenes[0].elements
        char_elements = [e.content for e in elements if e.type.value == "character"]
        assert set(char_elements) == {"林晓薇", "陈宇"}

    def test_to_dict_contains_elements(self):
        parser = ScriptParser()
        result = parser.parse_text("场景1 咖啡厅\n角色说话", "测试")
        scene_dict = result.scenes[0].to_dict()
        assert "elements" in scene_dict
        assert len(scene_dict["elements"]) > 0

    def test_ext_recognition(self):
        parser = ScriptParser()
        result = parser.parse_text("场景1 外景 公园\n一个人在散步。", "测试")
        assert result.scenes[0].int_ext == "EXT."

    def test_gb18030_encoding_fallback(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="wb") as f:
            f.write("场景1 咖啡厅\n角色说话".encode("gb18030"))
            tmp_path = f.name
        try:
            result = parse_script(tmp_path)
            assert len(result["scenes"]) >= 1
        finally:
            os.unlink(tmp_path)

    def test_cross_call_no_pollution(self):
        parser = ScriptParser()
        parser.parse_text("场景1 办公室\n张伟：\n你好", "test1")
        r2 = parser.parse_text("场景1 教室\n李娜：\n再见", "test2")
        assert len(r2.scenes) == 1
        assert "张伟" not in r2.all_characters


# ═══════════════════════════════════════════════════════
# 2. character_extractor: 从 elements 提取特征
# ═══════════════════════════════════════════════════════

class TestCharacterExtractor:
    @pytest.fixture
    def parsed_data(self):
        return {
            "all_characters": ["林晓薇"],
            "scenes": [{
                "number": 1,
                "characters": ["林晓薇"],
                "elements": [
                    {"type": "action", "content": "林晓薇，青年女性，长发飘飘，苗条身材", "line_number": 1},
                    {"type": "character", "content": "林晓薇", "line_number": 2},
                    {"type": "dialogue", "content": "你好", "line_number": 3},
                ],
            }],
        }

    def test_gender_extraction(self, parsed_data):
        result = extract_characters(parsed_data)
        assert result["林晓薇"]["appearance"]["gender"] == "female"

    def test_hair_extraction(self, parsed_data):
        result = extract_characters(parsed_data)
        assert "long hair" in result["林晓薇"]["appearance"]["hair_style"]

    def test_visual_keywords_nonempty(self, parsed_data):
        result = extract_characters(parsed_data)
        assert len(result["林晓薇"]["visual_keywords"]) > 0

    def test_prompt_description_not_placeholder(self, parsed_data):
        result = extract_characters(parsed_data)
        assert "character named" not in result["林晓薇"]["prompt_description"]

    def test_cross_call_no_pollution(self, parsed_data):
        extract_characters(parsed_data)
        parsed2 = {
            "all_characters": ["陈宇"],
            "scenes": [{"number": 1, "characters": ["陈宇"], "elements": []}],
        }
        result2 = extract_characters(parsed2)
        assert "林晓薇" not in result2


# ═══════════════════════════════════════════════════════
# 3. storyboard_generator: 元素驱动
# ═══════════════════════════════════════════════════════

class TestStoryboardGenerator:
    @pytest.fixture
    def storyboard_inputs(self):
        parsed = {
            "title": "测试",
            "scenes": [{
                "number": 1,
                "characters": ["张伟", "李娜"],
                "elements": [
                    {"type": "action", "content": "张伟走进办公室", "line_number": 1},
                    {"type": "character", "content": "张伟", "line_number": 2},
                    {"type": "dialogue", "content": "早上好", "line_number": 3},
                    {"type": "action", "content": "李娜微笑着点头", "line_number": 4},
                ],
            }],
        }
        scenes = [{"scene_number": 1, "environment": {"location_type": "office", "int_ext": "INT"},
                   "visual_prompt": "office interior", "mood_keywords": ["professional"]}]
        chars = {"张伟": {"prompt_description": "young male"},
                 "李娜": {"prompt_description": "young female"}}
        return parsed, scenes, chars

    def test_element_driven_shot_generation(self, storyboard_inputs):
        parsed, scenes, chars = storyboard_inputs
        result = generate_storyboard(parsed, scenes, chars)
        assert len(result.get("shots", [])) >= 4

    def test_dialogue_shots_contain_content(self, storyboard_inputs):
        parsed, scenes, chars = storyboard_inputs
        result = generate_storyboard(parsed, scenes, chars)
        dialogue_shots = [s for s in result.get("shots", []) if s.get("dialogue")]
        assert len(dialogue_shots) >= 1
        assert "早上好" in dialogue_shots[0]["dialogue"]


# ═══════════════════════════════════════════════════════
# 4. export_utils: 安全防护
# ═══════════════════════════════════════════════════════

class TestExportSecurity:
    def test_html_escape(self):
        assert _esc('<script>alert(1)</script>') == '&lt;script&gt;alert(1)&lt;/script&gt;'

    def test_filename_sanitize_dotdot(self):
        assert ".." not in _sanitize_filename("../../etc/passwd")

    def test_filename_sanitize_slash(self):
        assert "/" not in _sanitize_filename("a/b/c")

    def test_path_traversal_blocked(self):
        with pytest.raises(ValueError):
            _validate_output_path(Path("/tmp/../../etc/passwd"), Path("/tmp/output"))

    @pytest.mark.parametrize("input_val,expected", [
        ("=SUM(A1)", "'=SUM(A1)"),
        ("+cmd", "'+cmd"),
        ("-1+1", "'-1+1"),
        ("@import", "'@import"),
        ("hello", "hello"),
        (42, 42),
    ])
    def test_formula_injection(self, input_val, expected):
        assert _sanitize_cell(input_val) == expected


# ═══════════════════════════════════════════════════════
# 5. prompt_optimizer: 子串替换不污染
# ═══════════════════════════════════════════════════════

class TestPromptOptimizer:
    def test_recommend_not_misreplaced(self):
        opt = PromptOptimizer()
        result = opt.optimize("这是一个推荐的场景")
        assert "push in" not in result.optimized

    def test_ramen_not_misreplaced(self):
        opt = PromptOptimizer()
        result = opt.optimize("角色在吃拉面")
        assert "pull out" not in result.optimized

    def test_standalone_push_replaced(self):
        opt = PromptOptimizer()
        result = opt.optimize("镜头 推 向角色")
        assert "push in" in result.optimized


# ═══════════════════════════════════════════════════════
# 6. consistency_checker: 光线检查不再空操作
# ═══════════════════════════════════════════════════════

class TestConsistencyChecker:
    @pytest.fixture
    def checker_inputs(self):
        storyboard = {
            "shots": [
                {"shot_id": "1-1", "scene_number": 1, "subject": "张伟"},
                {"shot_id": "1-2", "scene_number": 1, "subject": "张伟"},
                {"shot_id": "1-3", "scene_number": 1, "subject": "张伟"},
                {"shot_id": "1-4", "scene_number": 1, "subject": "李娜"},
            ],
        }
        chars = {
            "张伟": {"visual_keywords": ["male"], "prompt_description": "young male"},
            "李娜": {"visual_keywords": ["female"], "prompt_description": "young female"},
        }
        scenes = [
            {"scene_number": 1, "visual_prompt": "office",
             "mood_keywords": ["pro"],
             "environment": {"lighting": {"type": "natural", "color_temperature": "warm"}}},
        ]
        return storyboard, chars, scenes

    def test_lighting_check_produces_issues(self, checker_inputs):
        storyboard, chars, scenes = checker_inputs
        checker = ConsistencyChecker()
        result = checker.check_consistency(storyboard, chars, scenes)
        lighting_issues = [i for i in result.get("issues", []) if i["type"] == "lighting"]
        assert len(lighting_issues) >= 1

    def test_cross_call_no_pollution(self, checker_inputs):
        storyboard, chars, scenes = checker_inputs
        checker = ConsistencyChecker()
        checker.check_consistency(storyboard, chars, scenes)
        result2 = checker.check_consistency({"shots": []}, {}, [])
        assert len(result2.get("issues", [])) == 0


# ═══════════════════════════════════════════════════════
# 7. Seedance 融合: SCELA 检查 + 合规检测
# ═══════════════════════════════════════════════════════

class TestSeedanceIntegration:
    @pytest.fixture
    def optimizer(self):
        return PromptOptimizer()

    def test_scela_full_coverage(self, optimizer):
        prompt = (
            "虚拟红衣女侠, low angle tracking shot, "
            "蓝色电弧绕剑旋转 particle explosion, "
            "cinematic golden hour lighting, "
            "音效：剑鸣声 wind sound"
        )
        scela = optimizer.check_scela(prompt)
        assert scela["S"]["present"]
        assert scela["C"]["present"]
        assert scela["E"]["present"]
        assert scela["L"]["present"]
        assert scela["A"]["present"]
        assert scela["score"] == 1.0

    def test_scela_missing_detection(self, optimizer):
        scela = optimizer.check_scela("一个女孩在走路")
        assert scela["score"] < 1.0

    def test_scela_chinese_prompt_full(self, optimizer):
        """P0 复现: 纯中文提示词应能识别全部5要素"""
        prompt = "一个女孩在咖啡厅喝咖啡，慢慢推进镜头，暖色灯光，背景音乐轻柔"
        scela = optimizer.check_scela(prompt)
        assert scela["S"]["present"], f"S missing, prompt={prompt}"
        assert scela["C"]["present"], f"C missing, prompt={prompt}"
        assert scela["L"]["present"], f"L missing, prompt={prompt}"
        assert scela["A"]["present"], f"A missing, prompt={prompt}"
        assert scela["score"] >= 0.8, f"score={scela['score']}"

    def test_scela_case_insensitive(self, optimizer):
        """P1: HDR/BGM/8K 大小写不应漏检"""
        prompt = "product shot, HDR, BGM playing, 8K resolution, particle glow"
        scela = optimizer.check_scela(prompt)
        assert scela["L"]["present"], "HDR/8K should match L"
        assert scela["A"]["present"], "BGM should match A"

    def test_compliance_real_person(self, optimizer):
        result = optimizer.optimize(
            "成龙在雨中打功夫",
            context={"type": "video", "platform": "seedance"}
        )
        warnings = [s for s in result.suggestions if "合规警告" in s]
        assert len(warnings) >= 1

    def test_compliance_copyright_ip(self, optimizer):
        result = optimizer.optimize(
            "钢铁侠在城市上空飞行",
            context={"type": "video", "platform": "seedance"}
        )
        warnings = [s for s in result.suggestions if "合规警告" in s]
        assert len(warnings) >= 1

    def test_compliance_brand(self, optimizer):
        result = optimizer.optimize(
            "可口可乐易拉罐在桌上旋转",
            context={"type": "video", "platform": "seedance"}
        )
        warnings = [s for s in result.suggestions if "合规警告" in s]
        assert len(warnings) >= 1

    def test_no_compliance_on_generic_platform(self, optimizer):
        result = optimizer.optimize(
            "成龙在雨中打功夫",
            context={"type": "video"}
        )
        warnings = [s for s in result.suggestions if "合规警告" in s]
        assert len(warnings) == 0

    def test_storyboard_platform_passthrough(self, optimizer):
        """P1: optimize_storyboard 应透传 platform 触发合规检查"""
        storyboard = {
            "shots": [
                {"shot_id": "1-1", "visual_prompt": "钢铁侠在飞行"},
            ]
        }
        result = optimizer.optimize_storyboard(storyboard, platform="seedance")
        shot = result["shots"][0]
        assert "compliance_warnings" in shot
        assert len(shot["compliance_warnings"]) >= 1

    def test_scela_missing_returns_labels(self, optimizer):
        """check_scela 应返回 missing 列表"""
        scela = optimizer.check_scela("just text")
        assert "missing" in scela
        assert len(scela["missing"]) > 0


# ═══════════════════════════════════════════════════════
# 8. generate_seedance_prompt: 模式B执行入口
# ═══════════════════════════════════════════════════════

class TestGenerateSeedancePrompt:
    def test_genre_auto_detection(self):
        result = generate_seedance_prompt("10秒仙侠战斗场景")
        assert result["matched_genre"] in ("仙侠", "战斗")
        assert len(result["matched_templates"]) >= 1

    def test_genre_explicit(self):
        result = generate_seedance_prompt("一个人在飞", genre="科幻")
        assert result["matched_genre"] == "科幻"
        assert "Q" in result["matched_templates"]

    def test_duration_clamped(self):
        result = generate_seedance_prompt("test", duration=100)
        assert result["duration"] == 15
        result2 = generate_seedance_prompt("test", duration=1)
        assert result2["duration"] == 4

    def test_scela_analysis_present(self):
        result = generate_seedance_prompt("虚拟女侠，低角度跟拍，电弧特效，电影级光影，音效剑鸣")
        assert result["scela_analysis"]["score"] == 1.0

    def test_compliance_in_result(self):
        result = generate_seedance_prompt("成龙在打功夫")
        assert len(result["compliance_issues"]) >= 1

    def test_output_structure(self):
        result = generate_seedance_prompt("一个女孩在跳舞")
        for key in ("intent", "duration", "aspect_ratio", "matched_genre",
                     "matched_templates", "scela_analysis", "compliance_issues",
                     "optimization", "suggestions"):
            assert key in result, f"missing key: {key}"
