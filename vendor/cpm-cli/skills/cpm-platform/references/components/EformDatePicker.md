> 来源：schema-tools/components/EformDatePicker/knowledge.md（同步于 2026-08-25）

# 日期框

> 组件 Key: `EformDatePicker`

## 适用场景
单日期选择，适用于出生日期、入职日期等。
与 EformDateRangePicker 区别：只选单个日期，非日期区间。

## 属性

> 公共属性（label、name、display、pattern、required）由系统自动注入。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| defaultValueType | `string` | `'custom'` | 默认值类型：`custom`（自定义值）、`variableDefaultValue`（变量默认值） |
| defaultValue | `string` | | 默认值（defaultValueType 为 custom 时使用） |
| variableDefaultValue | `string` | | 变量默认值（defaultValueType 为 variableDefaultValue 时使用，如 `'nowTime'`） |
| placeholder | `string` | `'请选择日期'` | 占位提示 |
| format | `string` | `'YYYY-MM-DD'` | 日期格式 |
| allowClear | `boolean` | `true` | 是否显示清除按钮 |
| allowBeforeNow | `boolean` | `true` | 是否允许选择过去的日期 |
| min | `Date` | | 最小可选日期 |
| max | `Date` | | 最大可选日期 |

### format 格式
- `'YYYY'` — 年份
- `'YYYY-MM'` — 年月
- `'YYYY-MM-DD'` — 年月日（默认）
- `'YYYY-MM-DD HH:mm:ss'` — 完整日期时间

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 设默认值为当前时间时：`defaultValueType: "variableDefaultValue"`, `variableDefaultValue: "nowTime"`
- min/max 优先级高于 allowBeforeNow
- allowBeforeNow=false 可禁用选择过去日期
