# 全局业务关系图契约（0.5.0）

## 工具与查询

本地 stdio 共 41 个工具，其中 6 个图工具；HTTP 仍只有 16 个基础工具，不包含图谱。业务图和数据图是同一份本地 SQLite 的投影，不是两份缓存。

- search_business_logic_graph：旧关键词／动作／页面／表／字段／状态／环境／relation_id 检索保持兼容；历史案例仍可检索，current_published_designs 更新对应动作依赖，current_evidence_fingerprints 需指定 relation_id。历史必须复核当前证据。
- upsert_business_logic_graph(relation)：接受旧 v2 或下述 format_version=3。返回 written、idempotent、relation、graph_revision 和 delta；delta 包含新增／复用实体和事实、更新实体／案例、新支持和待复核数量。
- invalidate_business_logic_graph：保留历史；reason 为 user_confirmed_incorrect（invalidated）、published_design_changed／evidence_invalidated（stale）。只撤销匹配案例支持，其他有效支持不受影响。
- get_business_graph(entity_ids?, query?, scope_id?, environment="development", projection="business", depth=2, include_catalog=false, request_id?, edge_cursor?)：entity_ids 是返回的规范化 SHA-256 ID；关键词也匹配历史别名，以及案例结论、case_key 和旧 business_keywords；案例种子扫描最多 1000 条／1 秒，query_complete=false 时用案例检索定位精确实体继续。depth 0–5；业务／数据投影和目录实体开关。
- trace_business_data_flow(start, target?, direction="downstream", max_depth=8, max_paths=5, scope_id?, environment="development")：start／target 使用规范化实体 ID，direction 为 upstream／downstream，深度 1–20，最多 5 条有向路径。
- analyze_business_graph(scope_id?, environment="development", projection="business", include_catalog=true, entity_ids?, request_id?)：检查整个声明 scope 的邻接；entity_ids 只选择补查种子，不将小邻域误作孤岛分析范围。返回连通分量、零度实体、SCC、收缩 Mermaid、边界、缺口、待复核任务和目录覆盖。

图查询返回 format_version、graph_revision、scope、环境、统一节点／边 ID、完整 evidence 支持集合、Mermaid、truncated、scope_complete 和 frontier。截断后用 frontier 中的 ID 继续查询；同一邻域大量平行边的响应截断可用 next_edge_cursor 作为 edge_cursor 在相同种子／深度下继续（graph_revision 改变则重新分页）；历史统一带 must_reverify_current_published_copy=true。每条边保留 condition、mapping、granularity、review_status；路径为 static_possible，不代表实际运行；路径中只要有 dataset_level 边，就不能当作已确认字段映射，granularity 保守返回 dataset_level。条件逐边展示，conditions_jointly_evaluated=false 表示没有证明所有分支条件可同时满足。

邻域／展示最多 200 节点、400 边，响应最多 256 KiB。支持集合不可切半；一条边最多返回 3 份完整支持，evidence_page_complete=false 表示其他支持未展示。路径因响应预算丢失边时整条路径不返回。分析聚合计数来自完整 scope；成员清单可以采样，带 size 和 truncated。若邻接扫描预算耗尽则 status=incomplete，不报告真实孤岛。内部扫描最多 10000 实体／20000 有效事实；图算法不依赖 NetworkX。

## v3 增量输入

必填：format_version=3、case_key、conclusion、status、entities、facts、evidence。scope_id 默认当前 Schema 配置的非敏感 scope，environment 默认 development；request_id 可选。只接受 confirmed_static／confirmed_data／runtime_verified，候选不入事实图。最多 200 实体、400 事实、100 证据；单次输入 128 KiB。

实体：id（本次局部 ID）、kind、key、label，可选 boundary=unknown/source/sink/independent。系统由 scope＋环境＋类型＋规范化 key 计算统一 ID；label、版本、行号不参与身份。同名不同对象不合并，缺 key 保留 identity_unresolved 任务，不保存猜测身份。

| kind | key 必填字段 |
|---|---|
| action | ref_id |
| node | ref_id, group_key, node_key |
| page / workflow | platform_id |
| business_object | business_key（明确业务标识或已确认映射） |
| report | page_id, component_id |
| table / view | datasource, schema, name |
| field | datasource, schema, owner_kind=table/view, owner, column |
| api | repository, method, route |
| service | repository, symbol |

Schema 必须来自确认的数据对象；不能使用名称猜环境、数据源或 Schema。目录接入默认 datasource 与配置 scope 相同，Schema 使用快照实际 database 名称；新数据源必须明确标识。API method 规范为大写，常见路径模板如 /api/orders/{id:int} 只在 route 身份字段接受，不接受查询参数／凭据；GUID 身份规范为小写；其他业务 key 保留平台大小写语义。别名独立保留。

事实：id（本次局部 ID）、source／target（实体局部 ID）、kind、label、evidence_ids。可选 condition、mapping、granularity=dataset_level/field_level、data_binding=false。

kind：calls/triggers/references/generates/writes/reads/transforms/displays/depends_on/associated_with/flows_to/contains/belongs_to。writes 方向是生产者→数据对象，reads 是数据对象→消费者。field_level 只用于两端都是已确认字段的映射；字段与动作／整份报表之间的关系保守标 dataset_level。

