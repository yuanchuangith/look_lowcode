# Look 开发文档

本文是 Look 唯一持续维护的开发主文档，说明代码入口、开发流程和验收口径。详细工具契约按需链接，历史方案与测量保留在 [参考及历史索引](docs/README.md)，不作为平行开发指南维护。安装与迁移以 [AI-SETUP.md](AI-SETUP.md) 为准；模型执行规则以 [SKILL.md](skills/gxp-lowcode-debug/SKILL.md) 及其引用为准。

## 架构与目录

调用链为 MCP 工具 → 服务/专用分析模块 → 受控数据库读取或本机证据缓存 → 有界结果。Look 负责只读诊断，Write 负责获授权的草稿编辑，两者不共享编辑会话或审批。

| 位置 | 开发职责 |
| --- | --- |
| [mcp/server.py](mcp/server.py) | 本地 stdio 工具注册、参数与响应边界；当前 44 个工具 |
| [mcp/http_server.py](mcp/http_server.py) | HTTP 入口，只注册 16 个 Look 工具，不开放本机扩展 |
| [mcp/gxp_core/service.py](mcp/gxp_core/service.py) | 动作、副本、画布、诊断与交接的服务编排 |
| [mcp/gxp_core/repository.py](mcp/gxp_core/repository.py)、[sql_guard.py](mcp/gxp_core/sql_guard.py) | 业务库只读访问、SQL 校验与查询限制 |
| `mcp/gxp_core/canvas*.py`、`call_flow.py`、`diagnostics.py` | 画布事实、控制流、跨动作追踪与异常定位 |
| `mcp/gxp_core/cpm_*.py`、`schema_*.py`、`relation_policy.py` | 平台/Schema 快照、可信关系与本机否决记录 |
| `mcp/gxp_core/source_*.py` | 按层源码索引、词法分析、调用链及指纹核对 |
| `mcp/gxp_core/business_graph*.py`、`graph_budget.py` | 本地 SQLite 图谱、证据支持、查询和工作预算 |
| `mcp/gxp_core/diagnostic_output.py`、`telemetry.py` | 响应投影、分页和分段耗时 |
| `skills/gxp-lowcode-debug/` | 模型工作流入口、条件路由和详细引用 |
| `scripts/`、`tests/`、`deploy/` | 启动/安装/验证、离线回归、HTTP 部署配置 |

## 修改时必须保持的契约

- 数据库只读，不增加业务写入、草稿保存或发布能力。结构化工具优先，SQL 必须经过现有防护；凭据不进入工具参数、日志或报告。开发环境证据不能证明生产结论。
- 同一动作的草稿和发布是两个副本，只有发布驱动运行。保持动作身份、设计 ID、节点 Key、环境和版本绑定；静态、数据型和真实运行证据分别表达。
- 默认先定位再精读。过滤审计和异常输出默认 `response_detail="summary"`、16 KiB，完整模式也受预算约束；分页游标绑定查询条件和证据版本。摘要、截断、零命中或预算中断不能证明完整或不存在。细节见 [诊断输出契约](skills/gxp-lowcode-debug/references/diagnostic-output.md)。
- 源码索引为 v4：每层记录实际解析字节的 SHA-256，并与 generation 原子发布；即时读取必须核对并复用同一份字节，旧索引按层重建。见 [源码证据](skills/gxp-lowcode-debug/references/source-code-evidence.md)。
- 图谱仅保存已确认的 metadata-only 事实和完整支持集合。整案替换必须精确读取完整 `case_snapshot`，检查 `complete/replacement_safe` 并带并发令牌；不能拼接邻域。见 [图谱契约](docs/business-logic-graph-contract.md)和[图谱工作流](skills/gxp-lowcode-debug/references/business-logic-graph.md)。
- 图查询默认 5 秒工作预算不是包含初始化、旧 JSON 导入或锁等待的严格端到端上限。提前中断返回不完整状态，不给完整计数、案例不存在或全局孤岛结论。
- 诊断交接可选，不能继承旧会话或审批；编辑授权、显式启用和保存后的核对规则由现有技能维护。见 [编辑交接](skills/gxp-lowcode-debug/references/edit-handoff.md)。

