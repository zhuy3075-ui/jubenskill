# AI视频提示词全能生成器 — 基础使用教程

> 版本 3.4.0 | 更新于 2026-03-05

---

## 大纲

```
AI视频提示词全能生成器 基础使用教程
│
├── 一、Skill 概述
│   ├── 1.1 这个 Skill 能做什么
│   ├── 1.2 四种工作模式一览
│   ├── 1.3 核心能力速查
│   └── 1.4 强制协议与门禁（必读）
│
├── 二、安装与配置
│   ├── 2.1 前置条件
│   ├── 2.2 文件夹结构
│   ├── 2.3 安装 Skill（本地部署）
│   ├── 2.4 验证安装
│   └── 2.5 单一维护源与同步策略
│
├── 三、快速上手（5 分钟跑通）
│   ├── 3.1 模式A：剧本 → 分镜 → 提示词
│   ├── 3.2 模式B：一句话 → Seedance 提示词
│   ├── 3.3 模式C：对标视频拆解
│   └── 3.4 模式D：视频理解 → 剧本
│
├── 四、触发词与模式判断
│   ├── 4.1 口语触发词
│   ├── 4.2 意图触发词
│   └── 4.3 自动模式匹配规则
│
├── 五、各模式详细使用
│   ├── 5.1 模式A 完整流程
│   ├── 5.2 模式B 完整流程
│   ├── 5.3 模式C 完整流程
│   └── 5.4 模式D 完整流程
│
├── 六、质检评分机制（v3.3 新增）
│   ├── 6.1 三层评分架构
│   ├── 6.2 七维度评分体系
│   ├── 6.3 微分差 ELO 配对比较
│   ├── 6.4 偏好自动形成
│   └── 6.5 三阶段渐进启用
│
├── 七、进化系统操作
│   ├── 7.1 /evolve 命令大全
│   ├── 7.2 评分与偏好查看
│   ├── 7.3 回滚与恢复
│   └── 7.4 数据目录说明
│
├── 八、输出格式与交付物
│   ├── 8.1 支持的导出格式
│   ├── 8.2 各模式交付物清单
│   └── 8.3 质量阈值说明
│
├── 九、测试与验收
│   ├── 9.1 运行测试
│   └── 9.2 验收清单
│
└── 十、常见问题与排错
    ├── 10.1 依赖安装问题
    ├── 10.2 API 问题（模式D）
    └── 10.3 评分系统问题
```

---

## 一、Skill 概述

### 1.1 这个 Skill 能做什么

把你的创意、剧本、视频素材，转化为可以直接喂给 AI 视频生成平台的**结构化提示词**。

你只需要说人话（比如"帮我做个10秒仙侠战斗视频"），Skill 自动完成：
- 剧本解析 → 角色提取 → 场景分析 → 分镜生成 → 提示词优化 → 一致性校验 → 多格式导出

### 1.2 四种工作模式一览

| 模式 | 输入 | 输出 | 适用场景 |
|------|------|------|----------|
| **A 剧本流水线** | 剧本文档（TXT/MD/DOCX/PDF/FDX） | 完整分镜 + 提示词 + 角色/场景设定 | 有完整剧本，要转成 AI 视频 |
| **B 直接生成** | 一句话创意意图 | Seedance 平台级提示词 | 快速出片，无需写剧本 |
| **C 视频拆解** | 对标视频链接/素材 | 五维分析 + 微创新重构方案 | 学习爆款、差异化二创 |
| **D 视频理解** | 视频文件 + API Key | 反推剧本 + 分镜 + 提示词 | 从视频反推结构化内容 |

### 1.3 核心能力速查

- **SCELA 公式**：Subject·Camera·Effect·Light·Audio 五要素结构化提示词
- **合规检查**：自动检测违禁词（真实人名/版权IP/品牌）
- **一致性校验**：角色外貌、场景光线、镜头风格连续性
- **18 个爆款模板**：覆盖动作/仙侠/产品/短剧/变身/舞蹈/生活/科幻
- **微分差评分**：ELO 配对比较 + 偏好自动形成（v3.3 新增）
- **多平台适配**：Seedance/即梦、Runway、Kling、Pika、Sora

### 1.4 强制协议与门禁（必读）

