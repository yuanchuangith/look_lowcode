# 只读排查到编辑的本机交接

已定位动作及目标节点、形成明确修改方案后，使用 `export_edit_handoff` 保存本次相关设计证据。它只读取数据库并写本机交接文件；不建立编辑会话、不修改业务、不代替用户确认。用户已经确认具体方案时沿用该确认，不再重复询问。

```json
{
  "identifier": "已核对的 action code 或 RefId",
  "targets": [{"group_key": "实际分组 Key", "node_key": "实际节点 Key"}],
  "diagnosis_source": {
    "version": "published",
    "design_id": "刚才检查的当前发布设计 ID",
    "data_sha256": "刚才工具返回的 64 位内容指纹"
  },
  "change_spec": {
    "user_request": "用户本次原始要求",
    "summary": "已展示的具体修改方案",
    "changes": [{
      "group_key": "实际分组 Key",
      "node_key": "实际节点 Key",
      "description": "修改内容",
      "parameter_path": "/inputParams/实际字段",
      "before": {"code": "完整原参数记录"},
      "after": {"code": "完整拟改参数记录"}
    }],
    "preserve": ["本次必须保留的表达式或行为"],
    "scenarios": [{"name": "场景名称", "description": "场景条件", "expected": "期望行为；未经运行验证不能写已通过"}]
  }
}
```

`targets` 必须是 1–10 个已经定位的精确节点；字段定义来自真实参数，不把示例占位符发送给工具。`change_spec` 仅接受示例顶层字段；changes 项仅接受示例中的字段。`preserve` 是文字列表，scenarios 可以是文字或上述三个字段的对象。原始要求限 8 KiB、摘要 2 KiB、方案合计 32 KiB；超限应缩小修改范围，不能截断完整参数。

导出集中读取当前草稿，保存目标完整参数、父级参数指纹、相邻节点、分组结构及完整分组上下文指纹；上下文包括所有节点参数及分组输入输出配置，以覆盖扁平标记画布中没有写入 `depth` 的条件依赖。诊断使用的发布／草稿单独核对设计 ID 和内容指纹。旧历史或已删除发布不能冒充当前版本。`source_target_differences` 明确指出诊断副本与草稿目标的差异；不得把发布参数直接覆盖草稿。同组无关参数变化也会保守要求刷新证据。指纹只是内容漂移守卫，不代表控制流语义已经验证；嵌套分支仍遵守原控制流取证规则。

导出返回 `handoff_ref: {handoff_id, sha256}`，交给编辑端 `begin_edit_session(handoff_ref=...)`。编辑端核对当前环境、动作、草稿及目标后直接返回必要上下文；复用已确认方案，不从头搜索页面和动作。用户未确认方案时仍先取得具体修改范围确认。

新对话可用 `read_edit_handoff(identifier="实际 action code 或 RefId")` 列出候选，必须明确选定 ID，不能自动取最新记录。再用 `read_edit_handoff(handoff_id="32 位小写十六进制 ID", sha256="内容指纹")` 读取；新对话需要确认本次修改范围，旧编辑占用和审批均不继承。同一对话已有明确确认时不重复索要。

记录超过响应预算时 `response_complete=false` 并给出 `next_read`；按返回的 `target_index` 续读。单节点仍过大时使用现有 `inspect_action` 和参数分页路径核对当前草稿。完整参数保留在记录中，不能将响应中省略部分当作空值。

交接数据位于 `%LOCALAPPDATA%\GxpLowcodeHandoff\v1`，其他系统沿用用户本地数据目录。只接收 ID，不接收任意路径。记录最多 256 KiB；不保存凭据、查询结果／业务记录值或完整生成 JS／C#。指纹只是完整性检查，不是授权或人工审批。两个工具仅本机 stdio 注册，不暴露给 HTTP。

记录缺失、损坏、版本不支持、缓存目录不可写时，工具返回错误码和普通定点检查路径。继续正常只读排查，不因交接失败建立新占用、重启 Codex、更新插件或触发业务保存。

MCP 响应外层的 `trace_id`、`total_elapsed_ms`、`timings` 仅用于性能诊断；数据库读取及交接阶段均记录耗时，失败也保留已完成阶段。计时不属于设计证据，不参与交接指纹、计划或审批签名。日志只有阶段、耗时、数量和错误码。
