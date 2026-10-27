# GXP 低代码平台映射

动作身份、坐标与副本语义用于普通定位；保存／发布复核、动态异常和生产取证按本文对应章节读取。输出格式统一见 [report-contract.md](report-contract.md)。

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

`exact_source_map=false` 时不得称为编译器级精确映射。异常栈直接给出的 C# 行是精确行，仍须结合发布设计 ID、时间、目标行、相邻行和画布节点判断归属。仅在当前设计与明确失败机制同时成立时定为 Bug，缺证据则标“候选”或“待运行验证”。

## 保存、发布和异常复核

| 用户输入 | 取证顺序 | 结论边界 |
| --- | --- | --- |
| “修改了／保存了” | 重读当前草稿与发布，检查草稿目标完整参数及生成 C# 候选 | 明确发布同步状态；草稿修复不代表线上生效 |
| “发布了” | 重读当前发布并定位目标，再比较当前草稿与发布 | 哈希同步后仍核对节点；没有真实样本则未执行运行验证 |
| 动态异常 | `trace_dynamic_exception`，有时间必须传 `at_time`；只接受该时点及以前最新发布快照 | 独立比较当前草稿与当前发布，不与历史发布混比 |

动态异常区分当前发布问题、历史发布问题、未发布草稿修复及旧任务继续执行旧快照。过滤／异常摘要和候选续读见 [diagnostic-output.md](diagnostic-output.md)。

## 生产环境数据按批取证

当前连接默认按开发环境理解，只有用户明确说明当前连接环境才覆盖。用户描述生产／正式／线上问题，不能据此把开发数据重标为生产数据。

1. 当前连接未确认为目标生产时，先用已有本地 Schema、动作及源码缩小范围。确需生产数据时，说明缺什么、为何需要，请用户在生产执行一批只读 SQL 并返回结果；不以开发数据代替生产验证。
2. 一次给齐本阶段已明确需要的全部查询，不明知还有同阶段数据却逐条追加；不要求预先穷尽后续所有可能查询。
3. 每批编号，每条标用途，提供完整可执行 SQL、共用参数和应返回的结果。复用已提供 ID、业务编号、时间范围；必要缺参集中列明，不猜值。可由关联／子查询取得的键在本批取出，不让用户逐条接力。
4. 仅使用已核对表／字段，遵守只读边界，以业务锚点、小列集、合理 limit 限量。生产结构有疑问时将结构核对并入本批；无法确定的字段先取结构，不凭开发结构断言生产一致。
5. 请用户按编号保留空结果、报错和截断说明。收到后复用证据继续分析，仅对新缺口给下一批并说明目的；等待期间继续独立排查，证据补齐前生产结论标待验证。

## 只读查询顺序

1. 优先 `diagnose_codex_input`、`resolve_action`、`search_actions`、`get_design_versions`、`inspect_action`。
2. 业务表先 `describe_table`，再用 `get_records` 的索引等值过滤。
3. 仅在前两者不能表达时使用 `readonly_sql`，并限制为单条、窄条件、最小列集。
4. 不执行数据库、设计、保存或发布写入。

兼容读取 ActionDesign 时，只读取目标 RefId 的当前副本或指定历史发布快照；不要回显整份长 JSON。若需哈希，可读取 `SHA2(data,256)` 与 `SHA2(csharp_code,256)`。
