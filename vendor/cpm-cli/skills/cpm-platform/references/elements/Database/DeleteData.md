> 来源：action-design-tools/nodes/Database/DeleteData/knowledge.md（同步于 2026-08-25）

# 删除数据

> 元件 Key: `DeleteData`

## 适用场景
删除数据模型中符合条件的数据记录，支持物理删除和逻辑删除。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `modelName`（输入，必填） | 数据模型信息对象 | **固定**：从 `getModelList` 取，关注 `modelComment`/`modelName`；组件已带 binding 时直接用 `binding.modelKey`。查不到→留空+说明，禁止猜 | 固定结构，取自工具 |
| `isDelete`（输入，可选） | 是否逻辑删除，布尔字面量 | **固定**：`true`=逻辑删除(标记)、`false`=物理删除(不可恢复，默认) | 固定枚举 |
| `whereConditions`（输入，必填） | 删除条件 `{Logic, Filters:[{Field,Operator,ParamInput}]}` | **半固定**：`Field` 是数据库字段名(**裸列名**，如 `status`，从 `getModelDetail` 取 `Name`，**不加表名前缀**)；`Operator` 固定枚举；`ParamInput` 表达式对象。**结构与 SelectData/UpdateData 一致（Field/Operator/ParamInput），不是 IfCondition 的 target/equalTo/value** | 结构固定，Field 取自工具 |
| `affectedRows`（输出，必填） | 受影响行数变量名。键名固定 `affectedRows` | **灵活**：变量名自己起；值为表达式对象 `paramTypes:"custom"`，`dataType:"number"` | 自定义 |

> ⚠️ **必须提供 whereConditions**，否则全表删除。`affectedRows` 产出局部变量，下游引用用 `paramTypes:"localVariable"`。

#### whereConditions 结构（基于真实数据，与 SelectData/UpdateData 同形状）
```jsonc
"whereConditions": {
  "Logic": "And",
  "Filters": [
    { "Field": "id", "Operator": "Equal", "ParamInput": { "paramTypes": "componentsVariable", "code": "inbiz.queryData.recordId", "label": "记录ID", "dataType": "string" } }
  ]
}
```
> 注：用数据库 Filter 形状（`Field`/`Operator`/`ParamInput`），**不是** IfCondition 的 `target`/`equalTo`/`value`。

## 使用示例
```
用户："删除状态为已取消的订单"
→ getModelList 找订单模型
→ addNode(DeleteData, modelName=订单模型, whereConditions={Logic:And, Filters:[{Field:"status", Operator:"Equal", ParamInput:{paramTypes:"custom", value:"已取消", code:"'已取消'", label:"已取消", dataType:"string"}}]})
```

## 注意事项
- `modelName` 用 `getModelList` 取真实模型 id（组件已带 binding 时直接用 binding.modelKey），不要凭名称猜测
- **必须提供 whereConditions**，避免全表删除
- `isDelete` 是布尔字面量（非表达式对象）：true=逻辑删除、false=物理删除（默认，不可恢复，谨慎）
- whereConditions 用 Field/Operator/ParamInput 形状，与 SelectData/UpdateData 一致；`Field` 用**裸列名**（如 `status`，不加表名前缀）
- `ParamInput` 的 `dataType` 只用规范值（`string`/`number`/`dateTime` 等，大小写敏感），不要直抄模型字段原始类型

## 自动补全（expand 层）
本元件支持 expand 自动补全，模型**只需给设计意图字段**，以下壳字段由工具自动补全，**不要手写**：
- `whereConditions` 及每个 Filter 的 `Id`、`value`、`type` 副本
- 表达式对象缺失的 `value`/`dataType`
模型给：`modelName` + `isDelete` + `whereConditions`(Field/Operator/ParamInput 条件树)。
