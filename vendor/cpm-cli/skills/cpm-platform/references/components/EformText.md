> 来源：schema-tools/components/EformText/knowledge.md（同步于 2026-08-25）

# 文本

> 组件 Key: `EformText`

## 适用场景
纯文本展示，适用于说明文字、提示信息、状态展示。
与 EformInput 区别：纯展示，不支持用户输入。
与 EformTextArea 区别：非输入组件，只读展示。

## 属性

> 公共属性（label、name、display、pattern）由系统自动注入。文本为展示组件，不需要 required。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| content | `string` | | 文本内容 |
| type | `string` | `'default'` | 文本样式（`'default'`、`'secondary'`、`'warning'`、`'danger'`） |
| ellipsis | `boolean` | `false` | 是否省略超出内容 |
| underline | `boolean` | `false` | 是否显示下划线 |

### type 样式说明
- `'default'` — 默认样式
- `'secondary'` — 次要信息样式
- `'warning'` — 警告提示样式
- `'danger'` — 异常错误样式

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 纯展示组件，不支持用户输入
- ellipsis=true 时文本过长自动省略并显示省略号
- underline=true 为文本添加下划线装饰
