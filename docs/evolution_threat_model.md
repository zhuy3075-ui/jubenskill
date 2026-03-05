# Evolution Threat Model — 进化系统威胁模型

## 版本
v2.0.0 | 2026-03-01

## 1. 威胁矩阵

| 威胁 | 严重度 | 攻击面 | 防护措施 | 状态 |
|------|--------|--------|----------|------|
| 供应链投毒 | P0 | repair_from_github | 仓库白名单 + 版本固定 + SHA-256 校验 | ✅ 已实现 |
| 记忆注入 | P0 | memory.set_preference | schema 校验 + 大小限制 + 敏感内容检测 | ✅ 已实现 |
| PII 泄漏 | P0 | memory/log/archive/package | 统一脱敏 + 打包前扫描 + 阻断 | ✅ 已实现 |
| 快照损坏 | P1 | snapshot.rollback | 两阶段提交 + 一致性校验 + 自动回滚 | ✅ 已实现 |
| 并发写入冲突 | P1 | memory/log/snapshot | 全局文件锁 (cross-platform) | ✅ 已实现 |
| 记忆膨胀 | P1 | memory store | 上限 1000/类 + 衰减 + 压缩 | ✅ 已实现 |
| 环境误判 | P1 | env_detect | probe matrix + 优先级 + 安全降级 | ✅ 已实现 |
| 规则绕过 | P1 | rules.check_request | hard_deny 不可跳过 + 审计日志 | ✅ 已实现 |
| 敏感文件学习 | P0 | learner/memory | 文件名黑名单 + 内容扫描 + 字段白名单 | ✅ 已实现 |
| 日志篡改 | P2 | evolution.jsonl | append-only + 文件锁 | ⚠️ 无签名 |

## 2. 防护边界

### 已防护
- 仓库来源验证 (allowlist)
- 文件完整性 (SHA-256)
- PII 自动脱敏 (手机/邮箱/身份证/银行卡/密钥/路径)
- 敏感文件检测 (.env, credentials, .pem, .key, id_rsa)
- 敏感内容检测 (api_key, password, Bearer token, private key)
- 学习字段白名单 (仅业务字段可入库)
- 记忆条目 schema 校验 (类型/大小/内容)
- 记忆冲突分级处理 (高影响→用户确认, 低影响→自动衰减)
- 压缩可追溯 (保留 merged_ids + reason)
- 快照事务语义 (prepare/commit + 失败回滚)
- 回滚一致性校验 (before/after hash)
- 跨平台文件锁 (Windows msvcrt + POSIX fcntl)

### 未防护 (已知风险)
1. **日志签名**: evolution.jsonl 为 append-only 但无密码学签名，本地攻击者可篡改
2. **网络传输**: repair_from_github 使用 git clone，依赖 HTTPS 但无额外证书固定
3. **内存中数据**: 运行时内存中的数据未加密，进程转储可能泄漏
4. **文件系统权限**: 依赖 OS 文件权限，未实现应用层加密

## 3. 安全配置

### 敏感规则清单 (可配置扩展)
```python
# security.py 中可扩展的模式列表:
PII_PATTERNS          # 正则 → 替换占位符
SENSITIVE_FILE_PATTERNS  # 文件名黑名单
SENSITIVE_CONTENT_PATTERNS  # 内容黑名单
LEARNING_WHITELIST    # 允许入库的字段名
ABS_PATH_PATTERN      # 绝对路径检测
```

### 扩展方式
继承 `SecurityGuard` 类并覆盖对应列表:
```python
class CustomGuard(SecurityGuard):
    PII_PATTERNS = SecurityGuard.PII_PATTERNS + [
        (re.compile(r"your_pattern"), "[YOUR_LABEL]"),
    ]
```

## 4. 安全不变量

以下条件在任何情况下都必须成立:
1. 未经快照不执行核心变更
2. 敏感信息不写入 memory/log/archive/package
3. 供应链校验失败立即拒绝并记录审计日志
4. 高影响记忆冲突不自动覆盖
5. 回滚失败自动恢复到 pre_rollback 状态
6. evolve_data/ 目录在热更新时永不被删除
