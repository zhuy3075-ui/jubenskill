# script-to-video-prompts 使用指南

## 1. 文档用途
本指南用于直接落地执行项目功能，包含完整操作步骤、输入输出规范、质检和排错说明。  
本指南不包含原理讲解。

## 2. 环境准备

### 2.1 基础环境
- Python 3.10+
- Windows PowerShell（项目当前环境）
- 可联网（模式D需要调用 API）

### 2.2 安装依赖
```powershell
cd c:\Users\zhuyue\Desktop\剧本skill\script-to-video-prompts
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pytest
```

### 2.3 可选依赖说明
- `python-docx`：解析 `.docx` 剧本
- `pdfplumber`：解析 `.pdf` 剧本
- `openpyxl`：导出 `.xlsx`

## 3. 目录与文件约定

### 3.1 推荐目录
- 输入剧本：`assets/` 或自建 `in/`
- 输出结果：`out/`
- 参考规范：`references/`

### 3.2 核心脚本入口
- `scripts/parse_script.py`：`parse_script(file_path)`
- `scripts/character_extractor.py`：`extract_characters(parsed_script)`
- `scripts/scene_analyzer.py`：`analyze_scenes(parsed_script)`
- `scripts/storyboard_generator.py`：`generate_storyboard(parsed, scenes, chars)`
- `scripts/prompt_optimizer.py`：`generate_seedance_prompt(...)` / `PromptOptimizer().optimize_storyboard(...)`
- `scripts/consistency_checker.py`：`check_consistency(storyboard, chars, scenes)`
- `scripts/export_utils.py`：`export_all(storyboard, chars, scenes, output_dir, formats)`
- `scripts/video_analyzer.py`：`analyze_video(...)` / `analyze_video_full(...)`

## 4. 快速开始（5 分钟）

### 4.1 跑通模式A（剧本 -> 导出）
在 IDE 新建并运行以下脚本：

```python
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path("scripts").resolve()))

from parse_script import parse_script
from character_extractor import extract_characters
from scene_analyzer import analyze_scenes
from storyboard_generator import generate_storyboard
from prompt_optimizer import PromptOptimizer
from consistency_checker import check_consistency
from export_utils import export_all

parsed = parse_script("assets/example_input.txt")
characters = extract_characters(parsed)
scenes = analyze_scenes(parsed)
storyboard = generate_storyboard(parsed, scenes, characters)

optimizer = PromptOptimizer()
storyboard = optimizer.optimize_storyboard(storyboard, platform="seedance")

consistency = check_consistency(storyboard, characters, scenes)
paths = export_all(storyboard, characters, scenes, output_dir="out", formats=["json", "markdown", "html"])

print("导出路径:", json.dumps(paths, ensure_ascii=False, indent=2))
print("一致性问题数:", len(consistency.get("issues", [])))
```

### 4.2 快速验证结果
- `out/` 下出现至少 `json`、`md`、`html`
- `storyboard.metadata.total_shots > 0`
- `consistency.issues` 已生成（数量可为 0 或 >0）

## 5. 模式A：剧本流水线（完整步骤）

### 5.1 输入
- 支持：`.txt`、`.md`、`.docx`、`.pdf`、`.fdx`
- 示例文件：`assets/example_input.txt`

### 5.2 执行顺序
1. 解析剧本：`parse_script(file_path)`
2. 提取角色：`extract_characters(parsed_script)`
3. 分析场景：`analyze_scenes(parsed_script)`
4. 生成分镜：`generate_storyboard(parsed, scenes, chars)`
5. 提示词优化（可选）：`PromptOptimizer().optimize_storyboard(...)`
6. 一致性校验：`check_consistency(...)`
7. 导出：`export_all(...)`

### 5.3 建议导出格式
- 最低交付：`json + markdown`
- 演示展示：追加 `html`
- 表格协作：追加 `csv` 或 `excel`

### 5.4 模式A交付物
- 分镜数据（镜号、景别、运镜、提示词）
- 角色设定（视觉描述、关键词、出场场景）
- 场景设定（地点、时间、光线、氛围）
- 一致性报告（问题项与修正建议）
- 多格式文件（json/csv/md/xlsx/html）

## 6. 模式B：一句话直出 Seedance 提示词

