> 来源：schema-tools/components/FormCollapse/knowledge.md（同步于 2026-08-25）

# 折叠面板

> 组件 Key: `FormCollapse`

## 适用场景
将表单内容分区到可折叠面板中展示的容器组件。适合内容较多、不需要同时展示所有区域的表单。

## 属性

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| panels | string[] | ['面板1'] | 面板名称列表 |
| accordion | boolean | - | 是否开启手风琴模式（每次只展开一个面板） |
| ghost | boolean | - | 是否开启透明无边框模式 |

## 放置规则
- ConfigContainer
- GxpCard（直接放置）
- FormSiderLayout（主内容区或侧边栏）

## 子组件
每个面板内可放置各类字段和容器组件。

## 注意事项
- panels 数组中每个字符串会自动创建一个可折叠面板区域
- 手风琴模式下同时只能展开一个面板
- ghost 模式下面板无边框和背景色
