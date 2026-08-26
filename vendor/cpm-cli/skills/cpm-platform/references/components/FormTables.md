> 来源：schema-tools/components/FormTables/knowledge.md（同步于 2026-08-25）

# 表格

> 组件 Key: `FormTables`

## 适用场景

在表单页面中嵌入的表格组件，用于展示和管理关联数据（如订单明细、物料清单等）。通常放在 GxpCard 内部，作为表单的一部分。

与智能表格（GxpSmartTables）区别：支持子表格（展开行）和行内编辑，但不支持视图管理。

## 属性

> 工具会自动补齐平台运行时字段（id、authority、queryFields、subForm、dbName、dbType、sourcetype、primaryKey 等），**模型只需提供下方「关键参数」和 columnConfig 的设计意图**。

### 关键参数

| 名称 | 类型 | 默认值 | 何时设置 |
|------|------|--------|----------|
| modelname | `string` | | 绑定的数据模型表名（如 `gxp_record_box`）。必填，否则表格无数据源 |
| columnConfig | 见下方 | | 列与操作按钮配置，**核心设计意图** |
| selectionMode | `'close' \| 'multiple' \| 'single'` | `'close'` | 需要选中行时设 |
| paging | `boolean` | `false` | 数据量大需分页时设 `true` |
| autoLoad | `boolean` | `false` | 进入页面立即加载数据时设 `true` |
| height | `number` | `400` | 固定表格高度（px）；`autoHeight:true` 时自适应 |

### 其余参数（有默认值，无明确需求不用设）

| 名称 | 默认值 | 说明 |
|------|--------|------|
| dataFilter / subTable | `false` | 数据过滤 / 是否子表 |
| autoHeight / autoWrap | `false` | 自适应高度 / 自动换行 |
| modelkey | | 模型 GUID，通常由 DataCenter 自动赋值，模型不必填 |

## columnConfig（核心）

模型只需给出 `columns`（列）和 `operations`（操作按钮）的设计意图，工具自动补齐 id/authority/dbName 等平台字段。

```json
{
  "columnConfig": {
    "columns": [
      { "attributeName": "box_no", "title": "盒号", "width": 120, "formatType": "text" },
      { "attributeName": "state", "title": "状态", "formatType": { "type": "switch", "openValue": "1", "closeValue": "0" } }
    ],
    "operations": [
      { "type": "add", "title": "新增", "pageInfo": "page/modelKey,pageId,页面名" },
      { "type": "delete" }
    ]
  }
}
```

### 列定义（columns 元素）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| attributeName | `string` | 是 | 绑定的模型字段名 |
| title | `string` | 是 | 列标题 |
| formatType | 见下 | 否 | **列渲染方式（模型设计决策）**，不设默认按文本渲染 |
| width | `number` | 否 | 列宽（px），默认 150 |
| quickSearch | `boolean` | 否 | 是否支持快速搜索 |
| freeze | `boolean` | 否 | 是否冻结列 |
| show | `boolean` | 否 | 是否显示，默认显示 |

### formatType（列渲染方式）

这是模型要为每列决定的核心字段——同一列数据用不同方式渲染，效果完全不同。取值：

| formatType | 含义 | 示例 |
|------------|------|------|
| `"text"` | 纯文本（默认） | `"text"` |
| `"date"` | 日期 | `"date"` |
| `"number"` | 数字 | `"number"` |
| `{ "type": "switch", "openValue": "1", "closeValue": "0" }` | 开关列（0/1 转 开/关） | 状态列 |
| `{ "type": "button", "pageInfo": "...", "pageParameter": ["id"], "openType": "modal" }` | 可点击跳转列 | 名称列点击打开详情 |
| `{ "type": "staticList", "relatedDictionary": "<字典GUID>" }` | 字典枚举显示 | 类型列显示中文名 |
| `{ "type": "member", "memberType": "user" }` | 人员显示 | 责任人列 |
| `{ "type": "model", "relatedModel": "...", "displayProperty": "..." }` | 关联模型显示 | 外键显示关联表字段 |

> 简单列用字符串（`"text"`/`"date"`），复杂渲染用对象。`pageInfo` 格式：`page/modelKey,pageId,页面名`。

### 操作按钮（operations 元素）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | `'add' \| 'edit' \| 'delete' \| 'view' \| 'export' \| 'custom'` | 是 | 按钮类型 |
| title | `string` | 否 | 按钮名称，不设时按 type 取默认（新增/编辑/删除...） |
| position | `'top' \| 'row'` | 否 | 顶部工具栏 / 行内，默认 `top` |
| pageInfo | `string` | 否 | add/edit/view 跳转目标页面，格式 `page/modelKey,pageId,页面名` |
| openType | `'modal' \| 'tab' \| 'newPage'` | 否 | 打开方式 |
| action | `string` | 否 | custom 类型的动作标识（如 `custom_1`） |

> add/edit 按钮的子页面按钮（保存/取消）由工具自动补齐，无需配置。

## 放置规则

- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 数据源通过 DataCenter 绑定，`modelname` 是模型该提供的唯一数据源标识；`modelkey`（GUID）通常由 DataCenter 自动赋值。
- 主键默认 `id`，平台自动处理，模型无需配置。
- 工具自动补齐的平台字段：列的 `id`/`authority`/`dbName`/`dbType`、`queryFields`（字段镜像）、`subForm`（按钮汇总）、`sourcetype`/`primaryKey` —— **模型不要手写这些**。
