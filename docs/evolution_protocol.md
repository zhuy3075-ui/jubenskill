# Evolution Protocol — 进化系统协议规范

## 版本
v2.0.0 | 2026-03-01

## 1. 快照协议

### 创建快照
- 触发时机: pre_evolution | pre_update | pre_rollback | pre_reset | manual
- 两阶段提交: PREPARE(复制文件到 staging) → COMMIT(原子重命名)
- PREPARE 失败: 清理 staging 目录，记录审计日志
- 最大保留: 20 个快照，超出按时间淘汰最旧的

### 回滚协议
1. 创建 pre_rollback 快照（保护当前状态）
2. 从目标快照恢复文件
3. 一致性校验（SHA-256 hash 逐文件比对）
4. 校验失败 → 自动恢复到 pre_rollback 快照
5. 写入审计日志: snapshot_id, before_hash, after_hash, operator, reason

### 快照内容
- 包含: scripts/, evolution/, references/, assets/, SKILL.md, requirements.txt
- 排除: evolve_data/, __pycache__/, .git/

## 2. 供应链更新协议 (P0-A)

### 安全检查链
1. 仓库白名单校验 (owner/repo)
2. 版本引用校验 (tag/commit pin)
3. 完整性清单校验 (manifest.json → SHA-256)
4. 预更新快照
5. 文件替换
6. 健康检查 (integrity check)
7. 校验失败 → 拒绝 + 回滚 + 审计日志

### dry-run 模式
- 执行步骤 1-3，不执行 4-6
- 返回: 将要执行的操作列表

## 3. 记忆协议

### 写入规则
- 所有写入经过 SecurityGuard.validate_memory_entry() 校验
- 仅白名单字段可入库 (LEARNING_WHITELIST)
- PII 自动脱敏后存储
- 原子写入 (write → .tmp → os.replace)

### 衰减算法
- decay_score = base × 0.95^天数
- 低于 0.1 的条目候选删除
- 每次 post_process 触发衰减检查

### 冲突解决
- 高影响冲突 (confidence > 0.8): 标记为 user_required，不自动覆盖
- 低影响冲突: 保留 confidence 最高 + access_count 最多的条目
- 压缩保留可追溯摘要 (merged_ids, reason, timestamp)

## 4. 日志字段规范

### evolution.jsonl 格式
```json
{
  "timestamp": "ISO 8601 UTC",
  "event_type": "learn|correct|archive|rollback|decay|check|security|error|...",
  "details": {},
  "before_state": null,
  "after_state": null,
  "operator": "system|user"
}
```

### event_type 枚举
| 类型 | 含义 |
|------|------|
| engine_start | 引擎启动 |
| pre_process | 生成前处理 |
| post_process | 生成后处理 |
| quality_check | 质量检查 |
| quality_attempt | 自动重试 |
| patterns_extracted | 模式提取 |
| reflection | 纠错反思 |
| preference_set | 偏好设置 |
| correction_added | 纠错记录 |
| pattern_added | 模式添加 |
| archive_created | 归档创建 |
| archive_blocked | 归档被阻止(敏感内容) |
| memory_rejected | 记忆写入被拒 |
| decay | 记忆衰减 |
| compress | 记忆压缩 |
| conflict_resolve | 冲突解决 |
| eviction | 条目淘汰 |
| maintenance | 维护运行 |
| snapshot_create | 快照创建 |
| snapshot_error | 快照错误 |
| rollback | 回滚执行 |
| rollback_failed | 回滚失败 |
| rollback_error | 回滚异常 |
| integrity_check | 完整性检查 |
| manifest_verify | 清单校验 |
| repair_success | 修复成功 |
| repair_rejected | 修复被拒 |
| repair_dry_run | 修复预演 |
| rule_check | 规则检查 |
| rules_loaded | 规则加载 |
| package_created | 打包完成 |
| package_blocked | 打包被阻止 |
| heartbeat_failure | 心跳检查失败 |
| reset | 系统重置 |

## 5. 心跳协议 (P1-D)

### 被动调度
- 每次调用检查 last_checked_at
- 超过 72h → 执行健康检查
- 失败退避: 2^consecutive_failures × 60 秒
- 最大退避: 3600 秒 (1小时)

### 外部调度适配
- 宿主支持 cron: 设置 `0 0 */3 * *` 调用 `/evolve health`
- 宿主支持 webhook: POST /evolve/health
