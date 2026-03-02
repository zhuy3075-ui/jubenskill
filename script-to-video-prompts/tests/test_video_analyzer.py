#!/usr/bin/env python3
"""
视频理解分析器测试 - video_analyzer.py 单元测试

全部 mock HTTP 调用，不实际请求 API。
"""

import json
import base64
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# 将 scripts 目录加入 sys.path
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "scripts")
)

from video_analyzer import VideoAnalyzer, analyze_video, analyze_video_full


# ======================================================================
# 测试夹具
# ======================================================================

SAMPLE_GEMINI_RESPONSE = {
    "title": "测试视频 - 咖啡厅场景",
    "scenes": [
        {
            "number": 1,
            "heading": "INT. 咖啡厅 - DAY",
            "location": "咖啡厅",
            "time_of_day": "DAY",
            "int_ext": "INT.",
            "characters": ["红衣女子", "西装男"],
            "elements": [
                {
                    "type": "scene_heading",
                    "content": "INT. 咖啡厅 - DAY",
                    "line_number": 0,
                    "metadata": {},
                },
                {
                    "type": "action",
                    "content": "红衣女子走进咖啡厅，环顾四周",
                    "line_number": 0,
                    "metadata": {},
                },
                {
                    "type": "character",
                    "content": "红衣女子",
                    "line_number": 0,
                    "metadata": {},
                },
                {
                    "type": "dialogue",
                    "content": "你好，好久不见",
                    "line_number": 0,
                    "metadata": {},
                },
                {
                    "type": "action",
                    "content": "西装男微笑着站起来",
                    "line_number": 0,
                    "metadata": {},
                },
            ],
            "mood": "温馨",
            "lighting": {
                "type": "natural",
                "direction": "side",
                "color_temperature": "warm",
            },
        },
        {
            "number": 2,
            "heading": "EXT. 街道 - EVENING",
            "location": "街道",
            "time_of_day": "EVENING",
            "int_ext": "EXT.",
            "characters": ["红衣女子"],
            "elements": [
                {
                    "type": "scene_heading",
                    "content": "EXT. 街道 - EVENING",
                    "line_number": 0,
                    "metadata": {},
                },
                {
                    "type": "action",
                    "content": "红衣女子独自走在街道上",
                    "line_number": 0,
                    "metadata": {},
                },
            ],
        },
    ],
    "all_characters": ["红衣女子", "西装男"],
    "all_locations": ["咖啡厅", "街道"],
    "character_descriptions": {
        "红衣女子": "青年女性，约25岁，长黑色直发，穿红色大衣",
        "西装男": "中年男性，约35岁，短发，穿深蓝色西装",
    },
    "video_metadata": {
        "estimated_duration_seconds": 30,
        "dominant_style": "cinematic",
        "color_palette": ["warm earth tones"],
        "overall_mood": "温馨",
    },
}


@pytest.fixture
def analyzer():
    return VideoAnalyzer()


@pytest.fixture
def tmp_video(tmp_path):
    """创建临时 mp4 文件（内容为假数据，仅用于验证文件操作）"""
    video_file = tmp_path / "test.mp4"
    video_file.write_bytes(b"\x00" * 1024)  # 1KB 假视频
    return str(video_file)


@pytest.fixture
def large_video(tmp_path):
    """创建 25MB 临时文件（触发警告）"""
    video_file = tmp_path / "large.mp4"
    video_file.write_bytes(b"\x00" * (25 * 1024 * 1024))
    return str(video_file)


@pytest.fixture
def oversized_video(tmp_path):
    """创建 55MB 临时文件（超出限制）"""
    video_file = tmp_path / "oversized.mp4"
    video_file.write_bytes(b"\x00" * (55 * 1024 * 1024))
    return str(video_file)


# ======================================================================
# TestVideoValidation
# ======================================================================


class TestVideoValidation:
    """视频文件验证测试"""

    def test_supported_formats(self, analyzer):
        """支持 mp4/mov/avi/webm 四种格式"""
        assert ".mp4" in analyzer.SUPPORTED_FORMATS
        assert ".mov" in analyzer.SUPPORTED_FORMATS
        assert ".avi" in analyzer.SUPPORTED_FORMATS
        assert ".webm" in analyzer.SUPPORTED_FORMATS

    def test_valid_mp4(self, analyzer, tmp_video):
        """合法 mp4 文件通过验证"""
        info = analyzer._validate_video(tmp_video)
        assert info.mime_type == "video/mp4"
        assert info.file_size_bytes == 1024

    def test_unsupported_format_rejected(self, analyzer, tmp_path):
        """不支持的格式抛出 ValueError"""
        flv_file = tmp_path / "test.flv"
        flv_file.write_bytes(b"\x00" * 100)
        with pytest.raises(ValueError, match="不支持的视频格式"):
            analyzer._validate_video(str(flv_file))

    def test_file_not_found(self, analyzer):
        """不存在的文件抛出 FileNotFoundError"""
        with pytest.raises(FileNotFoundError, match="视频文件不存在"):
            analyzer._validate_video("/nonexistent/video.mp4")

    def test_empty_file_rejected(self, analyzer, tmp_path):
        """空文件被拒绝"""
        empty = tmp_path / "empty.mp4"
        empty.write_bytes(b"")
        with pytest.raises(ValueError, match="视频文件为空"):
            analyzer._validate_video(str(empty))

    def test_oversized_file_rejected(self, analyzer, oversized_video):
        """超过 50MB 的文件被拒绝"""
        with pytest.raises(ValueError, match="上限"):
            analyzer._validate_video(oversized_video)

    def test_large_file_warning(self, analyzer, large_video):
        """20-50MB 文件通过但产生警告"""
        info = analyzer._validate_video(large_video)
        assert info.file_size_bytes > 0
        assert len(analyzer.warnings) == 1
        assert "较大" in analyzer.warnings[0]


