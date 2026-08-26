> 来源：schema-tools/components/FormFreeLayout/knowledge.md（同步于 2026-08-25）

# 自由列

> 组件 Key: `FormFreeLayout`

## 适用场景
支持绝对定位的自由布局容器。适合需要自由拖放组件位置的表单设计场景，不依赖栅格系统。

## 属性

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| maxColumns | number | 1 | 每行最大列数 |

## 放置规则
- ConfigContainer
- GxpCard（直接放置）
- FormSiderLayout（主内容区或侧边栏）

## 子组件
可放置所有 field 类型组件和 container 类型组件。

## 注意事项
- 子组件使用绝对定位，可自由拖放到任意位置
- 适合不规则布局需求
- x-decorator 固定为 `Container`，x-decorator-props 常见配置：`{ clickable: true, deletable: false, className: "ConfigContainer-FormFreeLayout web" }`