### 6.1 输入
- `intent`：一句话创意
- `duration`：4-15 秒
- `genre`：建议明确填写（如：仙侠、动作、广告、科幻）
- `aspect_ratio`：`16:9` 或 `9:16`

### 6.2 执行示例
```python
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path("scripts").resolve()))
from prompt_optimizer import generate_seedance_prompt

result = generate_seedance_prompt(
    intent="10秒仙侠战斗，女侠雨夜屋顶追击",
    duration=10,
    genre="仙侠",
    aspect_ratio="16:9",
)

print(json.dumps(result, ensure_ascii=False, indent=2))
```

### 6.3 输出读取
- `optimization.optimized`：可直接使用的优化提示词
- `scela_analysis`：SCELA覆盖情况
- `compliance_issues`：需处理的合规项
- `matched_templates`：命中模板编号

## 7. 模式C：视频拆解与爆款重构（执行版）

### 7.1 输入要求
- 必选：对标视频链接或视频文件
- 可选：发布时间、播放量、评论区截图、重构目标（复刻/差异化）

### 7.2 固定执行阶段
1. 阶段一：素材检查与目标确认
2. 阶段二：深度拆解报告（五维分析 + 评论洞察 + 策略菜单）
3. 阶段三：微创新重构（保留可复用资产 + 定向改写）
4. 阶段四：融合方案与迭代建议

### 7.3 每轮必须输出
- 可读版质检清单（参照 `SKILL.md` C8）
- 结构化质检 JSON（模板：`assets/c7_quality_gate_template.json`）

### 7.4 模式C交付标准
- 所有 `@标签` 已定义且逐字一致
- 分镜可独立使用（无“同上/略/占位符”）
- 合规风险项已标注或替换
- 网关字段齐全，`gate_decision.status` 与检查结果一致

## 8. 模式D：视频理解 -> 剧本 -> 分镜

### 8.1 输入
- 视频文件：`.mp4/.mov/.avi/.webm`
- `yunwu.ai` API Key

### 8.2 文件限制
- 最大 50MB（超出直接失败）
- 超过 20MB 会提示处理较慢

### 8.3 执行示例（完整结果）
```python
from pathlib import Path
import sys
import json

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
paths = export_all(storyboard, characters, scenes, output_dir="out", formats=["json", "markdown", "html"])

print("analysis_quality:", video_result["analysis_quality"])
print("warnings:", video_result["warnings"])
print("导出路径:", json.dumps(paths, ensure_ascii=False, indent=2))
```

### 8.4 输出内容
- `parsed_script`：可直接接入模式A后半段
- `character_hints`：视频识别的角色外貌提示
- `video_metadata`：时长与风格元信息
- `analysis_quality`：质量评分
- `warnings`：处理警告

## 9. 测试与验收

### 9.1 运行测试
```powershell
python -m pytest tests -v
python -m pytest tests/test_regression.py -v
python -m pytest tests/test_video_analyzer.py -v
```

### 9.2 验收清单
- 解析结果含 `scenes[*].elements`
- 分镜镜头数量 > 0
- 导出文件成功生成
- 合规警告已人工确认
- 一致性报告已人工确认

## 10. 常见问题处理（仅操作）

### 10.1 解析 `.docx` 失败
执行：
```powershell
pip install python-docx
```

### 10.2 解析 `.pdf` 失败
执行：
```powershell
pip install pdfplumber
```

### 10.3 导出 Excel 失败
执行：
```powershell
pip install openpyxl
```

### 10.4 模式D 报 API Key 错误
处理步骤：
1. 重新确认 API Key 未过期
2. 确认调用地址使用 `yunwu.ai`
3. 保持网络可访问

### 10.5 模式D 报文件过大
处理步骤：
1. 压缩视频到 50MB 以下
2. 保留主内容后重试

## 11. 推荐执行顺序
1. 先用 `assets/example_input.txt` 跑通模式A
2. 再接入真实剧本文件
3. 再启用模式B快速创意生成
4. 最后接入模式D视频理解流程

## 12. 关联文档
- `WORKFLOW.md`：工作流总览
- `SKILL.md`：完整规范
- `references/seedance_compliance.md`：合规清单
- `references/prompt_patterns.md`：提示词模板
