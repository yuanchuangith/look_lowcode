> 来源：schema-tools/components/Tree/knowledge.md（同步于 2026-08-25）

# 树形

> 组件 Key: `Tree`

## 适用场景

以树结构展示层级数据，支持懒加载子节点、单选/多选模式、搜索过滤、拖拽排序。适用于组织架构展示、分类导航、文件目录等场景。

## 属性

> 工具自动补齐平台运行时字段（model/modelend/sourcetype/businessData），数据源绑定（config/querySet/dataCenter/modelkey）由平台 DataCenter 完成。
> 公共属性（label、name、display、pattern、required）由系统自动注入。

### 关键参数

| 名称 | 类型 | 默认值 | 何时设置 |
|------|------|--------|----------|
| modelname | `string` | | 数据模型表名（树数据源） |
| config | `object` | | 树构建配置：含 fieldRelation（id/parentId/label 字段映射）+ operations（操作按钮）。**核心设计意图** |
| checkable | `boolean` | `false` | 是否启用多选（勾选框）模式 |
| search | `boolean` | `false` | 是否显示搜索框 |

### 其余参数（有默认值，无明确需求不用设）

| 名称 | 默认值 | 说明 |
|------|--------|------|
| checkStrictly | `false` | 多选时父子节点是否独立选择 |
| expandNode | `false` | 是否默认展开第一个根节点 |
| autoLoad | `true` | 是否自动加载数据 |
| showIcon | `false` | 是否显示节点图标 |
| draggable | `false` | 是否启用拖拽 |

## config（树构建核心）

树怎么构建由 config.fieldRelation 决定，操作按钮由 config.operations 决定。

```json
{
  "config": {
    "fieldRelation": {
      "id": "dept_id",
      "parentId": "parent_id",
      "label": "dept_name"
    },
    "operations": [
      { "type": "add", "title": "新增" },
      { "type": "delete" }
    ]
  }
}
```

> config 内部的 querySet（数据集查询）、Icons_settings（图标）、formItems（弹窗尺寸）、statusSetting（节点状态）等由平台自动生成，模型只需给 fieldRelation 和 operations。

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 数据源通过数据集（DataCenter）绑定，modelkey（GUID）由平台自动赋值。
- 开启 checkable 多选模式时搜索功能不可用。
- 拖拽功能需通过事件回调实现具体业务逻辑。
- 工具自动补齐的平台字段：model/modelend/sourcetype/dataCenter/businessData —— **模型不要手写这些**。
