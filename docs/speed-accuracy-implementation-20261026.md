# Look 速度与准确性实施记录

## 第一批：有界摘要与完整证据续读（0.5.2）

过滤器和异常工具新增 response_detail=summary/full、8–64 KiB 预算（默认16 KiB）、cursor、limit。摘要默认保留身份、计数和定位；完整记录使用同一接口续读，超大单条 JSON 可无损分片恢复。分页游标绑定实际证据指纹，拒绝跨版本及跨查询续读。过滤器保持全体 writer 计数与执行顺序，参数读取复用现有 design_id 固定的 value_path。

异常候选只保留一个集合，省去重复别名。公开服务调用方需要采用新的顶层 runtime_published_candidates；底层诊断引擎完整接口保持原样。summary 不作为完整证据，full 也不绕过预算。技能入口仅路由到独立引用说明。

验证：`python -m unittest test_diagnostic_output test_service test_diagnostics test_server_tools test_accuracy_evidence`，48 项通过。新增5项行为验证覆盖23条writer多页顺序、变旧/跨模式游标拒绝、超长中文完整JSON分片往返、参数版本绑定及异常重复集合消除。所有样例为内存/替身，不读取业务库；未安装或推送。速度对照在第三批统一测量，本批不声称整体提速比例。

## 第二批：源码固定快照与精确案例恢复（0.5.3）

源码索引 v3 升级到 v4；每层保存与实际解析字节一致的原始 SHA-256 台账，并随索引、层 generation 和总 manifest 原子发布。健康层仍可复用，旧版或缺台账层按需重建。模型绑定、异常流和过滤契约的即时读取都先将同一份字节与台账比对，再使用它做词法分析；有变化只重试一次，仍不匹配则不返回混合证据。索引 JSON 在单次请求内复用解析结果，不缓存跨请求的新鲜状态。

写后图谱响应过大时现在提供精确案例工具调用及 scope/environment/case_key，要求完整快照与并发令牌；不再指向可能截断的图邻域拼整案。

验证：44 项 source 系列测试、36 项 followup/repair/案例恢复测试通过（共80项）。新增6项源码台账验证覆盖 CRLF 原始字节、同大小同mtime改写、复用已验证字节、连续变化只重试一次、generation一致发布、缺台账重建及失败保留旧层；新增写后精确恢复回归。修正两处测试在Windows短路径与长路径表达上的不等价比较。全用临时目录或替身，无业务访问；未安装、推送或迁移业务数据库。

## 第三批：减少无效读取并限制查询工作量（0.5.4）

控制流根动作、公共被调动作及过滤器检查现在只取画布数据和 C# 指纹，不传输生成 C# 正文。后端调用追踪在单次请求构建 caller 邻接表和 symbol 多值映射，使用 deque；重复 symbol_id、原始候选顺序、歧义不自动展开、深度和循环语义保留。

图检索在 SQL 中限制 scope／环境／精确关系／生命周期／级别，只有携带当前证据时才开启写事务；逐行处理，仅保留 limit 个结果但完整计数，不反复序列化未使用的字段。图快照分批读取别名、首个有效支持和边界 observation，保留别名排序／20 条上限、支持 ID 排序／支持数量、最新有效边界语义。

检索、精确案例读取、邻域、路径和分析使用请求内 SQL 进度回调及 Python deadline；默认 5 秒、2500 万 SQLite VM 指令，内部仍保留原来的规模上限。中断明确返回 incomplete、未知总数与不完整范围，不提供案例不存在或真实孤岛的结论。发生中断的本地证据状态写入整体回滚。没有新增业务库迁移；未安装、推送或访问业务数据。

预算范围：5秒限制通过查询阶段安装的 SQLite progress handler 及 Python 检查实施，不是严格的端到端响应上限。deadline 在请求入口建立，但首次本地缓存初始化、旧 JSON 导入、连接设置和锁等待不能被该 handler 抢占中断；这些阶段可能使总耗时超过5秒，锁等待另受 lock_timeout_seconds／SQLite busy_timeout 限制。进入查询阶段后检查已过去的时间；若已超时，仍返回 incomplete，不给完整计数或缺失结论。

验证：`python -m unittest test_business_graph test_business_graph_catalog test_business_logic_graph test_source_lexical_contracts test_followup_contracts test_service test_control_flow test_accuracy_evidence test_graph_query_work`，152 项通过。新增8项覆盖只读事务／准确计数、SQL中断、Python deadline、版本与生命周期回滚、精确案例中断不误判缺失、批量读取、根／被调动作的 C# 载荷，以及重复目标顺序／循环／深度。40实体／20事实快照的读取查询最多7条，避免随每个实体／事实增长的查询次数。

性能对照：`python scripts/benchmark_query_work.py --rounds 5 --output docs/query-work-benchmark-20261026.json`。对照第三批前的 `15f7e89`，相同临时 SQLite（1000案例，其中250有效）和内存源码索引（25001符号、35100边），5轮交替先后顺序。只忽略新增 `matched_count_complete` 元信息，三个输出的完整规范JSON SHA-256每轮一致。原始每轮时间、查询次数和指纹保存在上述JSON。

| 合成工作 | 修改前中位数 | 修改后中位数 | 比值 |
| --- | ---: | ---: | ---: |
| 图快照 | 62.93 ms | 51.01 ms | 1.23× |
| 图检索 | 171.18 ms | 48.22 ms | 3.55× |
| 后端调用追踪 | 1027.86 ms | 64.63 ms | 15.90× |

测量不含子进程启动；不表示真实业务库、冷索引或完整诊断端到端具有同样倍数。C# 载荷优化由替身回归核对读取选项，不据此声称真实数据库网络耗时改善。

补充验证：50项 source／server工具／技能契约测试通过，`skill-creator/scripts/quick_validate.py` 验证技能有效。本批共202项相关测试通过。
