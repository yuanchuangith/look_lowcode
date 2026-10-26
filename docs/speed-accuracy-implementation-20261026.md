# Look 速度与准确性实施记录

## 第一批：有界摘要与完整证据续读（0.5.2）

过滤器和异常工具新增 response_detail=summary/full、8–64 KiB 预算（默认16 KiB）、cursor、limit。摘要默认保留身份、计数和定位；完整记录使用同一接口续读，超大单条 JSON 可无损分片恢复。分页游标绑定实际证据指纹，拒绝跨版本及跨查询续读。过滤器保持全体 writer 计数与执行顺序，参数读取复用现有 design_id 固定的 value_path。

异常候选只保留一个集合，省去重复别名。公开服务调用方需要采用新的顶层 runtime_published_candidates；底层诊断引擎完整接口保持原样。summary 不作为完整证据，full 也不绕过预算。技能入口仅路由到独立引用说明。

验证：`python -m unittest test_diagnostic_output test_service test_diagnostics test_server_tools test_accuracy_evidence`，48 项通过。新增5项行为验证覆盖23条writer多页顺序、变旧/跨模式游标拒绝、超长中文完整JSON分片往返、参数版本绑定及异常重复集合消除。所有样例为内存/替身，不读取业务库；未安装或推送。速度对照在第三批统一测量，本批不声称整体提速比例。
