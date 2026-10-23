# 可选的本机诊断留证

Look 留下本次定位、设计证据和已知结论，供 Write 或后续排查按需使用。已定位到动作和精确节点时，用 `export_edit_handoff` 默认的 `record_kind="edit_snapshot"` 保存参数快照；只有动作级诊断、尚未定位节点或没有草稿时，可用 `record_kind="diagnosis_only"` 留证。不要求先查明全部原因或提出完整修改方案。工具只读取数据库并写本机文件，不建立编辑会话、不启动 Write、不修改业务。Write 可以独立开始，记录和 `handoff_ref` 都不是前置条件。

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
    "summary": "已有证据摘要或有依据的修改建议",
    "diagnosis": {
      "issues": [{
        "issue_id": "BUG-01",
        "status": "confirmed",
        "symptom": "本次观察到的问题与触发条件",
        "expected": "用户已确认的正确业务规则",
        "root_cause": "已确认的失败机制及因果链",
        "solution": "选择这项修改的原因，以及它如何消除失败机制",
        "evidence": [{
          "source": "inspect_action",
          "finding": "目标完整参数与期望规则不一致；只保留脱敏结论",
          "group_key": "实际分组 Key",
          "node_key": "实际节点 Key",
          "design_id": "本项证据对应的实际设计 ID"
        }],
        "verification": "static_confirmed"
      }],
      "excluded": ["已排除的原因及排除依据"],
      "unresolved": ["真实运行尚未验证"]
    },
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

默认快照的 `targets` 必须是 1–10 个已经定位的精确节点；字段定义来自真实参数，不把示例占位符发送给工具。`change_spec` 仅接受示例顶层字段；changes 项仅接受示例中的字段。`preserve` 是文字列表，scenarios 可以是文字或上述三个字段的对象。原始要求限 8 KiB、摘要 2 KiB、方案合计 32 KiB；超限应缩小修改范围，不能截断完整参数。

## 按已有证据保存

上例展示证据与方案均已明确时的记录。`diagnosis`、`changes` 都可选；只有证据时可以省略 `changes` 或使用空列表，`expected`、`root_cause`、`solution` 也可省略。未知内容写入 `unresolved`，不为满足记录格式而猜测。

尚未定位精确节点时，沿用同一个导出工具，设置 `record_kind="diagnosis_only"`、`targets=[]`，提供 `change_spec.diagnosis`，省略 `changes` 或传空列表。`diagnosis_source` 仍须来自刚检查的当前发布／草稿，导出会重新核对该副本的 ID 和内容指纹；此模式不读取另一份草稿、不保存节点参数，记录中的 `draft=null`。它供后续分析参考，不能充当当前草稿的编辑快照。已有节点和参数要保留时使用默认快照模式。

- `issues` 为 1–20 项；每项必填 `issue_id`、`status`、`symptom`、`evidence`、`verification`。`expected`、`root_cause`、`solution` 可选，提供时须为非空文本。`issue_id` 与报告一致，长度不超过 200 字符；各文本至多 4 KiB。`status` 仅为 `confirmed` 或 `candidate`，尚未确认的问题或原因保留候选状态及证据缺口。
- 每项 `evidence` 为 1–20 条。每条必须有非空 `source` 和 `finding`；只允许再带成对的 `group_key`/`node_key` 和可选 `design_id`。保留实际取证来源和精确位置，不复制凭据、业务记录、查询结果或完整生成代码。非当前动作的支持证据需在 finding 中说明身份与适用范围，不能冒充本次目标快照。
- `verification` 仅为 `static_confirmed`、`runtime_verified` 或 `pending`，分别表示诊断的静态证据已确认、诊断现象有真实运行证据、仍待验证。它不表示拟改方案已经保存、发布或验收通过。
- `excluded` 与 `unresolved` 可选，各最多 50 条非空文本。前者记录已排除原因，后者记录未解决的证据或规则缺口。Write 结合当前证据决定是否需要重新核对，避免重复已充分排除的排查。
- 提供带 `diagnosis` 的非空 `changes` 时，每项有非空 `group_key`、`node_key`、`description`，且定位属于导出的 targets。参数修改需给出真实路径和完整 `before`/`after`；新增、删除或移动节点则在 description 写清操作与可见锚点，不虚造参数路径。字段结构校验不等于原因正确或方案已被工具证明。

