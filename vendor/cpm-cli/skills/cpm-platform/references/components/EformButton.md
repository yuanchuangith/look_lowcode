> 来源：schema-tools/components/EformButton/knowledge.md（同步于 2026-08-25）

# 按钮

> 组件 Key: `EformButton`

## 适用场景
触发表单操作，适用于提交、重置表单或执行自定义逻辑。

## 属性

> 公共属性（label、name、display）由系统自动注入。按钮为 void 类型，不需要 required 和 pattern。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| buttontype | `string` | `'submit'` | 按钮类型（`'submit'`、`'reset'`、`'custom'`） |
| buttonShowTyps | `string` | `'primary'` | 按钮样式（`'primary'`、`'default'`、`'dashed'`、`'text'`、`'link'`） |
| wapButtonShowTyps | `string` | `'solid'` | 移动端按钮样式（`'solid'`、`'outline'`、`'none'`） |
| buttonColorType | `string` | `'system'` | 颜色类型（`'system'`、`'custom'`） |
| buttonColor | `string` | | 自定义按钮颜色（buttonColorType='custom' 时可用） |
| icon | `ButtonIcon` | `{type: '', color: '#000', size: 14}` | 图标配置 |
| permissionBind | `string` | | 权限绑定 |

### buttontype 说明
- `'submit'` — 触发表单提交
- `'reset'` — 重置表单数据
- `'custom'` — 通过 onClick 事件执行自定义逻辑

### buttonShowTyps 说明
- `'primary'` — 主要按钮（蓝色填充）
- `'default'` — 默认按钮（白色填充带边框）
- `'dashed'` — 虚线按钮
- `'text'` — 文字按钮（无边框）
- `'link'` — 链接按钮

## 复杂类型定义（如有）
### ButtonIcon
```typescript
interface ButtonIcon {
  type: string;
  color: string;
  size: number;
}
```

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- buttontype='submit' 时点击触发整个表单提交
- buttontype='custom' 需要配合 onClick 事件使用
- buttonColorType='custom' 时使用 buttonColor 指定颜色