当任务命中“分镜重构强制协议”时，以下规则具有最高优先级：
- **强制原文锁定**：`sucai/tielv.txt`（铁律）+ `sucai/shuchu.txt`（提示词输出格式约束）必须原模原样执行，禁止改写/删减/重排。
- **工作流门禁**：先过启动引导门禁（A/S/B 分支），再走阶段门禁（阶段1→阶段2→阶段3），每阶段受质量门禁拦截。
- **AskUserQuestion 自动唤起（强制保留）**：参数缺失、阶段切换、批次循环、质量拦截分歧时必须自动提问确认。
- **语言与输出约束**：命中强制协议时，以全中文输出、防泄漏、格式锁定为准。

建议先阅读：`sucai/必须遵守规定提取整理与执行方案.md`。

---

## 二、安装与配置

### 2.1 前置条件

- Claude Code CLI 已安装
- Python 3.10+（用于脚本层，可选）
- 网络连接（模式D 需调用 Gemini API）

### 2.2 文件夹结构

```
script-to-video-prompts/
├── SKILL.md                    # Skill 定义文件（入口）
├── USAGE_GUIDE.md              # 本教程
├── WORKFLOW.md                 # 工作流总览
├── requirements.txt            # Python 可选依赖
├── scripts/                    # Python 自动化脚本
│   ├── parse_script.py         # 剧本解析
│   ├── video_analyzer.py       # 视频理解（Gemini API）
│   ├── character_extractor.py  # 角色提取
│   ├── scene_analyzer.py       # 场景分析
│   ├── storyboard_generator.py # 分镜生成
│   ├── prompt_optimizer.py     # 提示词优化 + 模式B入口
│   ├── consistency_checker.py  # 一致性校验
│   └── export_utils.py         # 多格式导出
├── evolution/                  # 自我进化系统（17模块）
│   ├── core.py                 # 中央调度器
│   ├── scorer.py               # 微分差评分引擎（v3.3 新增）
│   ├── dimensions.py           # 7维度子评分器（v3.3 新增）
│   ├── preference_former.py    # 偏好形成器（v3.3 新增）
│   ├── quality.py              # 质量检查门
│   ├── memory.py               # 持久记忆存储
│   ├── learner.py              # 模式学习器
│   ├── rules.py                # 三级规则引擎
│   ├── security.py             # 安全守卫
│   ├── snapshot.py             # 快照管理器
│   ├── triggers.py             # /evolve 命令路由
│   └── ...                     # 其他辅助模块
├── evolve_data/                # 进化持久数据
│   ├── memory/                 # 偏好/纠错/模式
│   ├── scores/                 # 评分历史（v3.3 新增）
│   ├── archive/                # 高质量归档
│   ├── snapshots/              # 版本快照
│   └── logs/                   # 审计日志
├── references/                 # 13份规范文档
├── assets/                     # 模板资源 + 示例
├── tests/                      # 测试用例（190+）
└── docs/                       # 协议规范
```

### 2.3 安装 Skill（本地部署）

**方式一：已在 Claude Code 中配置（推荐）**

Skill 文件已部署到 `~/.claude/skills/script-to-video-prompts/`，Claude Code 会自动识别。

**方式二：手动部署**

```bash
# 1. 确保 skill 目录存在
mkdir -p ~/.claude/skills/script-to-video-prompts

# 2. 复制项目文件到 skill 目录
cp -r /path/to/your/project/* ~/.claude/skills/script-to-video-prompts/

# 3. 安装 Python 依赖（可选，用于脚本层）
cd ~/.claude/skills/script-to-video-prompts
pip install -r requirements.txt
```

### 2.4 验证安装

在 Claude Code 中输入以下任意触发词，验证 Skill 是否被正确加载：

```
你：帮我做个视频
→ 应触发模式选择提示

你：/evolve status
→ 应显示进化系统状态面板
```

### 2.5 单一维护源与同步策略

- **唯一维护源（Source of Truth）**：`C:\Users\zhuyue\Desktop\剧本skill`（本仓库源码）。
- **运行时镜像目录**：`C:\Users\zhuyue\.codex\skills\script-to-video-prompts`、`C:\Users\zhuyue\.agents\skills\script-to-video-prompts`。
- **推荐流程**：先改源码并提交，再同步到运行时目录；不要只改运行时副本。
- **本次关键落地**：`SKILL.md` 已加入强制执行段、全局门禁、AskUserQuestion 自动唤起强化策略。

---

## 三、快速上手（5 分钟跑通）

### 3.1 模式A：剧本 → 分镜 → 提示词

