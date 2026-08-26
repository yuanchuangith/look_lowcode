# GXP 低代码平台映射

## 动作身份

| 动作类型 | 元数据表 | 编号 | 名称 | RefId |
| --- | --- | --- | --- | --- |
| 公共动作 | `cpm_public_flows` | `code` | `name` | `id` |
| 表单动作 | `cpm_bizflows` | `code` | `describe` | `id` |

表单动作通过 `page_id -> inbiz_page.Route/OutId/Id` 取得页面，再通过 `inbiz_language` 取得中文页面名。

动作编号可由数字开头，例如 `24qf4ene`。只有业务名称时使用 `search_actions`；多结果必须按动作类型、code、RefId、页面 ID 和名称消歧。

```text
动作 code 或 RefId
  -> cpm_public_flows / cpm_bizflows
  -> 动作 id
  -> cpm_bizflows_design.ref_Id
  -> data.actionData[] / csharp_code
```

## 同一动作的两个当前副本

| 副本 | 常见标记 | 作用 | 编辑是否影响运行 |
| --- | --- | --- | --- |
| 发布副本 | `is_publish=1 AND isDeleted=0` | 当前运行配置 | 发布操作才更新 |
| 草稿副本 | `is_publish=0 AND isDeleted=0` | 发布副本的可编辑副本 | 否 |

- 发布后两个副本通常重新同步。
- 保存草稿后内容可以暂时不同，此时状态是 `存在未发布草稿改动`，但运行仍使用发布副本。
- 哈希一致只说明副本内容相同，不说明业务逻辑正确或运行成功。
- 旧发布通常以 `is_publish=1 AND isDeleted=1` 保留，是过去运行过的发布快照，不是当前第三个运行副本。
- 历史草稿不得作为线上运行异常证据。

## 历史时间规则

- 发布快照以 `creationTime/created_time` 作为发布时间；缺失时才退回修改时间。
- 草稿当前内容以 `lastModificationTime/modified_time` 判断保存时间。
- 有异常时间时，只检查该时间及以前最新的发布快照。
- 异常候选与当前同步检查分开：前者读取历史发布，后者只比较当前发布与当前草稿。

## 画布坐标

```text
actionData[]
  key/title                 动作分组
  data[]                    有序画布节点
    key/title/elementKey    节点定位
    depth[]                 父级 IF/循环 Key
    paramsValue             条件、映射、变量和调用参数
```

- 画布行号 = 当前分组 `data[]` 内部索引 + 1。
- 内部索引从 0 开始。
- 生成 C# 行号独立计算，不能称为画布行。
- 新增/删除节点会使后续画布行变化，因此节点 Key 是复核时的稳定定位主键。
- `description` 可能丢失嵌套 OR、类型和完整表达式；以 `paramsValue` 为准。

## 节点指纹

| 节点 | 必查内容 |
| --- | --- |
| `SelectData` | 表、嵌套 WHERE、输出变量 |
| `AddNewData` | 表、每个字段映射、来源表达式 |
| `UpdateData` | 表、更新映射、完整 WHERE |
| `IfCondition` | 完整条件、逻辑组和父级路径 |
| `ForEachArray` / `ForEachDynamicArray` | 集合、当前项、索引 |
| `SetVariable` / `SetVariableValue` | 变量类型、变量名和表达式 |
| `CallPublicAction` | 动作 code/RefId、名称、完整入参 |
| `CallAction` | 当前设计分组和完整入参 |

已知字段名时给 `inspect_action.focus_fields`。`field_evidence` 返回节点定位和精确字段匹配；`node_generated_csharp_evidence` 返回与节点关联的 C# 关键词命中候选。关键词候选不是编译器 Source Map。

## 只读查询顺序

1. 优先 `diagnose_codex_input`、`resolve_action`、`search_actions`、`get_design_versions`、`inspect_action`。
2. 业务表先 `describe_table`，再用 `get_records` 的索引等值过滤。
3. 仅在前两者不能表达时使用 `readonly_sql`，并限制为单条、窄条件、最小列集。
4. 不执行数据库、设计、保存或发布写入。

兼容读取 ActionDesign 时，只读取目标 RefId 的当前副本或指定历史发布快照；不要回显整份长 JSON。若需哈希，可读取 `SHA2(data,256)` 与 `SHA2(csharp_code,256)`。
