> 来源：schema-tools/components/EformRichText/knowledge.md（同步于 2026-08-25）

# 富文本框

> 组件 Key: `EformRichText`

## 适用场景
富文本编辑，适用于文章编辑、公告编辑、图文混排。
与 EformTextArea 区别：支持格式化文本、图片等富文本内容。

## 属性

> 公共属性（label、name、display、pattern、required）由系统自动注入。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| defaultValue | `string` | | 默认值（HTML 格式） |
| placeholder | `string` | `'请输入内容'` | 占位提示 |
| tooltype | `string` | `'标准'` | 工具栏类型（`'标准'`、`'简洁'`、`'自定义'`） |
| toolbar | `ToolbarConfig` | | 自定义工具栏配置（tooltype='自定义' 时生效） |

## 复杂类型定义（如有）
### ToolbarConfig
```typescript
interface ToolbarConfig {
  menu: any[];
  toolbar: any[];
}
```

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 基于 TinyMCE 实现
- tooltype='自定义' 时可配置自定义工具栏
- tooltype='简洁' 仅提供常用编辑工具
