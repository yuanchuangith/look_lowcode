> 来源：action-design-tools/nodes/Database/UpdateData/knowledge.md（同步于 2026-08-25）

# 更新数据

> 元件 Key: `UpdateData`

## 适用场景
更新数据模型中符合条件的数据记录。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `modelName`（输入，必填） | 数据模型信息对象 | **固定**：从 `getModelList` 取，关注 `modelComment`(中文名)/`modelName`(英文表名)；查不到→留空+说明，禁止猜 | 固定结构，取自工具 |
| `updateParams`（输入，必填） | 更新字段数组 `[{modelAttribute, attribute, name}]` | **半固定**：`attribute` 是字段名(从 `getModelDetail` 取)；`name` 是新值表达式对象(灵活)；`modelAttribute`/`id` 平台自动填，**不要手写** | 结构固定，字段名取自工具 |
| `whereConditions`（输入，必填） | 更新条件 `{Logic, Filters:[{Field,Operator,ParamInput}]}` | **半固定**：`Field` 是数据库字段名(**裸列名**，如 `status`，从 `getModelDetail` 取 `Name`，**不加表名前缀**)；`Operator` 固定枚举；`ParamInput` 是表达式对象。**结构与 SelectData 一致（Field/Operator/ParamInput），不是 IfCondition 的 target/equalTo/value** | 结构固定，Field 取自工具 |
| `affectedRows`（输出，必填） | 受影响行数变量名。键名固定 `affectedRows` | **灵活**：变量名自己起；值为表达式对象 `paramTypes:"custom"`，`value`/`code`/`label` 填变量名，`dataType:"number"` | 自定义 |

> ⚠️ **必须提供 whereConditions**，否则全表更新。`affectedRows` 产出局部变量，下游引用用 `paramTypes:"localVariable"`。

#### updateParams / whereConditions 结构（基于真实数据）
```jsonc
// updateParams：数组，每项 {modelAttribute(平台填), attribute(字段名), name(新值表达式)}
"updateParams": [
  {
    "modelAttribute": { /* 平台按 modelName 自动补全的字段元数据，不要手写 */ },
    "attribute": "main_file_code",          // 字段名，从 getModelDetail 取
    "name": { "paramTypes": "custom", "value": "rows[0][\"file_code\"]", "code": "rows[0][\"file_code\"]", "label": "...", "dataType": "" }
  }
]

// whereConditions：{Logic, Filters:[{Field, Operator, ParamInput}]}（与 SelectData 同形状）
"whereConditions": {
  "Logic": "And",
  "Filters": [
    { "Field": "id", "Operator": "Equal", "ParamInput": { "paramTypes": "componentsVariable", "code": "inbiz.queryData.recordId", "label": "记录ID", "dataType": "string" } }
  ]
}
```

> 注：`whereConditions` 用数据库 Filter 形状（`Field`/`Operator`/`ParamInput`），**不是** IfCondition 的 `target`/`equalTo`/`value`，两者不要混。

### 真实数据样本
```json
{
  "elementKey": "UpdateData",
  "params": {
    "inputs": {
      "modelName": { "modelId": "...", "modelName": "gxp_dms_document_change_detailed", "modelComment": "文件变更明细", "group": "..." },
      "updateParams": [
        { "modelAttribute": { /* 平台填 */ }, "attribute": "main_file_code", "name": { "paramTypes": "custom", "value": "rows[0][\"file_code\"]", "code": "rows[0][\"file_code\"]", "label": "rows[0][\"file_code\"]", "dataType": "" } }
      ],
      "whereConditions": { "Logic": "And", "Filters": [ { "Field": "id", "Operator": "Equal", "ParamInput": { /* 表达式对象 */ } } ] }
    },
    "outputs": { "affectedRows": { "paramTypes": "custom", "value": "affected", "code": "affected", "label": "affected", "dataType": "number" } }
  }
}
```

## 注意事项
- **必须提供 whereConditions**，避免全表更新
- 字段名（attribute / Field）从 `getModelDetail` 取 `Name`（区分大小写），**用裸列名，不加表名前缀**（如 `status`，不是 `表.status`）
- 每个值（name / ParamInput）必须是表达式对象，其 `dataType` 只用规范值（`string`/`number`/`double`/`boolean`/`object`/`dictionary`/`array`/`dateTime`/`any`，大小写敏感）——**不要把模型字段原始类型（`varchar`/`text`/`int`/`datetime`）直抄**，对应映射：`varchar`/`text`/`char`→`string`、`int`/`long`→`number`、`datetime`→`dateTime`
- `updateParams` 是数组（结构与 AddNewData 的 params 一致）；`whereConditions` 用 Field/Operator/ParamInput 形状

## 自动补全（expand 层）
本元件支持 expand 自动补全，模型**只需给设计意图字段**，以下壳字段由工具自动补全，**不要手写**：
- `updateParams[]` 每项的 `id`、`paramTypes`、整块 `modelAttribute`（按 modelName 查模型字段补全）
- `whereConditions` 及每个 Filter 的 `Id`、`value`、`type` 副本
- 表达式对象缺失的 `value`/`dataType`（按 paramTypes 派生）
模型给：`attribute`(字段名) + `name`(值表达式) + `whereConditions`(Field/Operator/ParamInput 条件树)。
