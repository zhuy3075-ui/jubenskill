# 质检评分机制：代码目录级 TODO 清单

> 目标：实现“微小分差 -> ELO -> 偏好形成 -> 动态权重”的完整闭环，并保持向后兼容。

## `evolution/`
- [x] `models.py`
  - [x] 扩展 `QualityReport`：`dimension_scores`、`elo_ratings`、`active_weights`、`comparison_summary`
  - [x] 新增模型：`ScoreDimension`、`PairComparison`、`EvolvedPreference`
- [x] `dimensions.py`（新建）
  - [x] 实现7维绝对评分器
  - [x] 提供统一 `score_all(...)`
- [x] `scorer.py`（新建）
  - [x] generation 记录持久化（records）
  - [x] 配对比较（微分差、平局阈值、margin裁剪）
  - [x] ELO更新与状态机（shadow/observe/active）
  - [x] 命令能力：`reset`、`calibrate`、`compare_with_archive_id`
- [x] `preference_former.py`（新建）
  - [x] 从比较记录提炼偏好
  - [x] 生成动态权重（含裁剪与归一化）
- [x] `quality.py`
  - [x] 接入7维评分
  - [x] 保留旧字段兼容
  - [x] 支持外部传入动态权重
- [x] `core.py`
  - [x] 初始化 scorer / preference former
  - [x] `post_process` 接入比较学习闭环
  - [x] 写回 `evolved.*` 偏好
  - [x] `reset` 清理 `evolve_data/scores/`
  - [x] 新增命令处理函数：scores/preferences/compare/scorer子命令
- [x] `triggers.py`
  - [x] 注册命令：`scores`、`preferences`、`compare`、`scorer`
  - [x] 路由 scorer 子命令 `reset|calibrate`

## `evolve_data/`
- [x] 新增评分数据目录（运行时自动创建）
  - [x] `scores/state.json`
  - [x] `scores/elo_ratings.json`
  - [x] `scores/records.jsonl`
  - [x] `scores/comparisons.jsonl`

## `tests/`
- [x] `test_scorer.py`（新建）
  - [x] phase切换
  - [x] margin/tie规则
  - [x] ELO更新方向
  - [x] reset/calibrate
- [x] `test_preference_former.py`（新建）
  - [x] 偏好形成阈值
  - [x] 方向判定
  - [x] 权重归一化与边界
- [x] `test_triggers_scorer.py`（新建）
  - [x] 新命令路由可达
  - [x] scorer子命令行为
- [x] `test_quality_7d.py`（新建）
  - [x] 7维评分输出
  - [x] 旧字段兼容

## 文档同步
- [x] `SKILL.md` 新增评分命令说明
- [x] `CLAUDE.md` 新增命令说明与测试计数更新