# ======================================================================
# TestBase64Encoding
# ======================================================================


class TestBase64Encoding:
    """Base64 编码测试"""

    def test_encode_small_file(self, analyzer, tmp_video):
        """小文件正确编码为 base64"""
        info = analyzer._validate_video(tmp_video)
        b64 = analyzer._encode_video_base64(info)
        assert isinstance(b64, str)
        assert len(b64) > 0

    def test_encode_result_is_valid_base64(self, analyzer, tmp_video):
        """编码结果可正确解码"""
        info = analyzer._validate_video(tmp_video)
        b64 = analyzer._encode_video_base64(info)
        decoded = base64.b64decode(b64)
        assert decoded == b"\x00" * 1024


# ======================================================================
# TestApiConfig
# ======================================================================


class TestApiConfig:
    """API 配置测试"""

    def test_explicit_params(self, analyzer):
        """显式参数优先"""
        config = analyzer._build_api_config(
            "test-key", "https://custom.api", "gemini-pro"
        )
        assert config.api_key == "test-key"
        assert config.base_url == "https://custom.api"
        assert config.model == "gemini-pro"

    def test_default_values(self, analyzer):
        """省略参数使用默认值"""
        config = analyzer._build_api_config("test-key", None, None)
        assert config.base_url == "https://yunwu.ai"
        assert config.model == "gemini-2.5-pro"

    def test_empty_api_key_rejected(self, analyzer):
        """空 API Key 被拒绝"""
        with pytest.raises(ValueError, match="API Key 不能为空"):
            analyzer._build_api_config("", None, None)

        with pytest.raises(ValueError, match="API Key 不能为空"):
            analyzer._build_api_config("   ", None, None)


# ======================================================================
# TestResponseParsing
# ======================================================================


class TestResponseParsing:
    """Gemini 响应解析测试（4级容错）"""

    def test_clean_json(self, analyzer):
        """Level 1: 干净的 JSON 字符串"""
        raw = json.dumps(SAMPLE_GEMINI_RESPONSE, ensure_ascii=False)
        result = analyzer._parse_gemini_response(raw)
        assert result["title"] == "测试视频 - 咖啡厅场景"
        assert len(result["scenes"]) == 2

    def test_json_in_code_block(self, analyzer):
        """Level 2: JSON 包在 ```json ``` 代码块中"""
        raw = (
            "以下是分析结果：\n\n```json\n"
            + json.dumps(SAMPLE_GEMINI_RESPONSE, ensure_ascii=False)
            + "\n```\n\n分析完成。"
        )
        result = analyzer._parse_gemini_response(raw)
        assert result["title"] == "测试视频 - 咖啡厅场景"

    def test_json_with_surrounding_text(self, analyzer):
        """Level 3: JSON 前后有多余文字"""
        raw = (
            "Here is the analysis:\n"
            + json.dumps(SAMPLE_GEMINI_RESPONSE, ensure_ascii=False)
            + "\nDone."
        )
        result = analyzer._parse_gemini_response(raw)
        assert result["title"] == "测试视频 - 咖啡厅场景"

    def test_malformed_json_fallback(self, analyzer):
        """Level 4: 完全无法解析，降级为纯文本"""
        raw = "这是一段无法解析的文本，没有任何JSON结构"
        result = analyzer._parse_gemini_response(raw)
        assert result["title"] == "视频分析（纯文本降级）"
        assert len(result["scenes"]) == 1
        assert result["scenes"][0]["elements"][0]["type"] == "action"
        assert len(analyzer.warnings) == 1
        assert "降级" in analyzer.warnings[0]

    def test_missing_scenes_handled(self, analyzer):
        """缺少 scenes 字段不报错"""
        raw = json.dumps({"title": "Test", "all_characters": []})
        result = analyzer._parse_gemini_response(raw)
        assert result.get("scenes") is None or result.get("scenes") == []


# ======================================================================
# TestParsedScriptMapping
# ======================================================================


