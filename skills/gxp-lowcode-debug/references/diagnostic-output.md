# 有界诊断结果与续读

`inspect_component_filters` 与 `trace_dynamic_exception` 默认 `response_detail="summary"`，默认 `max_output_bytes=16384`，允许 8192–65536；`limit=10`，允许 1–50。摘要保留定位、计数及续读入口。`response_detail="full"` 展开当前页，仍遵守预算，并不意味着一次返回全量证据。

- 过滤器的分页 writer 位于顶层 `writers`，`component_filters.writer_count` 是完整匹配数；execution_order 保持所有分组中的原顺序。每个 writer 的 `params_read` 复用 `inspect_action.value_path`，绑定 design_id。只有确认全部相关 writer 及父条件后才能判断最终过滤范围。
- 异常候选位于唯一的 `runtime_published_candidates`，每条包含 action、发布设计身份及证据；不再重复返回 candidate_versions/current_published_vs_draft 别名。旧服务调用方若读取 actions 嵌套结构须迁移到这一集合；底层 DiagnosticEngine 的完整结果不变。
- `has_more=true` 时，保留原查询参数并将 `next_cursor` 作为 `cursor` 继续。游标绑定实际设计/证据指纹和 summary/full 模式，版本或查询变化即拒绝。摘要条目的 `detail_cursor` 用于相同查询的 full 模式，定位该条详细证据。
- 超大单条结果返回 `record_value_page`，其 text 是 JSON 的字符片段；沿 next_cursor 拼完该条后再解析，不把片段当完整 JSON 或完整证据。分页续读是按需读取，并不要求每次都拼回全部配置。
- `evidence_complete=false` 或 `response_complete=false` 必须保留；摘要、未读页及遗漏内容不能证明不存在其他调用、条件或历史候选。预算按缩进 UTF-8 JSON 结构载荷计算，传输附加计时字段不计入该预算。

已有 `inspect_action` 默认关闭完整参数和 C#；先按 group/node_key/focus_fields 定位。表达式只读精确 `/paramsValue/...`，续页使用返回的 next_offset，并携带 design_id。控制流按需指定 `render="tree_text"`，避免同时取多份文本视图。C# 只在需要时读取目标行或分组范围；关键词证据不是精确 Source Map。