```
你：我有个剧本，帮我转成视频提示词
→ 上传剧本文件（.txt / .md / .docx / .pdf）
→ Skill 自动执行 6 步流水线
→ 输出完整分镜表 + 角色设定 + 场景设定 + 提示词
```

### 3.2 模式B：一句话 → Seedance 提示词

```
你：帮我生成一个10秒仙侠战斗视频的提示词
→ Skill 确认时长/风格
→ 匹配最佳模板 → SCELA 展开 → 合规检查
→ 输出可直接用于 Seedance/即梦 的提示词
```

### 3.3 模式C：对标视频拆解

```
你：帮我拆解这个爆款视频，学习它的套路
→ 提供视频链接或素材描述
→ Skill 输出五维分析（时间/物体/人物/事件/空间）
→ 微创新策略菜单 + 差异化重构方案
```

### 3.4 模式D：视频理解 → 剧本

```
你：帮我理解这个视频，转成剧本
→ 上传视频文件（.mp4 / .mov / .avi / .webm，≤50MB）
→ 提供 yunwu.ai API Key
→ Gemini 2.5 Pro 自动理解视频内容
→ 生成结构化剧本 → 接入模式A后半段流水线
```

---

## 四、触发词与模式判断

### 4.1 口语触发词

直接说人话就能触发：

| 说法 | 触发模式 |
|------|----------|
| "做视频"、"拍视频"、"搞个视频" | 进入模式选择 |
| "写提示词"、"写分镜"、"视频文案" | 模式A 或 B |
| "剧本转视频"、"我有个剧本" | 模式A |
| "Seedance"、"即梦" | 模式B |
| "拆解视频"、"学爆款"、"拆片" | 模式C |
| "理解视频"、"视频转剧本" | 模式D |

### 4.2 意图触发词

| 说法 | 触发模式 |
|------|----------|
| "帮我做视频" | 进入模式选择 |
| "分析视频"、"分析这个视频" | 模式C 或 D |
| "模仿视频"、"对标拆解" | 模式C |
| "AI视频"、"文生视频"、"视频生成" | 模式B |
| "短剧"、"广告视频"、"短视频" | 按上下文判断 |

### 4.3 自动模式匹配规则

| 用户输入特征 | 自动匹配 |
|-------------|---------|
| 上传文档文件 | 模式A |
| 一句话描述创意 + 无文件 | 模式B |
| 提到"拆解"、"爆款"、"对标" | 模式C |
| 上传视频文件 + API Key | 模式D |
| 无法判断 | 主动询问用户 |
| 命中分支B但参数不全 | **自动唤起 AskUserQuestion，一次性补齐必填参数** |
| 第一阶段结束 / 第二阶段每批结束 | **自动唤起 AskUserQuestion，确认是否继续** |

---

## 五、各模式详细使用

### 5.1 模式A 完整流程

**输入要求**：
- 剧本文档（支持 .txt / .md / .docx / .pdf / .fdx）
- 可选：风格参考图、角色参考图、目标平台

**执行步骤**：
```
①解析剧本 → ②提取角色 ──→ ④生成分镜 → ④b优化提示词 → ⑤一致性校验 → ⑥导出
              ↘ ③分析场景 ─↗
              （②③可并行）
```

**输出交付物**：
- 分镜数据（镜号、景别、运镜、提示词、时长）
- 角色设定卡（外貌、服装、关键词）
- 场景设定（地点、时间、光线、氛围）
- 一致性报告（问题项 + 修正建议）
- 多格式文件（JSON / CSV / Markdown / Excel / HTML）

**代码调用方式**（高级用户）：
```python
from pathlib import Path
import sys, json
sys.path.insert(0, str(Path("scripts").resolve()))

from parse_script import parse_script
from character_extractor import extract_characters
from scene_analyzer import analyze_scenes
from storyboard_generator import generate_storyboard
from prompt_optimizer import PromptOptimizer
from consistency_checker import check_consistency
from export_utils import export_all

parsed = parse_script("your_script.txt")
characters = extract_characters(parsed)
scenes = analyze_scenes(parsed)
storyboard = generate_storyboard(parsed, scenes, characters)
storyboard = PromptOptimizer().optimize_storyboard(storyboard, platform="seedance")
consistency = check_consistency(storyboard, characters, scenes)
paths = export_all(storyboard, characters, scenes, "out", ["json", "markdown", "html"])
```

