> 来源：schema-tools/components/EformNumber/knowledge.md（同步于 2026-08-25）

# 数字框

> 组件 Key: `EformNumber`

## 适用场景
金额、数量、年龄等数值录入。
与 EformInput 区别：只接受数字，支持数值范围和精度控制。

## 属性

> 工具自动补齐平台运行时字段（model/modelend/sourcetype），模型只需提供下方参数。
> 公共属性（label、name、display、pattern、required）由系统自动注入。

### 关键参数

| 名称 | 类型 | 默认值 | 何时设置 |
|------|------|--------|----------|
| precision | `number` | | 小数位数（0=整数，2=两位小数）。金额/比率场景常用 |
| minimum | `number` | | 最小值 |
| maximum | `number` | | 最大值 |
| addonAfter | `string` | | 行内单位后缀（如 `%`、`元`、`kg`） |

### 其余参数（有默认值，无明确需求不用设）

| 名称 | 默认值 | 说明 |
|------|--------|------|
| defaultValue | `''` | 默认值 |
| placeholder | `'请输入'` | 占位提示 |
| clearable | `true` | 清除按钮 |

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- minimum 和 maximum 超出范围时组件自动限制
- 单位显示用 `addonAfter`（如百分比设 `addonAfter:'%'`、金额设 `addonAfter:'元'`）
