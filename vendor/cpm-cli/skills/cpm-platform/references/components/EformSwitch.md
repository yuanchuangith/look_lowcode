> 来源：schema-tools/components/EformSwitch/knowledge.md（同步于 2026-08-25）

# 开关框

> 组件 Key: `EformSwitch`

## 适用场景
两种状态切换，如启用/禁用、是/否选择。
与 EformInput 区别：视觉化开关样式，对应布尔值。

## 属性

> 公共属性（label、name、display、pattern、required）由系统自动注入。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| defaultChecked | `boolean` | `false` | 默认值（true=开启/1，false=关闭/0） |
| checkedChildren | `string` | `'打开'` | 开启时显示的文字 |
| unCheckedChildren | `string` | `'关闭'` | 关闭时显示的文字 |

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 开启状态（checked=true）存储值为 1
- 关闭状态（checked=false）存储值为 0
- checkedChildren/unCheckedChildren 可自定义显示文字
