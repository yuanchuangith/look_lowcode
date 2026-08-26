> 来源：schema-tools/components/Cascader/knowledge.md（同步于 2026-08-25）

# 级联组件

> 组件 Key: `Cascader`

## 适用场景

选择包含层次关系的数据，如省市区选择、组织架构选择、分类目录选择等。支持单选和多选模式，支持异步懒加载。

## 属性

> 公共属性（label、name、display、pattern、required）由系统自动注入。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| placeholder | `string` | `'请选择'` | 占位提示 |
| multiple | `boolean` | `false` | 是否多选 |
| allowClear | `boolean` | `true` | 是否允许清除 |
| targetLevel | `'leaf' \| 'any'` | `'leaf'` | 选取规则。`leaf` 仅可选最后一级，`any` 可选任意级 |
| showCheckedStrategy | `'SHOW_PARENT' \| 'SHOW_CHILD'` | `'SHOW_PARENT'` | 多选时显示规则 |
| configModalValue | `object` | `{ currentIdField: '', labelField: '', parentIdField: '' }` | 显示属性配置，包含字段映射关系 |
| storageMode | `'model' \| 'submodel'` | `'model'` | 数据存储模式 |
| childModelConfig | `boolean` | `false` | 是否启用子模型配置 |
| storageConfig | `object` | | 子模型存储配置，包含 business 和 tableData |
| disabled | `boolean` | `false` | 是否禁用组件 |
| readOnly | `boolean` | `false` | 是否只读模式 |
| value | `ReactText[]` | `[]` | 当前选中值，单选为一维路径数组，多选为二维路径数组 |

### configModalValue 结构

| 字段 | 类型 | 描述 |
|------|------|------|
| currentIdField | `string` | 当前节点 ID 属性 |
| labelField | `string` | 当前节点文本属性 |
| parentIdField | `string` | 父节点 ID 属性 |

### storageConfig 结构

| 字段 | 类型 | 描述 |
|------|------|------|
| business | `string` | 子模型标识 |
| tableData | `{ componentAttr: string; modelAttr: string }[]` | 字段映射关系数组 |

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 数据源通过设计器绑定数据集配置
- 选中值为路径数组，如 `['北京', '朝阳区']`
- 多选时值为二维路径数组
- 子模型存储时需配置 storageConfig
