# 数据资源四模块（models / datasets / dictionaries / events）详解

页面绑定（bindings）引用的底层资源，四个目录各司其职：

| 目录 | 是什么 | 页面侧引用键 |
|------|--------|--------------|
| `models/` | 数据模型 = 物理表结构（含字段清单） | 页面 `form.model`（主模型）、bindings 主模型节 |
| `datasets/` | 数据集 = 预置查询（条件+返回列+JOIN） | 组件 `binding.dataSetId`（子表/下拉/表格类） |
| `dictionaries/` | 字典 = 枚举选项集 | 组件 `binding.dictId`（下拉/单选类） |
| `events/` | 平台级事件定义（订阅/触发） | bizflows 代码按 `eventCode` 订阅 |

各目录 README.md 均为索引表（条目 | 说明）。文件名 `中文名-短码.json`（短码 = code）。

## models/（表结构）

JSON 顶层：`key/name/code/comment/config/columns`。README 说明列 = **物理表名**（如 `gxp_dms_form`，gxp_ 前缀 + 应用缩写）。

`columns[]` 字段：

| 字段 | 语义 |
|------|------|
| `Name` / `OldName` | 列名 / 改名前旧列名 |
| `DataType` / `MapType` | 数据库类型（varchar…）/ 运行时类型（System.String…） |
| `Length` / `IsNullable` / `IsDefault` | 长度 / 可空 / 有默认值 |
| `IsPrimary` | 主键 |
| `Comment` | 列注释（**找业务字段含义的第一入口**） |

## datasets/（预置查询）

JSON 顶层：`id/name/code/model/dataSourceId/primaryKey/state/permissions/config`。`model` = 主物理表名；`config` 是查询定义：

- `condition[]`：过滤条件树——`Logic`（And/Or）+ `Filters[]`（`Field`=表.列、`Operator`（isnotnull/eq…）、`OperatorValue`）
- `queryFields[]`：返回列（`name`=表.列，可带 `alias`）
- `tables[]`：JOIN 的其它表；`sort[]`：排序

组件拿到的是 dataSetId（数据集 id）；数据集再决定查哪张表、怎么过滤——改「下拉/表格显示哪些数据」先看这里，再看模型字段。

## dictionaries/（枚举选项集）

JSON 顶层：`id/name/key/categoryId/code/children[]`。`children[]` 每项 `{key, value}`：`key` = **存储值**（落库内容，如 `offline`），`value` = **显示文本**（如「线下」）——代码/数据里见到怪值先查字典反向翻译。支持嵌套 children（树形字典）。

## events/（平台级事件）

JSON 顶层：`id/name/description/code/eventCode/eventType/enable/count`。`eventCode` 是代码订阅标识（如 `DocumentInvalid`），`description` 说明事件数据载荷（data 字段）；`eventType: "custom"` 为自定义事件。与页面 bizflows 的区别：events 是**跨页面**的平台事件定义，bizflows 是页面内事件逻辑。

## 典型查询路径

1. **组件数据从哪来**：`components.json` 该组件 `binding` → `dataSetId` 查 datasets/（或 `dictId` 查 dictionaries/）→ 数据集 `model`/`modeTable` 落到 models/ 看字段
2. **某表被哪些页面用**：`indexes/model-usage.md`（主模型）；数据集消费方见页面 bindings.md「数据集」节
3. **字段业务含义**：models JSON 的 `columns[].Comment`
4. **存储值 ↔ 显示文本**：dictionaries 的 `children[]` key/value 对照