condition 只允许 branch_keys（排序稳定节点／分支标识）和可选 fingerprint（SHA-256）；mapping 只允许 kind=unknown/copy/derive/aggregate/constant/binding 与fingerprint；非 unknown 映射、transforms 和 field_level 都要求指纹。已确认转换使用已读取脱敏结构的指纹，不保存表达式正文。事实身份由两端、关系类型、方向、规范化条件与映射计算；不同分支／转换保留平行边，不用描述文字、案例或发布版本作事实身份。calls 两端必须是 action/node/api/service；仅在 data_binding=true、mapping.kind=binding、有 mapping.fingerprint 和 Schema／只读映射支持时进入数据投影。

证据：id、type、fingerprint（真实结构的 64 位小写 SHA-256）、summary（最多 1000 字）、dependencies（1–40 项），可选 anchors（最多 40 项）。

- type 为 published_design/control_flow/schema/readonly_data/runtime/source_static/cpm_catalog/schema_catalog。
- dependencies 每项只有 kind=action/schema/source/catalog、key、version。必须记录完整依赖，尤其跨动作的所有 RefId→当前发布设计；Schema／源码使用对应版本或指纹。
- anchors 只含 ref_id/design_id/group_key/node_key/page_id/component_id/repository/file/symbol/line/canvas_index 等定位元数据，不保存源正文。
- 发布／控制流证据须依赖 action；Schema 须依赖 schema；源码须依赖 source；目录须依赖 catalog。涉及动作的业务边需要当前 published_design＋control_flow 且覆盖两端动作。数据边另需 schema 或 readonly_data；confirmed_data 需 readonly_data，runtime_verified 再需 runtime。
- 一条事实引用的全部证据组成一个完整支持集合，带来源案例、确认级别、指纹和所有版本依赖。任一依赖变化仅使该集合 stale；至少一份完整有效集合即可支持事实。当前查询从有效集合选择属性，不用已经撤销的最新描述冒充有效绑定。

最小可运行脱敏示例见仓库 tests/fixtures/business_graph_cases.json；真实排查不得直接复用夹具指纹。

## 旧 v2 兼容

不带 format_version 的旧 relation 仍接受：relation_key、environment、conclusion、business_keywords、status、anchors、published_design_id、tables、views、fields、nodes、edges、evidence，可选 calls／relation_id／evidence_fingerprint。主动作仍为 anchors[0]，关系 ID 和返回字段保持原契约。

anchor 全含 id/action_code/ref_id/page/group_key/node_key/canvas_row/published_design_id；node 含 id/kind/label 和对应 anchor_id 或 table/view/field；edge 含 source/target/kind/label/evidence_ids；evidence 含 id/type/fingerprint/summary/anchor_ids。旧限制仍是 64 KiB、2–60 节点、120 边、60 证据，所有节点须有边。要保存孤立实体用 v3。

兼容检索保存安全 v2 案例。只有 RefId／分组／node_key 等明确稳定身份自动融入全局图。旧表、字段和报表没有数据源／Schema／稳定组件身份时保留待消歧；旧 confirmed 不是新版融合凭证。不凭 v2 表名补造 datasource/schema/default。

## 有界补查闭环

每次用户请求共享一个 UUID request_id；只有 get／analyze 显式带它时开启补查。预算在 SQLite 中持久记录，多个工具调用不能重置：最多 3 个既有目录 lookup、1 跳、30 秒（保留提交余量，每个 lookup 最多 10 秒），不递归、不读业务行、不自动刷新。只补当前确认的种子；Schema 表种子只读精确表及最多 20 列，字段种子只接父对象与自身；外键快照缺目标数据源／Schema 时仅保留待消歧，不按同名表连边。CPM 页面种子确认稳定组件，报表种子只接所属页面与自身，不补兄弟节点；源码只接入唯一且 structural 的静态调用，未绑定不作血缘。

快照过期／缺失、身份不明、目录超预算或精确发布证据不足时写待取证任务。不为了连接片段而猜连边，失败不撤销已确认事实、不阻断问题报告。source_static 目录调用明确标条件未确认、静态可能调用，不声明运行发生。

缺口区分 business_independent、legal_boundary、identity_unresolved、evidence_missing、evidence_expired，均不能直接判为 Bug。覆盖分母是声明 scope、快照版本下按需物化的已知目录，不是未知全平台。

## 存储、迁移与安全

Windows：%LOCALAPPDATA%/GxpLowcodeReadonly/business-graph.sqlite3；其他系统沿用系统数据目录，支持 GXP_LOWCODE_RUNTIME_ROOT。Python 标准库 SQLite，外键、WAL、5 秒 busy timeout，事务提交；实体／事实／证据／支持／依赖／观察／目录／任务／审计分开存储；观察与事实只引用 evidence_ids，证据正文每份观察保存一次，不按边重复展开。数据库及 WAL 总预算 256 MiB，超限不驱逐审计。

首次初始化持迁移锁创建临时库，按源文件指纹导入既有 business-logic-graph.json 与 .legacy-v1.json；每条记录有保存点，失败不留下半条观察。校验后原子发布；原文件不移动、不删除、不双写。重复初始化不重导，原有不可转换记录仅保存安全检索线索及原因。旧脚本缺环境／指纹／定位的记录不提升为事实。迁移原始坏载荷不写入 SQLite。

白名单结构和短文本门禁禁止凭据、连接信息、业务记录值、完整参数、SQL／源码正文与完整生成 C#；不能塞进 label/summary 绕过。Mermaid 从已校验结构生成、标签转义，不接受原始 Mermaid／HTML／链接／click 指令。available=false 或工具缺失时继续正常只读排查，不无限重试、不覆盖损坏库、不静默回退双写 JSON。
