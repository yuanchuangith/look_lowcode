> 来源：schema-tools/components/EformTextArea/knowledge.md（同步于 2026-08-25）

# 文本框

> 组件 Key: `EformTextArea`

## 适用场景
多行文本输入，适用于备注说明、详细描述、意见反馈。
与 EformInput 区别：支持多行换行。
与 EformRichText 区别：纯文本，不支持富文本格式。

## 属性

> 工具自动补齐平台运行时字段（model/modelend/sourcetype），模型只需提供下方参数。
> 公共属性（label、name、display、pattern、required）由系统自动注入。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| rows | `number` | | 显示行数（常用 3 行备注、9 行长说明） |
| defaultValue | `string` | | 默认值 |
| placeholder | `string` | `'请输入内容'` | 占位提示 |
| maxLength | `number` | | 最大字数 |
| minLength | `number` | | 最小字数 |

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 自动过滤 Emoji 表情
- maxLength 在用户输入时自动限制
- minLength 在表单提交时验证
