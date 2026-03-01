# AI视频提示词全能生成器 (script-to-video-prompts)

> 版本 3.1.3

AI视频提示词全能生成器 Claude Code Skill。支持三种模式：A）剧本流水线（剧本→分镜→提示词）；B）直接生成（一句话意图→Seedance 2.0 平台级提示词）；C）对标视频拆解与爆款重构（五维解构+微创新+差异化公式）。
触发词（口语优先）：「做视频」「拍视频」「搞个视频」「视频文案」「写提示词」「写分镜」「分镜」「视频脚本」「镜头」「帮我做视频」「我有个剧本」「剧本转视频」「拆解视频」「分析视频」「分析这个视频」「学爆款」「模仿视频」「拆片」「AI视频」「AI做视频」「AI生成视频」「文生视频」「图生视频」「视频提示词」「视频生成」「prompt」「Seedance」「seedance」「即梦」「即梦平台」「短剧」「广告视频」「视频延长」「对标拆解」「爆款分析」「短视频」

## 项目结构

```
script-to-video-prompts/
├── SKILL.md                    # Skill 定义文件（入口）
├── requirements.txt            # Python 可选依赖
├── scripts/                    # Python 自动化脚本（v2.0）
│   ├── parse_script.py         # 步骤1: 剧本解析（状态机驱动）
│   ├── character_extractor.py  # 步骤2: 角色提取（从 elements 提取特征）
│   ├── scene_analyzer.py       # 步骤3: 场景分析
│   ├── storyboard_generator.py # 步骤4: 分镜生成（元素驱动）
│   ├── prompt_optimizer.py     # 步骤4b + 模式B入口（SCELA公式 + 合规检查 + generate_seedance_prompt）
│   ├── consistency_checker.py  # 步骤5: 一致性校验（含光线检查）
│   └── export_utils.py         # 步骤6: 多格式导出（含安全防护）
├── references/                 # 规范文档（13份：8份原有 + 3份 Seedance 2.0 + 2份模式C协议）
├── assets/                     # 模板资源 + 端到端示例
├── evolution/                  # 自我进化系统（14模块）
├── evolve_data/                # 进化持久数据（记忆/快照/日志/归档）
├── docs/                       # 协议规范 + 威胁模型
└── tests/
    ├── test_regression.py      # 回归测试（45个用例）
    └── test_evolution_*.py     # 进化系统测试（116个用例）
```

## 工作流程

**模式A（剧本流水线）**：
```
剧本文件 → ①解析 → ②角色提取 ──→ ④分镜生成 → ④b提示词优化 → ⑤一致性校验 → ⑥导出
                   ↘ ③场景分析 ─↗
                  （②③可并行）
```

**模式B（直接生成）**：
```
一句话意图 → 确认时长/风格 → 匹配模板(A-R) → SCELA公式展开 → 合规检查 → 输出提示词
```

**模式C（视频拆解与爆款重构）**：
```
对标视频链接/素材 → 五维解构 → 评论区洞察 → 微创新策略菜单 → 差异化重构方案
```

| 步骤 | 脚本 | 入口函数 | 输入 | 输出 |
|------|------|---------|------|------|
| 1 解析 | parse_script.py | `parse_script(file_path)` | 文件路径 str | ParsedScript Dict（含 elements） |
| 2 角色 | character_extractor.py | `extract_characters(parsed_script)` | 步骤1输出 | Dict[str, Dict] |
| 3 场景 | scene_analyzer.py | `analyze_scenes(parsed_script)` | 步骤1输出 | List[Dict] |
| 4 分镜 | storyboard_generator.py | `generate_storyboard(parsed, scenes, chars)` | 步骤1+2+3 | Storyboard Dict |
| 4b 优化 | prompt_optimizer.py | `optimize_prompt(prompt, context)` | 提示词 str | 优化结果 Dict |
| B 直接生成 | prompt_optimizer.py | `generate_seedance_prompt(intent, duration, genre)` | 意图 str | Seedance 结果 Dict |
| 5 校验 | consistency_checker.py | `check_consistency(storyboard, chars, scenes)` | 步骤2+3+4 | 一致性报告 Dict |
| 6 导出 | export_utils.py | `export_all(storyboard, chars, scenes, dir)` | 步骤2+3+4 | 文件路径 Dict |

## v2.0 关键改进

