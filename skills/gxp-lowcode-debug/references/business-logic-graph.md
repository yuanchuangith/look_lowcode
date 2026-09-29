# 本地业务关系图

仅保存“已确认业务结论 + 证据链”，只作历史定位线索。当前发布副本、当前控制流和当前只读证据始终优先；它不参与业务运行，不写业务库、动作设计、草稿或发布状态，不上传服务器。

## 检索与复核

`search_business_logic_graph(query?, action?, page?, table?, field?, status?, environment="development", limit=20, relation_id?, current_published_designs?, current_evidence_fingerprints?)`

query 空格分词全部匹配，多项过滤条件取交集；table 同时检索表和视图。默认只返回 active 修订，status 可指定确认级别或 superseded/stale/invalidated。返回 relations 中的 nodes、edges、evidence、Mermaid，以及 `must_reverify_current_published_copy=true`。limit 为 1–50，响应最多 256 KiB，按完整关系截断并返回 matched_count/count/truncated。

按锚点重新核对动作身份、当前发布设计、控制流、Schema 或只读数据，运行结论还须本次运行证据。environment 使用实际证据环境 development/test/production，不能按问题发生环境重标开发证据；未知环境不写入。

取得当前证据后再次检索：current_published_designs 传 RefId → 当前发布 design ID；current_evidence_fingerprints 传 evidence ID → 当前 SHA-256，后者必须同时传 relation_id。已知设计或指纹不同会将旧 active 修订标记 stale；没有提供当前证据绝不等于旧图仍有效。

## 保存字段

`upsert_business_logic_graph(relation)` 在最终确认后自动调用一次。只接受白名单字段，不传整个工具响应。

| 字段 | 内容 |
| --- | --- |
| relation_key | 同一问题固定语义键，复查沿用，不含发布时间或随机号 |
| environment | 实际证据环境 |
| conclusion | 已确认抽象结论，最多 1000 字符，不含业务样本值 |
| business_keywords | 1–50 个问题关键词 |
| status | confirmed_static / confirmed_data / runtime_verified |
| published_design_id | 主动作当前发布设计 ID，等于 anchors[0] 的设计 ID |
| anchors | 1–30 个精确定位对象，第一个始终为主动作 |
| tables / views / fields | 各 0–50 个名称，无对应对象时传空数组 |
| calls（可选） | 至多 100 个符号调用摘要，不含传参值，调用边同时放入 edges |
| nodes / edges / evidence | 结构化链路与证据，见下 |
| relation_id / evidence_fingerprint（可选） | 存储自动计算；传入时须匹配，证据变更时省略旧 fingerprint |

每个 anchor 全部包含 `id, action_code, ref_id, page, group_key, node_key, canvas_row, published_design_id`。id 为关系内稳定标识，canvas_row 为 1-based 正整数。公共动作无页面时 page 使用 `public_action` 分类，不伪造页面。不确定节点、行号或副本时继续定位，不填猜测值；同一 RefId 不能同时出现不同设计。

每个 node 包含 `id, kind, label`，可选 `anchor_id, table, view, field`。kind 为 action/node/table/view/field/report；action/node 必须带 anchor_id，table/view/field 必须带同名定位属性。2–60 个节点，ID 唯一。

每个 edge 全部包含 `source, target, kind, label, evidence_ids`。source/target 引用 node ID；kind 为 calls/writes/reads/displays/flows_to；evidence_ids 引用证据 ID。最多 120 条，所有节点必须在边中出现，端点 anchor 必须由该边证据覆盖。

每个 evidence 全部包含 `id, type, fingerprint, summary, anchor_ids`。type 为 published_design/control_flow/schema/readonly_data/runtime；fingerprint 为实际证据的 64 位小写 SHA-256，优先复用工具内容指纹，没有现成指纹时对已读取并脱敏的结构化证据稳定序列化后计算，不能编造。summary 最多 1000 字符，只概述事实；anchor_ids 表示覆盖的锚点。最多 60 项。

## 确认门槛

- confirmed_static：当前发布身份/内容、有效控制流，加 Schema 或只读数据证据；只确认静态链路，不声称运行已经发生。
- confirmed_data：在静态确认基础上有当前只读数据证据，且环境相符；只保存抽象事实与指纹，不保存业务记录值。
- runtime_verified：再有真实运行证据；静态推演或用户“已经修好”不能替代。

每个 anchor 均须满足对应门槛。candidate、未确认推断、截断/partial、未解析调用、工具失败不写入。存储校验结构与证据种类；实际证据是否充分仍由排查流程核对。

同 environment、relation_key、主动作 RefId 生成稳定 relation_id；证据链规范化后生成 evidence_fingerprint。完全相同的重复提交不写新 revision、不增审计。证据或结论变化生成新修订，旧 active 标记 superseded。已知发布设计变化同时使依赖该动作的其他旧结论 stale。失效后重新确认可写新修订，历史保留。

## 失效、迁移与降级

`invalidate_business_logic_graph(relation_id, reason)` 的 reason 只能为 user_confirmed_incorrect/published_design_changed/evidence_invalidated。用户确认错误标记 invalidated，已确认设计或证据变化标记 stale；重复调用不增审计。质疑、候选或工具失败不能作为失效依据。

文件位于 Windows `%LOCALAPPDATA%/GxpLowcodeReadonly/business-logic-graph.json`，macOS/Linux 沿用系统数据目录；支持现有 GXP_LOWCODE_RUNTIME_ROOT。首次访问自动迁移原位置的旧 JSON 列表，或 version 缺省/0/1 且包含 relations/records 列表的对象。仅导入满足当前字段及证据校验的已确认记录；候选计 skipped，缺字段、证据或带敏感载荷计 rejected，重复记录合并，结果计数持久化。无法识别或损坏的文件不覆盖；原子替换失败保留原文件。

单条 payload 64 KiB，文件 16 MiB，超限不驱逐审计。复用跨进程文件锁、同目录临时文件、fsync 与原子替换，锁等待最多 5 秒。available=false 或工具缺失时继续正常只读排查，不把缓存错误当作业务问题，不无限重试或强制覆盖。

## 敏感信息与 Mermaid

禁止持久化密码、令牌、连接信息、业务记录值、完整参数、完整生成 C#、SQL/源码正文。结构使用字段白名单，短文本检查明显凭据/代码；不能改名或塞进 label/summary 绕过边界。提交前只保留名称、定位、抽象结论和指纹。

Mermaid 从已校验 nodes/edges 自动生成，不接受调用者原始图文本。使用 n0/n1 内部 ID，节点与边标签标点转义，禁止 click、链接、HTML 和初始化指令。展示图时保留结构化锚点与证据级别。三个工具只注册本地 stdio，HTTP 不提供。
