> 来源：schema-tools/components/Transfer/knowledge.md（同步于 2026-08-25）

# 穿梭框

> 组件 Key: `Transfer`

## 适用场景

以穿梭框的形式在"待选"和"已选"两个列表之间移动数据项。支持列表和树形两种数据展示类型。适用于人员选择、权限分配、数据分类等场景。

## 属性

> 公共属性（label、name、display、pattern、required）由系统自动注入。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| leftTitle | `string` | `'待选列表'` | 待选框标题 |
| rightTitle | `string` | `'已选列表'` | 已选框标题 |
| showSearch | `boolean` | `false` | 是否显示搜索框 |
| showPagination | `boolean` | `false` | 是否显示分页器 |
| pageSize | `number` | `10` | 每页显示条数 |
| configModalValue | `IConfigModalValue` | | 显示属性配置，包含数据类型、字段映射等 |
| childModelConfig | `boolean` | | 子模型配置开关，开启后数据以子表多条记录形式存储 |
| storageConfig | `StorageConfig` | | 存储配置，仅在开启子模型配置时可见 |
| type | `'list' \| 'tree'` | `'list'` | 数据展示类型。`list` 列表/表格模式，`tree` 树形模式 |
| currentIdField | `string` | | 当前节点 ID 属性，每条数据的唯一键 |
| parentIdField | `string` | | 父节点 ID 属性，树形模式下构建层级关系 |
| labelField | `string` | | 当前节点文本属性，显示的文本字段 |
| searchKey | `string` | | 搜索属性，搜索时匹配的字段名 |
| fieldOptions | `FieldOption[]` | `[]` | 列表模式下的列配置 |
| business | `string` | | 业务模型标识 |
| tableData | `TableDataMapping[]` | | 组件属性与模型属性的映射配置 |

### IConfigModalValue 结构

| 字段 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| type | `'list' \| 'tree'` | `'list'` | 数据展示类型 |
| currentIdField | `string` | `''` | 当前节点 ID 属性 |
| parentIdField | `string` | `''` | 父节点 ID 属性 |
| labelField | `string` | `''` | 当前节点文本属性 |
| searchKey | `string` | `''` | 搜索属性 |
| fieldOptions | `FieldOption[]` | `[]` | 列配置 |

### FieldOption 结构

| 字段 | 类型 | 描述 |
|------|------|------|
| key | `number` | 列序号 |
| field | `string` | 字段名 |
| label | `string` | 列标题 |

### StorageConfig 结构

| 字段 | 类型 | 描述 |
|------|------|------|
| business | `string` | 业务模型标识 |
| tableData | `TableDataMapping[]` | 字段映射配置 |

### TableDataMapping 结构

| 字段 | 类型 | 描述 |
|------|------|------|
| componentAttr | `string` | 组件属性名 |
| modelAttr | `string` | 模型属性名 |

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 数据源通过设计器绑定数据集配置
- 支持列表和树形两种数据展示类型
- 选中值以逗号分隔的字符串存储
- fieldOptions 中配置 1 条为简单列表，多条为表格形式
