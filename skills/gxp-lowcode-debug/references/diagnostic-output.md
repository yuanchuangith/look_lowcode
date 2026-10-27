# 有界诊断结果与续读

## 先定位，再精读

- `inspect_action` 第一阶段保持 `include_params=false/include_generated_csharp=false`；明确分组、节点 Key 或窄画布范围后才读参数，超过 10 个节点先缩小范围。
- 只有异常栈给出精确 C# 行，或节点事实仍不足以解释问题时，才显式 `include_generated_csharp=true`；`terms` 不是读取 C# 的授权。优先 `generated_csharp_scope=group_method`，未解析范围时不把全动作命中当精确节点。
- `inspect_action` 默认 32 KiB；出现 `response_complete=false`、`evidence_complete=false` 或省略清单，按 `next_read` 补齐当前结论所需证据，保留 `design_id`。未补齐前只报候选，不自动耗尽所有分页。

## 过滤器与动态异常

`inspect_component_filters` 与 `trace_dynamic_exception` 默认 `response_detail="summary"`，默认 `max_output_bytes=16384`，允许 8192–65536；`limit=10`，允许 1–50。摘要保留定位、计数及续读入口。`response_detail="full"` 展开当前页，仍遵守预算，并不意味着一次返回全量证据。

- 过滤器的分页 writer 位于顶层 `writers`，`component_filters.writer_count` 是完整匹配数；execution_order 保持所有分组中的原顺序。每个 writer 的 `params_read` 复用 `inspect_action.value_path`，绑定 design_id。只有确认全部相关 writer 及父条件后才能判断最终过滤范围。
- 异常候选位于唯一的 `runtime_published_candidates`，每条包含 action、发布设计身份及证据；不再重复返回 candidate_versions/current_published_vs_draft 别名。旧服务调用方若读取 actions 嵌套结构须迁移到这一集合；底层 DiagnosticEngine 的完整结果不变。
- `has_more=true` 时，保留原查询参数并将 `next_cursor` 作为 `cursor` 继续；该链同时覆盖未读记录和被裁剪的顶层元数据（envelope）。游标绑定实际设计/证据指纹和 summary/full 模式，版本或查询变化即拒绝。摘要条目的 `detail_cursor` 用于相同查询的 full 模式，定位该条详细证据。旧 v1 记录游标仍可使用，新 v2 游标同时保存记录与元数据的字符偏移；直接使用返回值，不自行改写。
- 超大单条结果返回 `record_value_page`；顶层元数据被裁剪时，同一 `next_cursor` 链先读完记录，再返回 `envelope_value_page`，无需独立游标。两者的 `text` 都是 JSON 的字符片段，按同一 `snapshot_fingerprint`、连续 `offset` 拼接，到达 `total_characters` 后再解析；`envelope_value_page.encoding="json"`，其 `continuation_complete=true` 只表示元数据片段已读完，不表示摘要省略的详细证据也已读完。分页续读按需进行，并不要求每次都拼回全部配置。
- 顶层元数据一旦被裁剪，该响应的 `response_complete` 与 `evidence_complete` 始终为 false，完整元数据需从片段恢复。`has_more=false` 只表示没有后续片段，不能单独证明已读全；还须核对指纹、偏移、总字符数及相关记录页。出现 `response_truncated=true`、`envelope_complete=false`、省略清单（`omitted`）或完整性标志为 false 时，不把当前响应当完整证据；摘要、未读页及遗漏内容不能证明不存在其他调用、条件或历史候选。预算按缩进 UTF-8 JSON 结构载荷计算，传输附加计时字段不计入该预算。

已有 `inspect_action` 默认关闭完整参数和 C#；先按 group/node_key/focus_fields 定位。表达式只读精确 `/paramsValue/...`，续页使用返回的 next_offset，并携带 design_id。控制流按需指定 `render="tree_text"`，避免同时取多份文本视图。C# 只在需要时读取目标行或分组范围；关键词证据不是精确 Source Map。