### 5.2 模式B 完整流程

**输入要求**：
- `intent`：一句话创意描述
- `duration`：视频时长（4~15秒）
- `genre`：风格类型（动作/仙侠/产品/短剧/科幻等）
- `aspect_ratio`：画面比例（16:9 或 9:16）

**输出**：
- 优化后的 Seedance 提示词
- SCELA 五要素覆盖分析
- 合规检查结果
- 命中的模板编号

**代码调用方式**：
```python
from prompt_optimizer import generate_seedance_prompt

result = generate_seedance_prompt(
    intent="10秒仙侠战斗，女侠雨夜屋顶追击",
    duration=10, genre="仙侠", aspect_ratio="16:9"
)
print(result["optimization"]["optimized"])
```

### 5.3 模式C 完整流程

**输入要求**：
- 对标视频链接或视频素材
- 可选：播放量、评论区截图、重构目标

**固定四阶段输出**：
1. **阶段一**：素材检查 + 目标确认
2. **阶段二**：五维深度拆解（时间/物体/人物/事件/空间）+ 评论洞察 + 策略菜单
3. **阶段三**：微创新重构（保留可复用资产 + 定向改写）
4. **阶段四**：融合方案 + 迭代建议

**每轮必须交付**：
- 可读版质检清单（C8 格式）
- 结构化质检 JSON（C9 格式，模板见 `assets/c7_quality_gate_template.json`）

### 5.4 模式D 完整流程

**输入要求**：
- 视频文件（.mp4 / .mov / .avi / .webm，≤50MB）
- yunwu.ai API Key

**执行链路**：
```
视频文件 → Gemini 2.5 Pro 理解 → 结构化剧本 → 接入模式A步骤②~⑥
```

**代码调用方式**：
```python
from video_analyzer import analyze_video_full

result = analyze_video_full("video.mp4", api_key="YOUR_KEY")
parsed = result["parsed_script"]  # 可直接传入模式A后续步骤
print("质量评分:", result["analysis_quality"])
print("警告:", result["warnings"])
```

---

## 六、质检评分机制（v3.3 新增）

### 6.1 三层评分架构

```
┌──────────────────────────────────────────┐
│  第一层：绝对评分                          │
│  7 个维度独立打分 → 精确到 0.001           │
│  每个维度有独立的评分算法                    │
└──────────────────┬───────────────────────┘
                   │
┌──────────────────▼───────────────────────┐
│  第二层：配对比较                          │
│  当前输出 vs 历史最优（同类型/同风格）       │
│  7 维度分别对比 → 微分差 (±0.01~0.05)      │
│  ELO 等级分更新（K=16自动/K=32用户反馈）    │
└──────────────────┬───────────────────────┘
                   │
┌──────────────────▼───────────────────────┐
│  第三层：偏好形成                          │
│  统计各维度胜率 → 发现强弱项               │
│  动态调整维度权重（弱项权重微增）            │
│  偏好写入记忆 → 影响下次生成               │
└──────────────────────────────────────────┘
```

### 6.2 七维度评分体系

| 维度 | 说明 | 评分依据 |
|------|------|----------|
| `scela_coverage` | SCELA 五要素覆盖度 | S/C/E/L/A 各元素是否出现在提示词中 |
| `consistency` | 一致性 | 角色引用命中率 + 场景连续性 + 场景参考可用性 |
| `compliance` | 合规性 | 违禁词检测（真实人名/版权IP/品牌） |
| `shot_diversity` | 镜头语言丰富度 | 景别种类数 + 运镜方式种类数 |
| `mood_rhythm` | 情绪节奏匹配度 | 情绪多样性 + 转场节奏（偏好适度变化） |
| `visual_precision` | 视觉精确度 | 提示词细节密度 + 镜头信息完整度 |
| `platform_fit` | 平台适配度 | 针对目标平台的格式/关键词匹配 |

### 6.3 微分差 ELO 配对比较

每次生成后，系统自动：
1. 从历史记录中匹配同类型对手（按风格、平台、时长匹配）
2. 逐维度对比分数，产生微分差（±0.01~0.05）
3. 差值 < 0.02 判定平局，≥ 0.02 判定胜负
4. 按 ELO 公式更新等级分（初始 1500，范围 1200~1800）

