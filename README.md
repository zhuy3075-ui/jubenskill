# script-to-video-prompts

AI 视频提示词与分镜工作流工具集，支持从剧本/创意/视频输入到可执行提示词与导出交付。

## 目录
- [项目能力](#项目能力)
- [快速开始](#快速开始)
- [输入与输出](#输入与输出)
- [四种工作模式](#四种工作模式)
- [质量与进化机制](#质量与进化机制)
- [命令速查](#命令速查)
- [目录结构](#目录结构)
- [测试](#测试)
- [文档导航](#文档导航)

## 项目能力
- 剧本解析：TXT/MD/DOCX/PDF/FDX -> 结构化场次数据
- 角色提取：外貌、服装、视觉关键词、角色描述
- 场景分析：地点、时间、光线、色调、氛围
- 分镜生成：镜号、景别、运镜、动作、提示词
- 提示词优化：SCELA 检查、术语标准化、合规提示
- 一致性检查：角色/场景/光线/风格连续性
- 多格式导出：JSON/CSV/Markdown/Excel/HTML
- 视频理解：上传视频后自动反推结构化剧本（Gemini API）

## 快速开始

### 1) 环境安装
```powershell
cd c:\Users\zhuyue\Desktop\剧本skill
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pytest
```

### 2) 运行模式A（剧本 -> 分镜 -> 导出）
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

parsed = parse_script("assets/example_input.txt")
characters = extract_characters(parsed)
scenes = analyze_scenes(parsed)
storyboard = generate_storyboard(parsed, scenes, characters)
storyboard = PromptOptimizer().optimize_storyboard(storyboard, platform="seedance")
consistency = check_consistency(storyboard, characters, scenes)
paths = export_all(storyboard, characters, scenes, output_dir="out", formats=["json", "markdown", "html"])

print(paths)
print(len(consistency.get("issues", [])))
```

## 输入与输出

### 输入
- 剧本文档：`.txt` `.md` `.docx` `.pdf` `.fdx`
- 视频文件（模式D）：`.mp4` `.mov` `.avi` `.webm`（<=50MB）
- 创意短句（模式B）：一句话意图 + 时长 + 风格 + 比例

### 输出
- `storyboard`：分镜列表与元数据
- `characters`：角色设定与关键词
- `scenes`：场景设定与视觉提示
- `consistency report`：一致性问题与建议
- 导出文件：`json/csv/md/xlsx/html`

## 四种工作模式

### 模式A：剧本流水线
剧本输入 -> 解析 -> 角色提取 + 场景分析 -> 分镜生成 -> 可选优化 -> 一致性校验 -> 导出。

### 模式B：直接生成（Seedance）
一句话创意 -> 类型识别 -> SCELA 展开 -> 合规检查 -> 生成可用提示词。

### 模式C：视频拆解与重构
对标视频输入 -> 五维拆解 -> 微创新重构 -> 质检清单 + 结构化机审输出。

### 模式D：视频理解与反推
视频输入 + API Key -> 视频理解 -> ParsedScript -> 接入模式A后半段流程。

## 质量与进化机制

`evolution/` 提供生成后质量治理与自我进化能力。

### 质量评分（7维）
- scela_coverage
- consistency
- compliance
- shot_diversity
- mood_rhythm
- visual_precision
- platform_fit

### 微分差进化
- 配对比较（微小分差）
- 维度级 ELO 更新
- 偏好形成与动态权重
- 分阶段启用：`shadow -> observe -> active`

### 兼容性
- 保留原有字段：`overall_score` `scela_score` `compliance_passed` `consistency_score`
- 新增字段：`dimension_scores` `elo_ratings` `active_weights` `comparison_summary`

## 命令速查

基础命令：
- `/evolve status`
- `/evolve learn`
- `/evolve rollback [snapshot_id]`
- `/evolve memory`
- `/evolve health`
- `/evolve export`
- `/evolve log`
- `/evolve reset --confirm`

评分相关命令：
- `/evolve scores`
- `/evolve preferences`
- `/evolve compare <archive_id>`
- `/evolve scorer reset`
- `/evolve scorer calibrate`

## 目录结构
```text
.
├── scripts/                 # 主功能脚本
├── evolution/               # 自我进化与质量治理
├── tests/                   # 单元与回归测试
├── assets/                  # 模板与示例输入输出
├── references/              # 规范/词库/协议文档
├── docs/                    # 设计与安全文档
├── SKILL.md                 # 技能主规范
├── WORKFLOW.md              # 工作流文档
└── USAGE_GUIDE.md           # 使用指南
```

## 测试
```powershell
python -m pytest tests -q
```

当前基线：`201 passed`

## 文档导航
- 使用手册：[USAGE_GUIDE.md](USAGE_GUIDE.md)
- 工作流：[WORKFLOW.md](WORKFLOW.md)
- 技能规范：[SKILL.md](SKILL.md)
- 进化协议：[docs/evolution_protocol.md](docs/evolution_protocol.md)
- 威胁模型：[docs/evolution_threat_model.md](docs/evolution_threat_model.md)

