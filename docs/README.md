# Look 文档索引

日常使用从[仓库入口](../README.md)或[使用手册](../GXP低代码只读排查使用手册.md)开始。当前模型规则由[技能入口](../skills/gxp-lowcode-debug/SKILL.md)及其参考文档维护；安装由 [AI-SETUP.md](../AI-SETUP.md) 维护。历史计划、评估和测量记录按当时版本理解。

## 当前使用与契约

| 需要什么 | 文档 |
| --- | --- |
| Codex / Claude 安装、更新及验收 | [AI-SETUP.md](../AI-SETUP.md) |
| 提问模板、排查和复核 | [使用手册](../GXP低代码只读排查使用手册.md) |
| 模型工作流及条件路由 | [SKILL.md](../skills/gxp-lowcode-debug/SKILL.md) |
| 动作、副本、画布及历史定位 | [platform-map.md](../skills/gxp-lowcode-debug/references/platform-map.md) |
| 页面、菜单、组件及流程快照 | [cpm-snapshot-routing.md](../skills/gxp-lowcode-debug/references/cpm-snapshot-routing.md) |
| 会话意图及证据绑定 | [conversation-contract.md](../skills/gxp-lowcode-debug/references/conversation-contract.md) |
| 嵌套控制流、交互命中及安全还原 | [branch-verification.md](../skills/gxp-lowcode-debug/references/branch-verification.md) |
| 开发库 Schema、可信关系及本机否决 | [schema-relations.md](../skills/gxp-lowcode-debug/references/schema-relations.md) |
| 摘要、分页、预算与精确值读取 | [diagnostic-output.md](../skills/gxp-lowcode-debug/references/diagnostic-output.md) |
| 组件过滤与覆盖链 | [component-filter-audit.md](../skills/gxp-lowcode-debug/references/component-filter-audit.md) |
| 源码命中、索引 v4 及版本一致性 | [source-code-evidence.md](../skills/gxp-lowcode-debug/references/source-code-evidence.md) |
| 结论、位置块与验证状态 | [report-contract.md](../skills/gxp-lowcode-debug/references/report-contract.md) |
| 本机图谱输入与复用规则 | [business-logic-graph.md](../skills/gxp-lowcode-debug/references/business-logic-graph.md) |
| 图谱存储、查询边界及验收 | [business-logic-graph-contract.md](business-logic-graph-contract.md)；历史验收在后半部分 |
| 可选诊断留证与编辑复用 | [edit-handoff.md](../skills/gxp-lowcode-debug/references/edit-handoff.md) |
| 本机数据库设置 | [database-settings.md](../skills/gxp-lowcode-debug/references/database-settings.md) |
| 已授权页面的运行取证 | [runtime-browser-evidence.md](../skills/gxp-lowcode-debug/references/runtime-browser-evidence.md) |

本地 stdio 为 44 个工具，HTTP 为 16 个；CPM CLI 0.3.1 与 Look 插件 0.5.4 是独立版本。源码索引 v4 按层懒重建；关系否决和恢复只在本机，不需要策略服务器。整案替换必须使用精确案例的完整快照与并发令牌，不能拼接邻域。

## 最新优化实施

[速度与准确性实施记录](speed-accuracy-implementation-20261026.md)按三批记录响应减量、源码字节指纹、精确案例恢复及查询优化。原始五轮测量见[查询工作量基准](query-work-benchmark-20261026.json)。跨 Look / Write 的完整交付报告保存在 Write 仓库的 `docs/look-write-optimization-delivery-2026-10-26.md`。

查询默认 5 秒工作预算不是包括首次初始化、旧 JSON 导入或锁等待的严格端到端上限；中断必须返回不完整状态，不能给完整计数、案例不存在或全局孤岛结论。合成基准不代表真实业务或模型端到端耗时。

## 历史设计、评估和验收

保留原文件及路径以便追溯；下列文档不是新安装或当前调用的必读清单。特别是早期 v3 索引与远程关系策略内容，不能替代上面的现行参考。

| 主题 | 文档 |
| --- | --- |
| 早期准确性扩展契约 | [accuracy-tool-contracts.md](accuracy-tool-contracts.md) |
| 多轮理解与关系检索评估 | [conversation-accuracy-review-2026-09-06.md](conversation-accuracy-review-2026-09-06.md) |
| 2026-09-06 准确性实施验收 | [accuracy-implementation-results-2026-09-06.md](accuracy-implementation-results-2026-09-06.md) |
| 环境与证据来源隔离方案 | [environment-evidence-isolation-plan.md](environment-evidence-isolation-plan.md) |
| 图谱阶段设计与旧版验收 | [业务关系图与自动复用](<GXP 低代码排查业务关系图与自动复用.md>) |
| 源码工具实现计划 | [source-evidence-tools-implementation-plan.md](source-evidence-tools-implementation-plan.md) |
| 源码工具评估 | [source-evidence-tools-evaluation-report.md](source-evidence-tools-evaluation-report.md) |
| 两轮优化独立复核 | [recent-optimizations-independent-review.md](recent-optimizations-independent-review.md) |
| 早期修复契约与验收 | [optimization-repair-contract.md](optimization-repair-contract.md)、[optimization-repair-results.md](optimization-repair-results.md) |
| 修复后第二轮复核 | [post-repair-optimization-review.md](post-repair-optimization-review.md) |
| 2026-09-30 图谱与画布性能 | [performance-optimizations-20260930.md](performance-optimizations-20260930.md) |
| 请求内读取复用实现 | [request-local-read-optimizations.md](request-local-read-optimizations.md) |
| 早期工作笔记 | 仓库根目录 `task_plan.md`、`findings.md`、`progress.md`；仅保留过程记录 |
