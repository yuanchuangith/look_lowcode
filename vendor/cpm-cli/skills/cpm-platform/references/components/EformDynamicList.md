> 来源：schema-tools/components/EformDynamicList/knowledge.md（同步于 2026-08-25）

# 动态列表

> 组件 Key: `EformDynamicList`

## 适用场景

以下拉弹窗表格的形式从数据集中选择一条或多条记录。适用于需要从大量动态数据中进行选择的场景，如选择员工、选择产品等。

与静态列表（EformStaticList）区别：数据来自数据集（DataCenter）动态查询，支持搜索和分页。

## 属性

> 工具自动补齐平台运行时字段（model/modelend/sourcetype），数据源绑定（dataCenter/modelkey）由平台 DataCenter 完成。
> 公共属性（label、name、display、pattern、required）由系统自动注入。

### 关键参数

| 名称 | 类型 | 默认值 | 何时设置 |
|------|------|--------|----------|
| selectType | `boolean` | `false` | 是否多选 |
| showconfig | `ShowConfig` | | 显示配置：绑哪个模型、显示/存储哪些字段。**核心设计意图** |
| modelname | `string` | | 数据模型表名（数据源） |
| search | `boolean` | `false` | 是否启用搜索 |

### 其余参数（有默认值，无明确需求不用设）

| 名称 | 默认值 | 说明 |
|------|--------|------|
| placeholder | `'请选择'` | 占位提示 |
| autoLoading | `true` | 自动加载数据 |
| defaultValue | | 默认值 |

## showconfig（核心）

模型只需给出要显示的列和存储字段，工具补齐平台运行时字段。

```json
{
  "showconfig": {
    "modelName": "gxp_archive_info",
    "storageField": "archive_info_id",
    "selectName": ["archive_name"],
    "pageSize": 5,
    "list": [
      { "Text": "档案名称", "Value": "archive_name", "dbName": "gxp_archive_info.archive_name" }
    ]
  }
}
```

### showconfig 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| modelName | `string` | 是 | 关联的数据模型名称 |
| storageField | `string` | 是 | 存储字段（选中后写入哪个字段） |
| selectName | `string[]` | 否 | 显示字段名称数组 |
| pageSize | `number` | 否 | 分页每页条数，默认 5 |
| list | `ShowConfigItem[]` | 否 | 表格列配置 |

### ShowConfigItem（列定义）

| 字段 | 类型 | 说明 |
|------|------|------|
| Text | `string` | 列标题 |
| Value | `string` | 字段值/别名 |
| dbName | `string` | 数据库字段名（模型.字段） |
| Width | `string \| number` | 列宽 |
| SelectText | `string` | 是否为查询字段 |

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 数据源通过数据集（DataCenter）绑定，modelkey（GUID）由平台自动赋值。
- 下拉面板以表格形式展示数据，支持搜索和分页。
- 选中值以逗号分隔的字符串存储。
- 工具自动补齐的平台字段：model/modelend/sourcetype/dataCenter/modelkey —— **模型不要手写这些**。
