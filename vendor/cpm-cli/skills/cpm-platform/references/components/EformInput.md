> 来源：schema-tools/components/EformInput/knowledge.md（同步于 2026-08-25）

# 输入框

> 组件 Key: `EformInput`

## 适用场景

单行文本输入，适用于用户名、编号、标题等短文本。
与 EformTextArea 区别：单行，不换行。
与 EformText 区别：可编辑，非纯展示。

## 属性

> 工具自动补齐平台运行时字段（model/modelend/sourcetype），模型只需提供下方参数。
> 公共属性（label、name、display、pattern、required）由系统自动注入。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| type | `'text' \| 'password'` | `'text'` | 输入类型，密码场景设 `password` |
| defaultValue | `string` | | 默认值 |
| placeholder | `string` | `'请输入'` | 占位提示 |
| addonAfter | `string` | | 行内单位，如 `"元"`、`"kg"` |
| minLength | `number` | | 最小字数 |
| maxLength | `number` | | 最大字数 |

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 自动过滤 Emoji 表情
- maxLength 在用户输入时自动限制，minLength 在表单提交时验证