## 日常开发流程

1. 从本页定位代码，再按任务读取一份相关契约。变更前核对调用方、工具参数、现有回归及本机/HTTP 差异；不要从历史计划推断当前协议。
2. 在最小相关模块修改；工具字段或默认值变化时同步服务边界、必要的兼容语义及对应技能引用。复用请求内已读取证据，不缓存跨请求的新鲜判断。
3. 先跑命中改动的离线测试。涉及版本、完整性、歧义或预算时，覆盖相应拒绝路径；测试夹具使用内存替身或临时目录。
4. 涉及响应体积或耗时才做成对测量，记录基线提交、运行环境、数据规模和输出一致性。结论与原始附件一起保留。
5. 检查差异后更新本页的持续规则或权威引用。提交代码不等于重新安装；安装、凭据配置和真实业务验收分别按用户任务执行。

## 针对性验证

### 诊断缓存与有限补查

两个诊断分页工具复用进程内纯分析快照，按数据源/账号作用域、参数和分析器版本隔离。LRU 上限32项，单项8 MiB、累计序列化64 MiB，闲置5分钟淘汰（不是 Python 堆硬上限）。每次命中用本请求数据库会话重验全部实际读取依赖，含空候选、历史、当前副本与访问权限；无法完整记录、截断或验证失败时不使用缓存。大字段以同谓词 UTF-8 SHA2 重读，淘汰重建继续核对现有 v1/v2 游标指纹。缓存不落盘、不缓存新鲜度或授权结论。

`diagnose_codex_input` 的动态异常分支复用同一摘要、分页和依赖重验缓存，默认16 KiB预算覆盖完整嵌套结构；上下文纳入游标绑定并支持 envelope 片段恢复。自然语言返回唯一且完整的动作身份时，技能直接复用身份读取当前版本。CPM 搜索返回查全状态和停止原因；达到上限立即停止并保守标记不完整，不能按零命中证明不存在。源码重建按当前字节摘要、配置和解析器版本复用进程内纯解析结果，跨文件关联及 generation 仍完整重建；`force=true` 强制重解析。实现、验证及未测范围见[本轮修复记录](docs/speed-accuracy-repairs-20261028.md)。

`evidence_gaps` 和 `fallback` 是计入相应载荷预算的传输指导，不进入诊断指纹。字段包括缺口代码、受影响结论、`next_read`、可继续工作、已尝试路径和停止原因。跨工具有限补查由技能维护同问题累计3次/30秒预算；不增加通用执行器。详情见[有限补查](skills/gxp-lowcode-debug/references/diagnostic-fallback.md)。

`resolve_table_relation(force_live=true)` 在四项源/目标表列明确时直接走窄实时路径，不依赖全量刷新；新增可选 `live_timeout_ms=30000`（100..30000）约束该路径共享的查询工作期限，不改变其他参数组合的全量候选流程。保留前后否决检查、完整目标唯一键、类型与全量数据阈值；不持久化，不证明全局候选唯一。连接建立和驱动退出受原有连接/网络超时控制，不将查询工作期限宣称为操作系统级硬取消。

CPM 查询刷新失败时仅在旧快照结构可用的情况下返回显式陈旧候选；缺旧快照仍报错。源码层失败只保留健康层；不得用旧索引位置说明当前源码。离线成对测量见[缓存基准](docs/diagnostic-cache-benchmark-20261027.json)，跨库验收另见 Write 的本次交付报告。

CPM 表单拉取先经 `/api/app_info` 获取当前开发版本并核对应用/站点，再把同一 `dataVersionId` 传给页面清单和结构请求；明确 `isOfficialPreview=false`，不在缺版本时回落到发布。每页 `page-meta.json.designSource` 记录来源；旧来源基线必须先全量刷新，降级保留旧页时保留原来源。显式 `refresh_cpm_snapshot` 默认跳过TTL，普通快照查询仍按TTL复用。验证入口为 `vendor/cpm-cli` 下 `npm test`（含已保存未发布后单页重拉），及 `test_cpm_snapshot.py`。