```
示例：
  scela_coverage:    新 0.85 vs 旧 0.82 → 新胜 (+0.03) → ELO 1500→1504
  visual_precision:  新 0.68 vs 旧 0.75 → 旧胜 (-0.05) → ELO 1500→1492
  mood_rhythm:       新 0.80 vs 旧 0.81 → 平局 (0.01)  → ELO 不变
```

**K 值（分数变动幅度）**：
| 来源 | K 值 | 说明 |
|------|------|------|
| 自动对比 | 16 | 常规生成后的自动比较 |
| 用户反馈 | 32 | 用户修正触发的比较（影响力翻倍） |
| 手动比较 | 12 | `/evolve compare` 命令触发 |

### 6.4 偏好自动形成

系统通过累积微分差，自动发现你的强弱项：

```
胜率 > 55% → 该维度标记为 "prefer_high"（强项）
胜率 < 45% → 该维度标记为 "prefer_low"（弱项，权重微增以强化关注）
胜率 45~55% → "neutral"（均衡）
```

**权重动态调整公式**：
```
new_weight = base_weight + adjustment × confidence × 0.98^天数

其中：
- base_weight = 1/7 ≈ 0.143（七维度均分）
- adjustment = (win_rate - 0.5) × 0.2，范围 [-0.1, +0.1]
- confidence = min(比较次数 / 20, 1.0)
- 权重硬限制：[0.08, 0.22]（不会归零或过大）
```

偏好形成后自动写入记忆系统，在下次生成前注入上下文。

### 6.5 三阶段渐进启用

| 阶段 | 触发条件 | 行为 |
|------|----------|------|
| **Shadow（影子）** | 前 10 次生成 | 只记录绝对评分，不做配对比较 |
| **Observe（观察）** | 第 11~30 次 | 开始配对比较 + ELO 更新，但不调整权重 |
| **Active（激活）** | 第 31 次起 | 比较 + ELO + 偏好形成 + 权重动态调整 |

---

## 七、进化系统操作

### 7.1 /evolve 命令大全

| 命令 | 说明 |
|------|------|
| `/evolve status` | 显示进化系统状态（版本、环境、记忆条目、归档数） |
| `/evolve scores` | 查看 7 维度 ELO 等级分与当前阶段 |
| `/evolve preferences` | 查看已形成的进化偏好及强度 |
| `/evolve compare <id>` | 与指定归档手动配对比较 |
| `/evolve scorer reset` | 重置评分历史（保留普通记忆） |
| `/evolve scorer calibrate` | 用全部比较记录重新校准 ELO |
| `/evolve learn` | 强制从最近归档学习模式 |
| `/evolve memory` | 查看偏好/纠错/模式存储 |
| `/evolve health` | 运行文件完整性检查 |
| `/evolve rollback [id]` | 列出快照或回滚到指定版本 |
| `/evolve export` | 一键打包分发 |
| `/evolve log [n]` | 查看最近 n 条进化日志 |
| `/evolve reset --confirm` | 清除所有进化数据（需确认） |
| `/evolve help` | 显示命令帮助 |

### 7.2 评分与偏好查看

```
你：/evolve scores

→ 🏁 微分差评分状态
  phase: observe
  generation_count: 15
  comparisons_count: 35

  ELO:
    compliance: 1508.0
    consistency: 1495.2
    mood_rhythm: 1501.7
    platform_fit: 1512.3
    scela_coverage: 1498.6
    shot_diversity: 1504.1
    visual_precision: 1489.4
```

```
你：/evolve preferences

→ 🧠 进化偏好：
  evolved.pref.visual_precision: {'direction': 'prefer_low', 'strength': 0.3, ...}
  evolved.weight.visual_precision: 0.158
  → 说明：视觉精确度偏弱，系统已微增其权重以加强关注
```

### 7.3 回滚与恢复

```
1. /evolve health        ← 先检查文件完整性
2. /evolve rollback      ← 列出可用快照
3. /evolve rollback <id> ← 回滚到指定快照
   → 回滚前自动创建 pre_rollback 快照，失败自动恢复
```

### 7.4 数据目录说明

```
evolve_data/
├── memory/
│   ├── preferences.json    # 用户偏好 + 进化偏好
│   ├── corrections.json    # 纠错记录
│   └── patterns.json       # 学习到的提示词模式
├── scores/                 # v3.3 新增
│   ├── state.json          # 评分器状态（阶段、计数）
│   ├── elo_ratings.json    # 7 维度 ELO 等级分
│   ├── records.jsonl       # 每次生成的维度评分记录
│   └── comparisons.jsonl   # 配对比较记录
├── archive/                # 高质量输出归档（评分 ≥ 0.85）
├── snapshots/              # 版本快照（含 SHA-256 校验）
└── logs/
    └── evolution.jsonl     # 审计日志
```

