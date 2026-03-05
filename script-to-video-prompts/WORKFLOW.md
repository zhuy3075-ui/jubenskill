# script-to-video-prompts 工作流

## 1. 目标
本文件定义项目内统一执行流程，覆盖：
- 模式A：剧本 -> 分镜 -> 提示词 -> 一致性 -> 导出
- 模式B：一句话创意 -> Seedance 提示词
- 模式D：视频理解 -> 剧本 -> 分镜 -> 导出
- 开发测试与交付检查

## 2. 环境准备
```powershell
cd c:\Users\zhuyue\Desktop\剧本skill\script-to-video-prompts
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pytest
```

## 3. 标准数据流（模式A）
输入：剧本文档（`.txt/.md/.docx/.pdf/.fdx`）

输出：`storyboard + characters + scenes + consistency report + 导出文件`

```python
from pathlib import Path
import sys

sys.path.insert(0, str(Path("scripts").resolve()))

from parse_script import parse_script
from character_extractor import extract_characters
from scene_analyzer import analyze_scenes
from storyboard_generator import generate_storyboard
from prompt_optimizer import PromptOptimizer
from consistency_checker import check_consistency
from export_utils import export_all

# 1) 解析剧本
parsed = parse_script("assets/example_input.txt")

# 2) 角色提取 + 3) 场景分析（可并行）
characters = extract_characters(parsed)
scenes = analyze_scenes(parsed)

# 4) 分镜生成
storyboard = generate_storyboard(parsed, scenes, characters)

# 4b) 提示词优化（可选）
optimizer = PromptOptimizer()
storyboard = optimizer.optimize_storyboard(storyboard, platform="seedance")

# 5) 一致性校验
consistency = check_consistency(storyboard, characters, scenes)

# 6) 导出
paths = export_all(
    storyboard=storyboard,
    characters=characters,
    scenes=scenes,
    output_dir="out",
    formats=["json", "csv", "markdown", "excel", "html"],
)

print("导出完成:", paths)
print("一致性问题数:", len(consistency.get("issues", [])))
```

## 4. 快速生成（模式B）
输入：一句话创意意图

```python
from pathlib import Path
import sys

sys.path.insert(0, str(Path("scripts").resolve()))

from prompt_optimizer import generate_seedance_prompt

result = generate_seedance_prompt(
    intent="10秒仙侠战斗，女侠在雨夜屋顶追击敌人",
    duration=10,
    genre="仙侠",
    aspect_ratio="16:9",
)

print(result["optimization"]["optimized"])
print("SCELA得分:", result["scela_analysis"]["score"])
print("合规问题:", result["compliance_issues"])
```

## 5. 视频理解串联（模式D）
输入：视频文件（`.mp4/.mov/.avi/.webm`）+ `yunwu.ai` API Key

```python
from pathlib import Path
import sys

sys.path.insert(0, str(Path("scripts").resolve()))

from video_analyzer import analyze_video_full
from character_extractor import extract_characters
from scene_analyzer import analyze_scenes
from storyboard_generator import generate_storyboard
from export_utils import export_all

video_result = analyze_video_full(
    file_path="your_video.mp4",
    api_key="YOUR_API_KEY",
)

parsed = video_result["parsed_script"]
characters = extract_characters(parsed)
scenes = analyze_scenes(parsed)
storyboard = generate_storyboard(parsed, scenes, characters)

export_all(storyboard, characters, scenes, output_dir="out", formats=["markdown", "json", "html"])
```

## 6. 测试流程
```powershell
# 全量测试
python -m pytest tests -v

# 关键回归
python -m pytest tests/test_regression.py -v

# 视频分析模块（全mock）
python -m pytest tests/test_video_analyzer.py -v
```

## 7. 交付检查清单
- 解析输出 `scenes[*].elements` 非空
- 分镜 `metadata.total_shots > 0`
- 提示词质量建议中无高风险合规警告
- 一致性报告 `issues` 已人工确认可接受
- `out/` 至少包含 `markdown + json` 两种产物

## 8. 参考文档
- `SKILL.md`（主规范）
- `references/seedance_compliance.md`（合规规则）
- `references/prompt_patterns.md`（提示词结构）
- `docs/evolution_protocol.md`（进化系统协议）

## 9. 极简版流程图（仅功能说明）

### 9.1 模式A：剧本到可交付分镜
剧本文档输入  
→ 剧本结构解析（场次、对白、动作、角色）  
→ 角色设定提取（外貌、服装、视觉关键词）  
→ 场景分析（地点、时间、光线、氛围）  
→ 分镜生成（镜号、景别、运镜、提示词）  
→ 提示词优化（质量增强、平台适配、合规检查）  
→ 一致性校验（角色/场景/光线/风格连续性）  
→ 多格式导出（JSON/CSV/Markdown/Excel/HTML）

可实现功能：
- 从剧本自动生成可直接用于 AI 视频生成的分镜提示词体系
- 自动给出角色与场景的统一视觉描述
- 产出可审阅、可归档、可二次编辑的交付文件

### 9.2 模式B：一句话创意直出提示词
一句话创意输入  
→ 类型识别（动作/仙侠/广告/短剧/科幻等）  
→ 模板匹配（生产级提示词结构）  
→ SCELA 要素展开（主体、镜头、情绪特效、光影风格、声音）  
→ 合规检查与替换建议  
→ 生成可用的 Seedance 风格提示词

可实现功能：
- 快速把创意意图转成平台可用提示词
- 自动提示缺失要素并提升提示词完整度
- 规避常见合规风险表达

### 9.3 模式D：视频理解反推剧本再生成分镜
视频文件输入  
→ 视频内容理解（场景、角色、对白、镜头语言）  
→ 结构化剧本重建（与剧本解析结果同构）  
→ 角色提取 + 场景分析  
→ 分镜与提示词生成  
→ 导出结果用于复刻/重构

可实现功能：
- 从现有视频自动反推结构化剧本
- 快速完成“视频理解 -> 分镜生产”闭环
- 支持对标学习与二次创作

### 9.4 质量与交付闭环
生成结果  
→ 质量检查（提示词完整度、合规、连续性）  
→ 问题定位与修正建议  
→ 最终交付（文档化与可视化）

可实现功能：
- 在生成阶段提前暴露一致性和合规问题
- 形成稳定可复用的内容生产流程
