> 来源：schema-tools/components/Space/knowledge.md（同步于 2026-08-25）

# 占位

> 组件 Key: `Space`

## 适用场景
控制子组件之间间距和排列方向的容器。用于在一行或一列中排列多个组件并保持统一间距。

## 属性

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| direction | 'horizontal' \| 'vertical' | 'horizontal' | 排列方向 |
| size | 'small' \| 'middle' \| 'large' | 'middle' | 间距大小 |

## 放置规则
- GridColumn
- FormTab.TabPane
- FormCollapse（直接放置）
- GxpCard（直接放置）
- FormSiderLayout（主内容区或侧边栏）
- ConfigContainer

## 子组件
可放置所有 field 类型组件。

## 注意事项
- direction 为 horizontal 时子组件水平排列，vertical 时垂直排列
- size 控制子组件之间的间距大小