---

## 八、输出格式与交付物

### 8.1 支持的导出格式

| 格式 | 用途 | 文件 |
|------|------|------|
| JSON | 程序对接、二次开发 | `storyboard.json` |
| Markdown | 人工阅读、团队协作 | `storyboard.md` |
| CSV | 表格化管理 | `storyboard.csv` |
| Excel | 项目管理、客户交付 | `storyboard.xlsx` |
| HTML | 可视化展示 | `storyboard.html` |

### 8.2 各模式交付物清单

**模式A**：分镜表 + 角色卡 + 场景设定 + 一致性报告 + 导出文件
**模式B**：优化提示词 + SCELA 分析 + 合规结果 + 匹配模板
**模式C**：五维分析 + 策略菜单 + 重构方案 + 质检清单(C8) + 质检JSON(C9)
**模式D**：反推剧本 + 角色提示 + 视频元数据 + 质量评分 → 接入模式A输出

### 8.3 质量阈值说明

| 阈值 | 值 | 含义 |
|------|-----|------|
| 及格线 | ≥ 0.7 | 生成通过，可交付 |
| 归档线 | ≥ 0.85 | 高质量，自动归档为参考案例 |
| 不及格 | < 0.7 | 自动重试（最多 3 次），取最高分 |

---

## 九、测试与验收

### 9.1 运行测试

```bash
# 全量测试（190+ 用例）
python -m pytest tests/ -v

# 核心回归（45 用例）
python -m pytest tests/test_regression.py -v

# 视频分析（29 用例）
python -m pytest tests/test_video_analyzer.py -v

# 进化系统（116 用例）
python -m pytest tests/test_evolution_*.py -v
```

### 9.2 验收清单

- [ ] 剧本解析结果含 `scenes[*].elements`
- [ ] 分镜镜头数量 > 0
- [ ] 提示词通过 SCELA 检查（5/5 要素）
- [ ] 合规警告已人工确认
- [ ] 一致性报告已人工确认
- [ ] 导出文件成功生成（至少 JSON + Markdown）
- [ ] `/evolve status` 正常响应
- [ ] `/evolve scores` 显示 7 维度 ELO

---

## 十、常见问题与排错

### 10.1 依赖安装问题

| 问题 | 解决 |
|------|------|
| 解析 `.docx` 失败 | `pip install python-docx` |
| 解析 `.pdf` 失败 | `pip install pdfplumber` |
| 导出 Excel 失败 | `pip install openpyxl` |

### 10.2 API 问题（模式D）

| 问题 | 解决 |
|------|------|
| API Key 错误 | 确认 Key 未过期，调用地址为 `yunwu.ai` |
| 文件过大 | 压缩视频到 50MB 以下 |
| 超时 | 视频超过 20MB 时处理较慢，请耐心等待 |

### 10.3 评分系统问题

| 问题 | 解决 |
|------|------|
| ELO 不更新 | 前 10 次为 Shadow 阶段，只记录不比较 |
| 偏好未形成 | 需至少 10 次同维度比较才形成偏好 |
| 评分异常 | `/evolve scorer calibrate` 重新校准 |
| 想重新开始 | `/evolve scorer reset` 重置评分历史 |

---

## 关联文档

- [SKILL.md](SKILL.md) — 完整技术规范
- [WORKFLOW.md](WORKFLOW.md) — 工作流总览
- [sucai/必须遵守规定提取整理与执行方案.md](sucai/必须遵守规定提取整理与执行方案.md) — 强制执行总方案
- [sucai/tielv.txt](sucai/tielv.txt) — 铁律（原文锁定）
- [sucai/shuchu.txt](sucai/shuchu.txt) — 输出格式约束（原文锁定）
- [sucai/zhiliang.txt](sucai/zhiliang.txt) — 质量自查协议
- [sucai/qidong.txt](sucai/qidong.txt) — 启动与交互逻辑
- [references/seedance_compliance.md](references/seedance_compliance.md) — 合规清单
- [references/prompt_patterns.md](references/prompt_patterns.md) — 提示词模板
- [docs/evolution_protocol.md](docs/evolution_protocol.md) — 进化系统协议
