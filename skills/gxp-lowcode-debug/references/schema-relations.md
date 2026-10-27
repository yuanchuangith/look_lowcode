# 开发库 Schema 与可信关系

仅在表、字段、备注、索引、约束或跨表关系问题时读取。本机 Schema 快照来自可访问的开发库，不代表生产结构或数据；环境与生产批量取证见 [platform-map.md](platform-map.md#生产环境数据按批取证)。

## 候选与验证

1. `search_database_schema` 按表名、字段名和备注定位，`inspect_table_schema` 读取表结构、数据库声明外键和当前可信关系。
2. 先结合任务语义、业务锚点、备注、外键、唯一键和调用上下文提出候选并解释，再回到 `inspect_table_schema` 或 `resolve_table_relation` 校验。语义不足、候选冲突、证据不完整或无法稳定输出结构化候选时，回退 `generate_candidates` 脚本解析并执行数据库验证。
3. 推断关系只有目标列唯一、类型兼容、至少 20 个不同非空来源键且全量数据 100% 匹配，才标 `data_verified`。自动选择还要求同组候选验证完整、无截断或未决项且仅一个通过；`verification_scope=explicit_target` 只证明指定目标匹配，不证明全局唯一。
4. 快照过期、Schema 指纹变化、关系歧义、验证失败或当前故障与关系冲突时，`resolve_table_relation(..., force_live=true)`。按 `live_database` 回答，不把实时结果称为快照；仍不确定则不得选择候选。

## 本机否决与恢复

- 每次使用推断关系前检查本机否决记录，不访问策略服务器。命中 `rejected` 立即停止，不重验、不重建，直到显式恢复；记录不可读时只展示 `declared_fk`，推断关系标“尚未确认”。
- 只有用户明确指出关系错误，且当前回答已有该 `relation_id`，才 `reject_table_relation`。普通质疑、待确认或查询失败不永久否决。
- 否决只在本机保存 relation ID、标准原因码和审计，不上传或跨机同步。首次只导入本机同 scope 旧缓存，不下载服务器历史。
- `restore_table_relation` 后必须重新数据验证；恢复版本使本机旧验证失效，同组竞争候选恢复也使旧唯一性失效。

通用关系验证只返回计数。具体业务样本仍走 `get_records` 的索引等值、小列集、小 limit。分别标记证据为 `数据库架构快照`、`数据验证关系`、`实时数据库验证`、`本机用户否决`、`尚未确认`。
