> 来源：schema-tools/components/EformApplicationDept/knowledge.md（同步于 2026-08-25）

# 申请部门

> 组件 Key: `EformApplicationDept`

## 适用场景
部门选择，适用于申请所属部门、部门分配等表单场景。

## 属性

> 公共属性（label、name、display、pattern、required）由系统自动注入。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| placeholder | `string` | `'请选择申请部门'` | 占位提示 |
| allowClear | `boolean` | `true` | 是否允许清除 |
| isDefaultValue | `boolean` | `true` | 是否使用默认值（当前用户部门） |
| isCrossCompany | `boolean` | `false` | 是否支持跨公司选择 |

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- isDefaultValue=true 时自动填充当前登录用户所属部门
- isCrossCompany=true 时允许选择其他公司的部门