在仓库根目录运行。`run_tests.py` 优先使用已安装的 Look Python 环境，否则使用当前 Python；需要已具备 [requirements.txt](requirements.txt) 依赖。它设置模块路径，默认强制关闭真实数据库测试，即使外部设置了 `GXP_LIVE_TEST=1`；只有显式 `--live` 才启用在线只读检查。

```powershell
python scripts/run_tests.py -p test_skill_contract.py -v
```

按改动选择测试文件，每条命令将 `-p` 换成对应模式即可，无需把下表全跑一遍：

| 改动范围 | 建议测试模式 |
| --- | --- |
| 技能引用或模型路由 | `test_skill_contract.py` |
| MCP 参数、注册或 HTTP 范围 | `test_server_tools.py`、`test_http_server.py` |
| 摘要、分页、版本绑定 | `test_diagnostic_output.py`、`test_accuracy_evidence.py` |
| 画布和跨动作控制流 | `test_canvas.py`、`test_control_flow.py` |
| 源码索引和文件一致性 | `test_source_file_snapshots.py`、`test_source_freshness_contracts.py`、`test_source_index.py` |
| 图谱存储、查询和预算 | `test_business_graph.py`、`test_business_graph_catalog.py`、`test_graph_query_work.py` |
| 启动或安装入口 | `test_local_entrypoints.py` |

扩大验证时运行 `python scripts/run_tests.py`。启动协议核对使用 `python scripts/verify_mcp.py --timeout 15`：只执行 `initialize`、`ping`、`tools/list`，不调用业务工具；通过只证明进程和工具注册可用。图协议改动可用 `python scripts/verify_business_graph_stdio.py`，它向临时缓存写脱敏夹具，不写业务库。

## 性能与准确性口径

- 响应减量比较完整流程总 UTF-8 字节，同时记录新增往返次数；完整证据可恢复性和语义一致性必须先通过。
- 耗时区分冷/热路径、来源扫描、子进程、SQL、序列化和服务总耗时。同机交替基线与候选，每场景至少五轮，报告中位数与范围；尾延迟结论需要更多样本。
- 合成基准入口为 `scripts/benchmark_query_work.py`，只用临时 SQLite 和内存源码索引。例：`python scripts/benchmark_query_work.py --baseline-ref 15f7e89 --rounds 5 --output docs/query-work-comparison.json`。该提交是既有第三批基线，新任务应明确选择自己的基线，附件不要覆盖已交付测量。
- 准确性分别统计误绿、误阻和未验证。歧义、超时、不支持及执行失败不得被补成正确或错误；静态分析通过不等于真实运行通过。
- 最近一轮实施与测量见 [2026-10-26 实施记录](docs/speed-accuracy-implementation-20261026.md)。合成提速倍数不能外推到真实业务、冷索引或模型端到端延迟；未测项明确标为未测。

## 安装、版本与文档维护

安装/更新/迁移先完整阅读 [AI-SETUP.md](AI-SETUP.md)，并遵循 [AGENTS.md](AGENTS.md)。Codex 使用 `scripts/install_codex_plugin.py`，Claude 使用 `scripts/install_claude.py`；不要手工重建 Look marketplace 或复制插件目录。安装后按指南验证并重新加载客户端会话，普通源码修改不自动触发这些操作。

插件版本以 [.codex-plugin/plugin.json](.codex-plugin/plugin.json) 为准；源码索引版本、图数据格式和 CPM CLI 版本各自独立。修改公共契约时核对版本影响，不因只改文档自动提升运行版本。

只维护本页这一份开发主文档。[README.md](README.md) 负责入口与产品概览，[AI-SETUP.md](AI-SETUP.md) 负责安装，[使用手册](GXP低代码只读排查使用手册.md) 负责用户操作，技能引用负责模型规则和详细契约，[docs/README.md](docs/README.md) 只列参考及历史资料。历史报告保持日期、原结论和附件路径，不追改成当前指南；新增成果以记录链接接入，不另建平行开发总览。