class TestParsedScriptMapping:
    """ParsedScript 映射测试"""

    def test_output_has_required_keys(self, analyzer):
        """输出包含 ParsedScript 必需字段"""
        mapped = analyzer._map_to_parsed_script(SAMPLE_GEMINI_RESPONSE)
        assert "title" in mapped
        assert "metadata" in mapped
        assert "total_duration_seconds" in mapped
        assert "total_duration_formatted" in mapped
        assert "all_characters" in mapped
        assert "all_locations" in mapped
        assert "scenes" in mapped

    def test_scenes_have_elements(self, analyzer):
        """每个场景包含 elements 列表"""
        mapped = analyzer._map_to_parsed_script(SAMPLE_GEMINI_RESPONSE)
        for scene in mapped["scenes"]:
            assert "elements" in scene
            assert isinstance(scene["elements"], list)
            assert "element_count" in scene
            assert scene["element_count"] == len(scene["elements"])

    def test_element_types_valid(self, analyzer):
        """所有 element type 合法"""
        valid_types = {
            "scene_heading", "action", "character",
            "dialogue", "parenthetical", "transition", "note",
        }
        mapped = analyzer._map_to_parsed_script(SAMPLE_GEMINI_RESPONSE)
        for scene in mapped["scenes"]:
            for elem in scene["elements"]:
                assert elem["type"] in valid_types

    def test_characters_extracted(self, analyzer):
        """角色列表正确提取"""
        mapped = analyzer._map_to_parsed_script(SAMPLE_GEMINI_RESPONSE)
        assert "红衣女子" in mapped["all_characters"]
        assert "西装男" in mapped["all_characters"]

    def test_scene_structure_matches_parse_script(self, analyzer):
        """场景结构与 parse_script 输出一致"""
        mapped = analyzer._map_to_parsed_script(SAMPLE_GEMINI_RESPONSE)
        scene = mapped["scenes"][0]
        # parse_script 输出的 scene 必有字段
        assert "number" in scene
        assert "heading" in scene
        assert "location" in scene
        assert "time_of_day" in scene
        assert "int_ext" in scene
        assert "characters" in scene
        assert "estimated_duration" in scene
        assert "element_count" in scene
        assert "elements" in scene

    def test_duration_estimation(self, analyzer):
        """时长估算合理"""
        mapped = analyzer._map_to_parsed_script(SAMPLE_GEMINI_RESPONSE)
        assert mapped["total_duration_seconds"] > 0
        assert ":" in mapped["total_duration_formatted"]


# ======================================================================
# TestQualityAssessment
# ======================================================================


class TestQualityAssessment:
    """分析质量评估测试"""

    def test_full_analysis_high_score(self, analyzer):
        """完整分析数据得分 >= 0.8"""
        mapped = analyzer._map_to_parsed_script(SAMPLE_GEMINI_RESPONSE)
        score = analyzer._assess_quality(mapped)
        assert score >= 0.8

    def test_empty_analysis_low_score(self, analyzer):
        """空数据得分 = 0"""
        score = analyzer._assess_quality({"scenes": []})
        assert score == 0.0

    def test_partial_analysis_medium_score(self, analyzer):
        """部分数据得分在 0.2-0.7 之间"""
        partial = {
            "scenes": [
                {
                    "elements": [
                        {"type": "action", "content": "test"}
                    ]
                }
            ],
            "all_characters": ["角色A"],
            "all_locations": [],
        }
        score = analyzer._assess_quality(partial)
        assert 0.2 <= score <= 0.7


# ======================================================================
# TestCrossCallPollution
# ======================================================================


class TestCrossCallPollution:
    """跨调用状态污染测试"""

    def test_reset_clears_warnings(self):
        """两次调用不共享 warnings"""
        a = VideoAnalyzer()
        a.warnings.append("test warning")
        a._reset()
        assert len(a.warnings) == 0


# ======================================================================
# TestConvenienceFunctions
# ======================================================================


class TestConvenienceFunctions:
    """模块级便捷函数测试"""

    @patch.object(VideoAnalyzer, "analyze_video")
    def test_analyze_video_returns_parsed_script(self, mock_method):
        """analyze_video() 返回 parsed_script 字段"""
        mock_method.return_value = {
            "parsed_script": {"title": "test"},
            "character_hints": {},
            "video_metadata": {},
            "analysis_quality": 0.8,
            "warnings": [],
        }
        result = analyze_video("test.mp4", "key")
        assert result == {"title": "test"}

    @patch.object(VideoAnalyzer, "analyze_video")
    def test_analyze_video_full_returns_all(self, mock_method):
        """analyze_video_full() 返回完整结果"""
        expected = {
            "parsed_script": {"title": "test"},
            "character_hints": {"角色A": "desc"},
            "video_metadata": {},
            "analysis_quality": 0.8,
            "warnings": [],
        }
        mock_method.return_value = expected
        result = analyze_video_full("test.mp4", "key")
        assert "parsed_script" in result
        assert "character_hints" in result
        assert "analysis_quality" in result
