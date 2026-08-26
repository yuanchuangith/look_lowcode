> 来源：schema-tools/components/FormGrid/knowledge.md（同步于 2026-08-25）

# 网格布局

> 组件 Key: `FormGrid`

## 适用场景
使用栅格方式对表单字段进行布局的容器组件。将页面区域划分为若干列，可嵌套 GridColumn 网格列来精确控制每一行显示哪些字段。

## 属性

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| colWrap | boolean | `true` | 是否自动换行 |
| maxColumns | number | `12` | 最大列数 |
| minColumns | number | `12` | 最小列数 |

## 放置规则
- FormGrid（嵌套）
- FormTab.TabPane
- FormCollapse（直接放置）
- GxpCard（直接放置）
- FormSiderLayout（主内容区或侧边栏）
- FormFreeLayout
- ConfigContainer

## 子组件
- GridColumn（必须嵌套网格列才能放置字段组件）

## 注意事项
- 网格布局需要嵌套 GridColumn 使用，每个 GridColumn 包含一行中的字段
- maxColumns 和 minColumns 通常设为相同值（12列）
- x-decorator 固定为 `Container`，x-decorator-props 常见配置：`{ className: "FormGridContainer web" }`
- x-decorator-props.style 中可配置 `margin: "auto"` 居中
