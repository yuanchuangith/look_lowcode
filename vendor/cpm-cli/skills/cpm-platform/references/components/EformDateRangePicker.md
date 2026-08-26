> 来源：schema-tools/components/EformDateRangePicker/knowledge.md（同步于 2026-08-25）

# 区间日期

> 组件 Key: `EformDateRangePicker`

## 适用场景
日期区间选择，适用于请假起止日期、项目周期、有效期设置。
与 EformDatePicker 区别：选择开始和结束两个日期。

## 属性

> 公共属性（label、name、display、pattern、required）由系统自动注入。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| defaultValue | `[string, string]` | | 默认值，如 `['nowTime', 'nowTime']` |
| format | `string` | `'YYYY-MM-DD'` | 日期格式 |
| startPlaceholder | `string` | `'请选择开始日期'` | 开始日期占位提示 |
| endPlaceholder | `string` | `'请选择结束日期'` | 结束日期占位提示 |
| dateQuickChoose | `boolean` | `true` | 是否显示快捷周期选择 |
| allowClear | `boolean` | `true` | 是否显示清除按钮 |
| allowBeforeNow | `boolean` | `true` | 是否允许选择过去的日期 |
| min | `Date` | | 最小可选日期 |
| max | `Date` | | 最大可选日期 |

### format 格式
- `'YYYY-MM-DD'` — 年月日（默认）
- `'YYYY-MM-DD HH:mm:ss'` — 完整日期时间
- `'YYYY-MM'` — 年月

### defaultValue 说明
数组两个元素分别对应开始和结束的默认值：
- `'nowTime'` 表示当前时间
- 日期字符串表示自定义日期

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- dateQuickChoose=true 时显示快捷选项：今天、本周、本月、本季度、本年
- 快捷周期选项：今天、本周、本月、本季度、本年
