> 来源：action-design-tools/nodes/Components/DataFilter/knowledge.md（同步于 2026-08-25）

# 数据过滤

> 元件 Key: `DataFilter`

## 适用场景
给组件（通常是表格/列表）的数据源**新增过滤条件**。例如打开页面前给列表组件叠加"只看本部门"的条件。区别于 SelectData（查数据库），DataFilter 是给已有组件的数据叠加过滤。

## ⚠️ 使用前必做

**使用 DataFilter 前，必须先调用 `getModelDetail` 获取目标模型的字段列表！**

`Field` 字段必须是 **`表名.列名`** 格式（如 `gxp_dms_document.OrgId`），不能只写列名（如 `OrgId`）。
- 从 `getModelDetail` 返回的字段列表中取 `Name` 字段，拼成 `表名.列名` 格式
- 或从 `getPageComponents` 返回的表格列引用中取字段名

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `name`（输入，必填） | 目标组件引用 `{label, value, modelkey}` | **固定**：从 `getPageComponents` 取组件 ref 粘贴；`modelkey` 为平台派生，**不要手写** | 固定结构，取自工具 |
| `whereConditions`（输入，必填） | 过滤条件树 `{Logic, Filters:[...]}` | **半固定**：`Field` 是数据库字段名(`表名.列名`，从 `getModelDetail` 取)；`Operator` 固定枚举；`ParamInput` 表达式对象。支持递归嵌套（Filters 项可为子组）。**结构同 SelectData/UpdateData/DeleteData 的 whereConditions（Field/Operator/ParamInput）** | 结构固定，Field 取自工具 |

> 无输出参数。DataFilter 是给**已有组件的数据源**叠加过滤条件，区别于 SelectData（直接查数据库返回结果）。

## whereConditions 条件树

`{Logic, Filters}` 结构，**支持递归嵌套**（Filters 项可为子组，形成 AND/OR 树）：

```jsonc
{
  "Logic": "And",
  "Filters": [
    {
      "Field": "表名.列名",        // ⚠️ 必须是"表名.列名"格式，从 getModelDetail 获取
      "Operator": "Equal",         // Equal/NotEqual/GreaterThan/.../Contains/Any/isnull/isnotnull
      "ParamInput": {              // 比较值（表达式对象）
        "paramTypes": "localVariable", "code": "orgId", "label": "局部变量-orgId", "dataType": "string"
      },
      "value": "..."               // 平台填的代码值
    },
    {
      "Logic": "Or",               // 子组：递归嵌套，本组内 OR
      "Filters": [
        { "Field": "表名.列名1", "Operator": "Equal", "ParamInput": {...} },
        { "Field": "表名.列名2", "Operator": "Equal", "ParamInput": {...} }
      ]
    }
  ]
}
```

**Operator 取值**：Equal / NotEqual / GreaterThan / GreaterThanOrEqual / LessThan / LessThanOrEqual / Contains / NotContains / Any / In / isnull / isnotnull

> **注意**：`isnull` / `isnotnull` 操作符不需要 `ParamInput`（判断字段是否为空）。

## 参数示例
```json
{
  "elementKey": "DataFilter",
  "params": {
    "inputs": {
      "name": { "value": "MainFile", "label": "文件信息", "modelkey": "<GUID>" },
      "whereConditions": {
        "Logic": "And",
        "Filters": [
          { "Field": "gxp_dms_document.OrgId", "Operator": "Equal", "ParamInput": { "paramTypes": "localVariable", "code": "orgId", "label": "局部变量-orgId", "dataType": "string" } }
        ]
      }
    }
  }
}
```

## 使用示例
```
result = 数据过滤(数据源=文件信息, 配置="OrgId=局部变量-orgId, (RefId='default' OR RefId=系统变量-记录ID)")
```

## 常见错误

### ❌ Field 格式错误
```json
// 错误：只写了列名，缺少表名
{ "Field": "status", "Operator": "Equal", ... }

// 正确：表名.列名格式
{ "Field": "gxp_qms_unqualified_product_info.status", "Operator": "Equal", ... }
```

### ❌ 缺少必要字段
```json
// 错误：缺少 ParamInput
{ "Field": "表名.status", "Operator": "Equal" }

// 正确：完整结构
{ "Field": "表名.status", "Operator": "Equal", "ParamInput": { "paramTypes": "custom", "value": "'active'", "code": "'active'", "label": "'active'", "dataType": "string" } }
```

### ✅ isnull 操作符（不需要 ParamInput）
```json
{ "Field": "表名.ref_id", "Operator": "isnull" }
```

## 注意事项
- `name` 是组件引用（表达式对象），从 getPageComponents 取；`modelkey` 为平台派生，不用手写。
- **Field 必须是 `表名.列名` 格式**，从 `getModelDetail` 获取，不能只写列名。
- Operator 用 PascalCase 枚举（`Equal` 不是 `=`）。
- **平台自动生成、模型不要手写**：每条 Filter 的 `Id`、`whereConditions.Id`、`type`、`value`（代码形态）。
- 与 IfCondition 的 `{target, equalTo, value}` 形状不同，不要混用。
