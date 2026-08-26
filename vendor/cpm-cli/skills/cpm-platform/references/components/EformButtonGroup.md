> 来源：schema-tools/components/EformButtonGroup/knowledge.md（同步于 2026-08-25）

# 按钮组

> 组件 Key: `EformButtonGroup`

## 适用场景
多个操作按钮的集中管理，适用于表单操作按钮集合、弹窗操作。
与 EformButton 区别：管理多个按钮，支持平铺和下拉两种布局。

## 属性

> 公共属性（label、name、display）由系统自动注入。按钮组为 void 类型，不需要 required 和 pattern。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| buttonType | `string` | `'drop-down'` | 布局方式（`'tile'`、`'drop-down'`） |
| config | `object` | | 子窗体和操作配置 |
| icon | `ButtonGroupIcon` | `{type: 'icon-ic-arrow-down-bold'}` | 图标配置 |
| iconPosition | `string` | `'left'` | 图标位置（`'left'`、`'right'`） |
| buttonLayout | `string` | `'center'` | 按钮对齐方式（`'center'`、`'left'`、`'right'`） |
| buttonSpace | `number` | | 按钮间距（px） |

### buttonType 说明
- `'tile'` — 平铺，按钮水平排列显示
- `'drop-down'` — 下拉，按钮收纳在下拉菜单中

### buttonLayout 说明
- `'center'` — 居中对齐
- `'left'` — 左对齐
- `'right'` — 右对齐

## 复杂类型定义（如有）
### ButtonGroupIcon
```typescript
interface ButtonGroupIcon {
  type: string;
}
```

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 按钮组支持子窗体弹窗操作（新增、编辑等）
- 支持动态控制按钮状态（禁用、危险样式等）
