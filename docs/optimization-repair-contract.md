# 优化修复：证据与协议契约

## 兼容边界

MCP 工具名称、参数及 HTTP 工具集合保持不变。字段增量升级，不上传源码、Schema 或业务值。源码索引版本为 3；关系策略 JSON 文件结构仍为 1，线上协议增加 protocol_version=2。

## 源码索引 v3

- Git 状态使用 NUL 分隔原始字节；修改文件使用内容摘要。指纹覆盖 selected root、commit、版本、状态、重命名前后路径和内容。
- Git 子进程隔离标准输入，避免继承 MCP 输入管道；每条命令设置 10 秒超时，超时转换为 GIT_METADATA_TIMEOUT，受影响层按新鲜度门禁降级。
- 每个 layer 有 index_version；manifest 包含 generation。缺失、歧义、失败或旧版本 layer 的索引不用于精确证据。
- 构建前后校验指纹；读取代次变化最多重试一次。部分健康结果使用 status=partial，跨层 contract_status=unresolved。
- 使用共享词法边界保留行号；普通路由字符串只写 route-candidates。请求源自实际调用并关联函数作用域，包装器不确定性仍单独保留。
- 后端符号以 namespace/type/member/signature 为身份；target_ids 由接收类型、继承/接口及参数约束产生。类别包括 business、data_access、infrastructure、unresolved。未确认目标不递归。
- 解析不闭合的文件记录 parse_failures 并跳过；metadata-only 索引不保存源码正文。

## 二轮优化增量契约

- 前端 URL 的复合赋值、自增减、解构写入及闭包写入参与失效判断；作用域遮蔽隔离同名变量。确定的查询分隔符拼接保留路径证据，query_dynamic 与 path_confidence 分开，最终请求体继续保留包装器未决。
- 完整 symbol_id 优先匹配，命名空间、参数签名及 System 基本类型别名参与入口消歧；指定身份未命中不退回其它命名空间。短名歧义只列候选。
- response_budget 对结构化 JSON（UTF-8、indent=2，不含 MCP 外层封装）执行 64 KiB 上限。裁剪不修改输入，记录省略原因并将完整性设为 false；源码缺失等提前返回也经过相同门禁。
- 索引 v3 指纹按 layer 筛选源码和配置依赖，重命名前后路径都参与相关性判定。Git dirty 列表仍可见，无关产物不读内容、不触发重建。扫描与实时过滤证据共用排除目录。
- 同长度/同 mtime 重复编辑保障针对 Git 已列为 dirty 的相关文件。若外部工具将原本 clean 文件内容改写后又完全还原 Git 依赖的 stat 信息，Git 可能仍报告 clean；本轮未引入每次查询全仓内容审计，需另行设计强校验模式。

## 关系策略协议 v2

GET scope 保留 scope_id、revision、rejections，新增 protocol_version=2 与 restore_revisions（opaque relation ID 到最后恢复版本的映射）。ETag 格式为 policy-v2-REVISION。

真正的 rejected→restored 转换推进 scope revision，并保存 last_restore_revision；重复恢复幂等。重新否决不删除恢复版本。旧 restored 决策缺少恢复版本时，以迁移时的 scope revision 保守补齐并在锁内原子持久化，审计与否决均保留。

客户端保存完整 ETag 和协议元数据。PUT/DELETE 后先让本地 ETag 失效，再完整同步，避免遗漏其它机器的同期变更。旧缓存无 ETag 时完整获取；无完整缓存的 304 和缺失恢复版本的 v2 响应视为策略故障。

## 数据验证与唯一性

- 每组候选保存 candidate_count、candidate_truncated、每项 status 和 group_status。超时、异常、未完成和截断均不等于排除候选。
- 发布自动关系需要同组完整、恰有一项通过；显式目标实时验证使用 verification_scope=explicit_target，仅证明该目标匹配。
- 验证记录保存 policy_revision_at_validation。完成后重新同步策略，验证期间被否决或恢复的结果作废。
- 缓存记录保存 candidate_group_relations；目标关系或同组竞争候选恢复后，旧唯一性验证失效。其它关系的恢复不影响该缓存。
- 缺少验证版本的旧关系按需重验，表结构缓存继续复用。连接旧协议服务时要求 scope revision 一致；策略故障时不使用推断关系。

## 发布和回退

先备份服务代码及策略 JSON，再原子替换兼容策略模块并重启；不恢复旧策略文件覆盖新的业务决定。通过健康、协议版本、ETag、持久化权限及工具边界检查后，执行 AI-SETUP.md 指定的安装器升级本地插件。源码索引按需重建，不刷新无关 CPM 或发起开发库全量压测。

回退仅回退代码，保留最新策略 JSON、恢复版本与审计。新客户端连接旧服务时采用 scope revision 保守规则；继续使用旧客户端的机器尚未获得跨机器恢复修复，应一并升级。

## 回归与性能

重点测试位于 test_repair_regressions、test_repair_policy_contracts、test_source_lexical_contracts、test_source_freshness_contracts。旧 review-probes 保留观测输出，正式验收以 unittest 期望正确行为的断言为准。

scripts/benchmark_source_repair.py 在临时索引目录运行五次强制构建及五次黄金查询，读取真实源码但不修改业务仓库或已安装索引。耗时、载荷、误报及黄金链结果写入指定 JSON 文件；构建和热查询分别比较，不把热查询收益当作完整重建收益。
