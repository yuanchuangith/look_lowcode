> 来源：schema-tools/components/FormTab/knowledge.md（同步于 2026-08-25）

# 选项卡

> 组件 Key: `FormTab`

## 适用场景
将表单内容分区到不同标签页中展示的容器组件。适合字段较多、需要分类管理的复杂表单。

## 属性

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| tabs | string[] | ['标签页1'] | 标签页名称列表 |
| clickable | boolean | true | 是否可点击切换标签页 |

## 放置规则
- ConfigContainer
- GxpCard（直接放置）
- FormSiderLayout（主内容区或侧边栏）

## 子组件
- FormTab.TabPane（每个标签页对应一个 TabPane）

## 注意事项
- tabs 数组中每个字符串会自动创建一个 TabPane
- TabPane 内可放置各类字段和容器组件
- clickable 控制标签页是否可通过点击切换
