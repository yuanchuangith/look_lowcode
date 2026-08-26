> 来源：schema-tools/components/GxpCard/knowledge.md（同步于 2026-08-25）

# 区块

> 组件 Key: `GxpCard`

## 适用场景
以卡片形式划分页面区域的容器组件，可带标题和边框。适合将表单内容按业务模块分区展示。

## 属性

> 公共属性中的 `label` 即为卡片标题文本。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| showCardTitle | boolean | true | 是否显示卡片标题 |
| bordered | boolean | false | 是否显示边框 |
| hoverable | boolean | false | 是否启用悬停效果 |
| cardHidden | boolean | false | 是否隐藏卡片 |
| hiddenCard | boolean | false | 只读模式下是否隐藏卡片 |

## 放置规则
- ConfigContainer
- GridColumn
- FormTab.TabPane
- FormSiderLayout（主内容区或侧边栏）
- FormFreeLayout

## 子组件
可放置所有 field 类型组件和 container 类型组件（如 FormGrid、Space 等）。

## 注意事项
- `label` 设置卡片标题文本，如 `"请假信息"`
- showCardTitle 为 false 时隐藏标题栏
- bordered 为 false 时卡片无边框
- hiddenCard 为 true 时只读模式下整个卡片区域隐藏，常用于存放系统字段（org_id、creator_id 等）