- 双模式: 新增模式B直接生成，融合 Seedance 2.0 提示词生成能力
- SCELA公式: Subject·Camera·Effect·Light·Audio 结构化提示词（check_scela 方法）
- 合规检查: 违禁词检测（真实人名/版权IP/品牌），合规替换建议
- 18个爆款模板: 覆盖8大主题（动作/仙侠/产品/短剧/变身/舞蹈/生活/科幻）
- 解析层: 状态机替代纯正则，解决中文对白/动作误判为角色名
- 数据层: `Scene.to_dict()` 输出完整 elements，修复步骤间数据契约断裂
- 生成层: 分镜从固定模板升级为元素驱动规划器
- 安全层: HTML escape、文件名净化、CSV/Excel 公式注入防护
- 稳定性: 所有类入口自动 `_reset()`，消除跨调用状态污染
- 测试: 45 个 pytest 用例覆盖上述所有修复点（含 SCELA 中文全覆盖 + 大小写 + 合规 + 模式B入口）

## v3.1 增量改进

- 模式C: 新增“视频拆解与爆款重构”工作流
- 协议融合: 引入 `references/cjie_video_deconstruction_protocol.md` 作为完整执行模板
- 触发词扩展: 新增“对标视频拆解/爆款分析/微创新重构/差异化公式”

## v3.1.1 增量改进

- 模式C补强: 新增 `references/new_storyboard_reconstruction_architect_protocol.md` 作为分镜重构补充协议
- 执行规则补齐: 增加资产引用一致性、分阶段输出、宫格批量生成、抽卡视频变体等可执行约束

## v3.1.2 增量改进

- 新增模式C硬性自检模板：资产一致性、分阶段执行、宫格模式、抽卡变体、安全合规
- 新增“质检成果清单”固定输出格式，强制在每轮模式C任务后给出可审计结果

## v3.1.3 增量改进

- 新增模式C结构化 JSON 机审模板（C9）
- 新增 `assets/c7_quality_gate_template.json`，用于自动质检网关判定与后续流水线集成

## 开发约定

### 双语规则
- 文档、注释、用户提示：中文
- 代码标识符（类名、函数名、变量名）：英文
- AI 提示词关键词：英文（脚本中通过字典映射 `中文 → 英文`）

### 命名规范
- 脚本文件：snake_case.py
- 类名：PascalCase（如 ScriptParser, CharacterExtractor）
- 函数：snake_case（如 parse_script, extract_characters）
- 类常量：UPPER_SNAKE_CASE 字典（如 AGE_KEYWORDS, LOCATION_TYPES）

### 代码模式
每个脚本遵循统一结构：dataclass 数据模型 → 主处理类（含 `_reset()` + 关键词映射字典）→ 模块级便捷函数 → `__main__` 示例

## 格式支持

- 输入：TXT, Markdown, Word(.docx), PDF, Final Draft(.fdx)
- 输出：Markdown, JSON, CSV, Excel(.xlsx), HTML（可视化）
- 可选依赖见 `requirements.txt`：`python-docx`、`pdfplumber`、`openpyxl`

## 测试

```bash
python -m pytest tests/test_regression.py -v    # 45 个用例，pytest 标准断言
python -m pytest tests/test_evolution_*.py -v   # 116 个进化系统测试
python -m pytest tests/ -v                      # 全量 161 个测试
```

## 注意事项

1. 项目未初始化 Git，建议 `git init` 建立版本管理
2. 步骤间通过 Dict 传递数据，`Scene.to_dict()` 现在输出完整 elements
3. 提示词验证规则：单条不超过200词，必须包含 WHO/WHAT/WHERE/WHEN/HOW/QUALITY 六要素
4. 质量评分合格阈值 ≥ 0.7（满分1.0）

## 进化系统 (v2.0)

14 个模块位于 `evolution/`，持久数据位于 `evolve_data/`（热更新时保留）。

### 运维命令
`/evolve status` | `learn` | `rollback [id]` | `memory` | `health` | `export` | `log` | `reset --confirm`

### 安全策略
- 供应链: 仓库白名单 + 版本固定 + SHA-256 + dry-run + 审计日志
- 快照: 两阶段提交 + 失败自动回滚 + hash 一致性校验
- 隐私: 字段白名单 + PII 脱敏 + 敏感文件/内容检测 + 打包前扫描阻断
- 记忆: 衰减(0.95^天) + 压缩(可追溯) + 冲突分级(高影响→用户确认)
- 规则: hard_deny / soft_warn / suggest_alternative 三级反驳

### 恢复流程
1. `/evolve health` — 检查文件完整性
2. `/evolve rollback` — 列出快照，选择回滚点
3. 回滚自动创建 pre_rollback 快照，失败自动恢复

详见 `docs/evolution_protocol.md` 和 `docs/evolution_threat_model.md`
