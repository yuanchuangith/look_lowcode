> 来源：schema-tools/components/FormSiderLayout/knowledge.md（同步于 2026-08-25）

# 个性化布局

> 组件 Key: `FormSiderLayout`

## 适用场景
提供主内容区加侧边栏的两栏布局容器。适合需要侧边导航或辅助信息展示的页面。

## 属性

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| header | `SiderRegion` | | 顶栏区域配置 |
| left | `SiderRegion` | | 左侧栏配置 |
| right | `SiderRegion` | | 右侧栏配置 |
| content | `SiderRegion` | | 主内容区配置 |

### SiderRegion 结构

| 字段 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| isHide | boolean | false | 是否隐藏该区域 |
| isOpen | boolean | true | 是否展开该区域 |
| isShowIcon | boolean | true | 是否显示展开/收起图标 |
| isWidth | boolean | true | 是否启用宽度控制 |
| width | number | - | 区域宽度（px） |
| leftMaxWidth | number | 500 | 左侧栏最大宽度（仅 left 区域） |
| rightMaxWidth | number | 500 | 右侧栏最大宽度（仅 right 区域） |
| notData | object | {} | 空数据占位配置 |

## 放置规则
- ConfigContainer
- GxpCard（直接放置）

## 子组件
通过 `FormSiderLayout.LayoutColumn` 子组件放置内容：
- 主内容区：可放置各类字段和容器组件
- 侧边栏：可放置各类字段和容器组件

## 注意事项
- header 常设为 `{ isHide: true }` 隐藏顶栏
- left 和 right 可独立配置显隐和宽度
- x-decorator 固定为 `Container`，x-decorator-props 常见配置：`{ clickable: true, style: { height: "100%" } }`
- 实际 Schema 中不使用 siderPosition 属性，通过 left/right 区域的 isHide 控制侧边栏位置
