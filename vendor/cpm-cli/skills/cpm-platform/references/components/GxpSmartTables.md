> 来源：schema-tools/components/GxpSmartTables/knowledge.md（同步于 2026-08-25）

# 智能表格

> 组件 Key: `GxpSmartTables`

## 适用场景

独立的页面级数据表格，支持视图管理（保存、切换视图）、多条件筛选、多列排序、列隐藏/冻结、行级高亮、数据导出。采用虚拟滚动技术，适合大数据量场景。

与表格（FormTables）区别：支持视图管理和多条件筛选，但不支持子表格展开和行内编辑。

## 属性

> 工具会自动补齐平台运行时字段（id、authority、queryFields、subForm、dbName、dbType、sourcetype、primaryKey 等），**模型只需提供下方「关键参数」和 columnConfig 的设计意图**。

### 关键参数

| 名称 | 类型 | 默认值 | 何时设置 |
|------|------|--------|----------|
| modelname | `string` | | 绑定的数据模型表名（如 `gxp_archive_info`）。必填，否则表格无数据源 |
| columnConfig | 见下方 | | 列与操作按钮配置，**核心设计意图** |
| selectionMode | `'close' \| 'multiple' \| 'single'` | `'close'` | 需要选中行时设 |
| paging | `boolean` | `false` | 数据量大需分页时设 `true` |
| autoLoad | `boolean` | `false` | 进入页面立即加载数据时设 `true` |
| dataFilter | `boolean` | `false` | 需要多条件筛选时设 `true` |

### 其余参数（有默认值，无明确需求不用设）

| 名称 | 默认值 | 说明 |
|------|--------|------|
| isCollapsed | `false` | 是否折叠左侧视图面板 |
| modelkey | | 模型 GUID，通常由 DataCenter 自动赋值，模型不必填 |

## columnConfig（核心）

模型只需给出 `columns`（列）、`operations`（操作按钮）和可选的 `sort`（排序），工具自动补齐 id/authority/dbName 等平台字段。

```json
{
  "columnConfig": {
    "columns": [
      { "attributeName": "archive_name", "title": "档案名称", "formatType": { "type": "button", "pageInfo": "page/modelKey,pageId,档案信息", "pageParameter": ["id"], "openType": "modal" } },
      { "attributeName": "expire_date", "title": "到期日期", "formatType": "date" },
      { "attributeName": "state", "title": "状态", "formatType": { "type": "staticList", "relatedDictionary": "<字典GUID>" } }
    ],
    "operations": [
      { "type": "custom", "title": "打印", "action": "custom_1" },
      { "type": "export" }
    ],
    "sort": [{ "field": "expire_date", "order": "desc" }]
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
| `{ "type": "button", "pageInfo": "...", "pageParameter": ["id"], "openType": "modal" }` | 可点击跳转列 | 名称列点击打开详情 |
| `{ "type": "staticList", "relatedDictionary": "<字典GUID>" }` | 字典枚举显示 | 类型列显示中文名 |
| `{ "type": "switch", "openValue": "1", "closeValue": "0" }` | 开关列 | 状态列 |
| `{ "type": "member", "memberType": "user" }` | 人员显示 | 责任人列 |
| `{ "type": "model", "relatedModel": "...", "displayProperty": "..." }` | 关联模型显示 | 外键显示关联表字段 |
| `{ "type": "json", "expression": "${[].label}", "separator": "\\n" }` | 动态字段 JSON 渲染 | 复合字段 |

> 简单列用字符串（`"text"`/`"date"`），复杂渲染用对象。`pageInfo` 格式：`page/modelKey,pageId,页面名`。

### 操作按钮（operations 元素）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | `'add' \| 'edit' \| 'delete' \| 'view' \| 'export' \| 'custom'` | 是 | 按钮类型 |
| title | `string` | 否 | 按钮名称，不设时按 type 取默认 |
| position | `'top' \| 'row'` | 否 | 顶部工具栏 / 行内，默认 `top` |
| pageInfo | `string` | 否 | 跳转目标页面，格式 `page/modelKey,pageId,页面名` |
| openType | `'modal' \| 'tab' \| 'newPage'` | 否 | 打开方式 |
| action | `string` | 否 | custom 类型的动作标识（如 `custom_1`、`barcodePrint`、`print`） |

> add/edit 按钮的子页面按钮（保存/取消）由工具自动补齐，无需配置。

### sort（排序）

```json
"sort": [{ "field": "expire_date", "order": "desc" }]
```

| 字段 | 类型 | 说明 |
|------|------|------|
| field | `string` | 排序字段名（模型字段） |
| order | `'asc' \| 'desc'` | 升序 / 降序 |

可多列排序，数组顺序即优先级。

## 放置规则

- 页面根节点（直接放置）

## 注意事项

- 数据源仅支持 DataCenter 类型；`modelname` 是模型该提供的唯一数据源标识，`modelkey`（GUID）通常由 DataCenter 自动赋值。
- 默认启用双向虚拟滚动；分页模式（paging=true）使用分页加载，否则使用滚动加载。
- 工具自动补齐的平台字段：列的 `id`/`authority`/`dbName`/`dbType`、`queryFields`（字段镜像）、`subForm`（按钮汇总）、`sourcetype`/`primaryKey` —— **模型不要手写这些**。
