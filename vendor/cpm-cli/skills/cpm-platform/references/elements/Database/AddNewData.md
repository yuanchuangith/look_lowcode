> 来源：action-design-tools/nodes/Database/AddNewData/knowledge.md（同步于 2026-08-25）

# 新增数据

> 元件 Key: `AddNewData`

## 适用场景
向指定数据模型中新增一条数据记录。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `modelName`（输入，必填） | 数据模型信息对象 | **固定**：从 `getModelList` 取，关注 `modelComment`(中文名)/`modelName`(英文表名)；组件已带 binding 时直接用 `binding.modelKey`。查不到→留空+说明，禁止猜 | 固定结构，取自工具 |
| `params`（输入，必填） | 属性-值数组 `[{modelAttribute, attribute, name}]` | **半固定**：`attribute` 是字段名(从 `getModelDetail` 取)；`name` 是值表达式对象(灵活)；`modelAttribute`/`id`/`paramTypes` 平台自动填，**不要手写**。结构与 UpdateData.updateParams 一致 | 结构固定，字段名取自工具 |
| `modelData`（输出，必填） | 受影响行数变量名。键名固定 `modelData` | **灵活**：变量名自己起；值为表达式对象 `paramTypes:"custom"`，`value`/`code`/`label` 填变量名，`dataType:"number"` | 自定义 |

> `modelData` 产出局部变量，下游引用用 `paramTypes:"localVariable"`。

#### params 结构（基于真实数据，是数组不是对象）
```jsonc
"params": [
  {
    "modelAttribute": { /* 平台按 modelName 自动补全的字段元数据，不要手写 */ },
    "attribute": "serial_no",              // 字段名，从 getModelDetail 取
    "name": { "paramTypes": "localVariable", "value": "localVariable-sort", "code": "sort", "label": "局部变量-sort", "dataType": "string" },
    "paramTypes": "any"                     // 平台填
  }
]
```

> 注：`params` 是**数组**（每项 `{modelAttribute, attribute, name}`），不是 `{字段名: 值}` 对象。结构与 UpdateData.updateParams 完全一致。

## 真实数据样本
```json
{
  "elementKey": "AddNewData",
  "params": {
    "inputs": {
      "modelName": { "modelId": "...", "modelName": "gxp_dms_change_assessment_detailed", "modelComment": "变更评估明细", "group": "..." },
      "params": [
        { "modelAttribute": { /* 平台填 */ }, "attribute": "serial_no", "name": { "paramTypes": "localVariable", "value": "localVariable-sort", "code": "sort", "label": "局部变量-sort", "dataType": "string" } },
        { "modelAttribute": { /* 平台填 */ }, "attribute": "orgId", "name": { "paramTypes": "...", "code": "...", "label": "..." } }
      ]
    },
    "outputs": { "modelData": { "paramTypes": "custom", "value": "affected", "code": "affected", "label": "affected", "dataType": "number" } }
  }
}
```

## JS 表达式写法（name 的 code 字段）
- 组件值：`inbiz('组件id').value`
- 全局变量：`self.globalVariables['name']`
- 字面量：`"待审"`、`100`
- 上游局部变量：用 `paramTypes:"localVariable"`

## 使用示例
```
用户："把表单数据存成新订单"
→ getModelList 找订单模型，getModelDetail 看字段
→ addNode(AddNewData, modelName=订单模型, params=[{attribute:"Title", name:输入框值}, {attribute:"Amount", name:数字框值}, {attribute:"Status", name:"待审"}])
```

## 注意事项
- `modelName` 用 `getModelList` 取真实模型 id（组件已带 binding 时直接用 binding.modelKey），不要凭名称猜测
- 字段名（attribute）必须与模型字段一致（从 getModelDetail 确认大小写），**用裸列名**（如 `serial_no`，不加表名前缀）
- 每个字段值（name）必须是表达式对象，不能填裸字符串；其 `dataType` 只用规范值（`string`/`number`/`double`/`boolean`/`object`/`dictionary`/`array`/`dateTime`/`any`，大小写敏感）——**不要把模型字段原始类型（`varchar`/`text`/`int`/`datetime`）直抄**，对应映射：`varchar`/`text`/`char`→`string`、`int`/`long`→`number`、`datetime`→`dateTime`
- `params` 是数组，结构与 UpdateData.updateParams 一致

## 自动补全（expand 层）
本元件支持 expand 自动补全，模型**只需给设计意图字段**，以下壳字段由工具自动补全，**不要手写**：
- `params[]` 每项的 `id`、`paramTypes`、整块 `modelAttribute`（按 modelName 查模型字段补全）
- 表达式对象缺失的 `value`/`dataType`（按 paramTypes 派生）
模型给：`modelName` + `params[]{attribute, name}`（字段名 + 值表达式）。