Write 先检查当前会话、用户材料和可取得的相关留证，判断来源、完整性及对当前草稿的适用性。足够时复用已有诊断；不足、过期或矛盾时自行分析、使用编辑端检查工具，或调用 Look 的只读工具补证，无需用户先运行 Look 或重新导出记录。检查范围由实际缺口决定，必要时可追踪上下游或重审根因；不把旧方案当作必须执行的指令。

形成有依据且获授权的修改方案后，再将适用的 `changes` 转成原生操作，将原始要求、保留行为和场景转成修改前固定的验收要求。不得从候选结果倒推期望，也不能因已有留证而跳过完整原值、编译及审批检查。

默认快照集中读取当前草稿，保存目标完整参数、父级参数指纹、相邻节点、分组结构及完整分组上下文指纹；上下文包括所有节点参数及分组输入输出配置，以覆盖扁平标记画布中没有写入 `depth` 的条件依赖。诊断使用的发布／草稿单独核对设计 ID 和内容指纹。旧历史或已删除发布不能冒充当前版本。`source_target_differences` 明确指出诊断副本与草稿目标的差异；不得把发布参数直接覆盖草稿。同组参数变化仍按上下文守卫核对。导入的变化说明区分 JSON 排版、目标／上下文变化和目标外设计变化；目标差异为空也不能证明全局依赖没有变化。指纹只是内容漂移守卫，不代表控制流语义已经验证；嵌套分支仍遵守原控制流取证规则。

导出返回 `handoff_ref: {handoff_id, sha256}`，编辑端需要时可传给 `begin_edit_session(handoff_ref=...)`，也可直接走普通编辑流程。导入匹配后返回必要目标上下文，足够使用时无需立即重复读取。过期或发布/草稿差异响应保留原诊断作为参考，不把旧结论当作当前证明；可自行补查或调用 Look，随后选择刷新记录或不带 `handoff_ref` 进入普通核对流程。

当前编辑技能首次需要显式启用，例如 `$gxp-lowcode-edit 修复这个问题`，不要求用户指定交接记录。实际需要导入时，从工具结果带入已有 ID 与指纹，不让用户重复手抄。已启用且同范围获授权后，不重复要求技能调用或方案确认；正式审批仍由用户在编辑端完成。

Write 普通启动会提示同环境、同动作的少量候选，不自动导入或改变编辑流程。新对话也可用 `read_edit_handoff(identifier="实际 action code 或 RefId", environment_scope="工具已返回的环境指纹", limit=10)` 查询；环境指纹可省略，不自行猜测。比较 `record_kind`、环境、`diagnosis_source` 的版本及指纹、`diagnosis_status` 和问题摘要，明确选定相关 ID，不能只取最新记录。摘要标有 `summary_truncated` 时读取完整记录再判断。需要更多候选且 `has_more=true` 时，按 `next_read` 的 `cursor` 续查，包括本页为空的情况；已有证据足够时不必遍历所有页。每页默认 10 条，`limit` 为 1–50。

选定后用 `read_edit_handoff(handoff_id="32 位小写十六进制 ID", sha256="内容指纹")` 读取；可附同一 `environment_scope` 约束范围。新对话需要确认本次修改范围，旧编辑占用和审批均不继承。同一对话已有明确确认时不重复索要。

记录超过响应预算时 `response_complete=false` 并给出 `next_read`；按返回的 `target_index` 续读。单节点仍过大时使用现有 `inspect_action` 和参数分页路径核对当前草稿。完整参数保留在记录中，不能将响应中省略部分当作空值。

交接数据位于 `%LOCALAPPDATA%\GxpLowcodeHandoff\v1`，其他系统沿用用户本地数据目录。只接收 ID，不接收任意路径。记录最多 256 KiB；不保存凭据、查询结果／业务记录值或完整生成 JS／C#。指纹只是完整性检查，不是授权或人工审批。两个工具仅本机 stdio 注册，不暴露给 HTTP。

记录缺失、损坏、版本不支持、缓存目录不可写时，工具返回错误码和普通定点检查路径。继续正常只读排查，不因交接失败建立新占用、重启 Codex、更新插件或触发业务保存。

MCP 响应外层的 `trace_id`、`total_elapsed_ms`、`timings` 仅用于性能诊断；数据库读取及交接阶段均记录耗时，失败也保留已完成阶段。计时不属于设计证据，不参与交接指纹、计划或审批签名。日志只有阶段、耗时、数量和错误码。
