> 来源：schema-tools/components/EformHidden/knowledge.md（同步于 2026-08-25）

# 隐藏域

> 组件 Key: `EformHidden`

## 适用场景
存储不需要对用户展示的数据字段，如用户ID、时间戳、关联记录ID等。

## 属性

> 公共属性（label、name、display、required）由系统自动注入。隐藏域不支持 pattern。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| defaultValueType | `string` | `'custom'` | 默认值类型（`'system'` 或 `'custom'`） |
| systemDefaultValue | `string` | `'System_Var_LoginUserID'` | 系统变量值 |
| customValue | `string` | | 自定义默认值 |

### 系统变量列表
- `System_Var_LoginUserID` — 当前用户ID
- `System_Var_LoginUserName` — 当前用户名称
- `System_Var_LoginUserDeptID` — 当前用户部门ID
- `System_Var_LoginUserDeptName` — 当前用户部门名称
- `System_Var_LoginUserPostID` — 当前用户职位ID
- `System_Var_LoginUserPostName` — 当前用户职位名称
- `System_Var_LoginUserAccount` — 当前用户账号

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 完全隐藏，不在界面上显示
- 表单提交时会随其他字段一起提交
- defaultValueType='system' 时使用 systemDefaultValue 指定的系统变量
- defaultValueType='custom' 时使用 customValue 作为默认值
