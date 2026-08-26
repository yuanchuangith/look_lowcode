> 来源：schema-tools/components/ConfigContainer/knowledge.md（同步于 2026-08-25）

# 页面布局

> 组件 Key: `ConfigContainer`

## 适用场景
表单页面的顶层容器组件。每个表单页面最外层必须使用 ConfigContainer 包裹，用于统一管理页面内所有组件的布局和配置。

## 属性
> 该组件无特殊属性，作为顶层容器使用。

## 放置规则
- 作为最顶层容器使用，不嵌套在其他容器内

## 子组件
可放置所有 container 类型组件（如 FormGrid、FormTab、GxpCard、Space 等）和 field 类型组件。

## 注意事项
- 每个表单页面有且仅有一个 ConfigContainer 作为根节点
- 不要在其他容器内部嵌套 ConfigContainer
