> 来源：schema-tools/components/TreeSelect/knowledge.md（同步于 2026-08-25）

# 下拉树列表

> 组件 Key: `TreeSelect`

## 适用场景

以树形结构进行下拉选择数据。支持下拉面板内搜索过滤、单选/多选模式。适用于组织架构选择、分类选择等需要从层级结构数据中进行选择的场景。

## 属性

> 工具自动补齐平台运行时字段（model/modelend/sourcetype/businessData），数据源绑定（config/querySet/dataCenter/modelkey）由平台 DataCenter 完成。
> 公共属性（label、name、display、pattern、required）由系统自动注入。

### 关键参数

| 名称 | 类型 | 默认值 | 何时设置 |
|------|------|--------|----------|
| multiple | `boolean` | `false` | 是否多选 |
| modelname | `string` | | 数据模型表名（树数据源） |
| config | `object` | | 树构建配置：含 fieldRelation（id/parentId/label 字段映射）。**核心设计意图** |

### 其余参数（有默认值，无明确需求不用设）

| 名称 | 默认值 | 说明 |
|------|--------|------|
| showSearch | `true` | 是否支持搜索 |
| expandNode | `false` | 是否默认展开所有节点 |
| showIcon | `false` | 是否显示节点图标 |
| placeholder | `'请选择'` | 占位提示 |

## config（树构建核心）

树怎么构建由 config.fieldRelation 决定——它定义 id 字段、父 id 字段、显示字段。

```json
{
  "config": {
    "fieldRelation": {
      "id": "dept_id",
      "parentId": "parent_id",
      "label": "dept_name"
    }
  }
}
```

> config 内部的 querySet（数据集查询）、Icons_settings（图标）等由平台自动生成，模型只需给 fieldRelation。

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 数据源通过数据集（DataCenter）绑定，modelkey（GUID）由平台自动赋值。
- 多选模式下显示勾选框，父子节点选中状态互不影响。
- 搜索时保留匹配节点及其所有父节点。
- 工具自动补齐的平台字段：model/modelend/sourcetype/dataCenter/businessData —— **模型不要手写这些**。
