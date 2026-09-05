# 修复后第二轮优化复核

> 日期：2026-09-05。方式：当前实现审阅、隔离临时探针、真实源码只读对照。
> 本轮只补充复核记录，没有修改插件实现、安装配置、远程策略或业务仓库。

## 结论

四项改进已完成实现与回归：URL 写入和响应预算两个 P1 已修复，完整符号入口及脏仓库依赖面两个 P2 已修复。上一轮测试与黄金链继续保留，本轮新增输入和性能矩阵也已纳入回归。

## P1：覆盖所有 URL 写入形式，并拆开路径与查询不确定性

- 位置：mcp/gxp_core/source_frontend.py 的 URL 写入收集与 resolve；mcp/gxp_core/source_lex.py 的 WORDS。
- 修复后：复合赋值、前后置自增减、解构写入和作用域遮蔽纳入失效判断；查询追加区分确定路径与动态查询，返回 `query_status=unresolved`。
- 根因：当前收集普通 `=` 和以“前一个 token”为变量名的 ++/--；词法器未将 += 等复合写入作为完整操作符，前置自增又取错变量位置。
- 真实例子：ConfigExport/preview/web/service.ts:23 的条件 validate 查询拼接未反映在下一行请求的 dynamic 状态中。此例路径本身稳定，丢失的是查询不确定性；任意 suffix 的隔离例子还可能改变路径。
- 验收：`tests/test_followup_contracts.py` 覆盖未知写入、查询追加、遮蔽、闭包、参数和解构边界；真实 ConfigExport 查询拼接保留路径并标记查询未决。
- 验收：相关变异输入不再输出旧 URL 的确定结果；注释和不同函数不串归属；黄金调用者与 wrapper_unresolved 继续保留。

## P1：将 64 KiB 从抽样门槛变成真正的输出预算

- 位置：mcp/gxp_core/source_budget.py 和 mcp/gxp_core/source_index.py 的 bounded_result。
- 复现：frontend_callers 内单个 70,000 字符字段，裁剪后紧凑 JSON 仍为 70,091 字节，虽标记 response_truncated=true 却仍超限。
- 根因：只处理 evidence/call_tree/usages/candidates 的顶层列表，且至少保留 10 项；超长字符串、嵌套结构、其它字段都没有硬兜底。反复 pop 并完整序列化也可能放大裁剪耗时。
- 修复后：按 UTF-8 JSON 字节预算递归裁剪，限制字符串、列表、对象字段和嵌套深度；提前失败路径同样经过预算门禁，并保留省略原因与完整性未决状态。
- 验收：中文、单个巨型对象、多个嵌套列表、超多调用者均达标；截断后的精确性/完整性状态真实，避免将被裁掉的未决项当成链路闭合。

## P2：保留调用链查询入口的完整符号身份

- 位置：mcp/gxp_core/source_analysis.py 的 _backend_query、_entry_matches 与 trace_backend_call_chain starts 筛选。
- 复现：输入 App.Worker.Run(string)，存在 App 的 string/int 重载以及 Other.Worker.Run(string) 时，三个都成为起点，返回 ambiguous。
- 当前实现没有静默选错目标，这是正向保护；但用户已经提供的 namespace/signature 被入口丢弃，导致额外歧义、无关展开与更大结果。内部 target_ids 的类型约束并没有补上这个入口。
- 修复后：完整 symbol_id、命名空间、签名及 System 基本类型别名优先匹配；短名歧义仅返回候选，不递归展开。
- 验收：完整符号只命中一个起点；短名保持明确歧义；异常栈和现有短名黄金查询兼容。

## P2：缩小脏文件指纹依赖面，再考虑增量索引

- 位置：mcp/gxp_core/source_scope.py、source_config.py 和 source_index.py。
- 复现：临时仓库仅增加 notes.md，就改变指纹，并触发一次完整前端扫描。当前名为 relevant_dirty 的列表实际上包含全部 Git dirty/untracked 文件。
- 性能探针：同一临时仓库、各 5 次 repository_metadata；小型文档修改中位数 0.07135 秒，增加无关 64 MiB 未跟踪产物后为 0.12147 秒，约 1.70 倍。此为隔离元数据测量，不是实际业务仓库查询耗时承诺。
- 修复后：索引 v3 按 layer 筛选源码与配置依赖；无关文档/产物仍显示 Git 状态但不读内容、不触发源码重建。相关源码同长度改写仍使用内容摘要失效。
- 验收：无关文档修改不重建，相关文件同长度重写必失效；clean/dirty/大产物/单文件修改分别比较热查询与重建，健康 layer 不受无关文件拖累。

## 已关闭的验收疑点：后端 593 → 592

按 route/method/controller/action 比较原始基线与当前真实源码结果，发现五条旧身份删除、四条新身份增加：

- AuthController.TestConnection1 的 GET test_connection 位于注释中，新版删除正确。
- LockController 的 Refresh/Check/Unlock 由旧版错误聚合的 /api/Lock，恢复各自方法级 Route。
- AppsController.ChangeStatus 由 /api/apps 恢复为 /api/apps/{id}/{status}，参数类型也恢复为 string/bool。

因此此次计数下降属于伪端点清理及路由纠正，不是该对照集合丢失一个活动端点。两个扫描均无 parse_failures；这仍不等于支持所有 C# 语法。

## 实施结果

1. 四项实现和 25 项新增 follow-up 回归已完成；完整套件当前为 173 项，3 项 live 跳过。
2. 最终插件安装后独立 stdio 验证索引 v3、35 项本地工具和黄金链，HTTP 仍为 16 项。
3. 关系策略协议 v2 未因本轮源码优化重新部署；数据库全量压测、页面端到端和其它机器升级仍按原计划安排。

本轮探针使用临时仓库和测试替身，未向实际前后端仓库写入文件；真实对照仅扫描源码，不创建业务数据或修改线上策略。
