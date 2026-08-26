> 来源：action-design-tools/nodes/Database/SelectModelData/knowledge.md（同步于 2026-08-25）

# 数据集查询

> 元件 Key: `SelectModelData`

## 适用场景
从数据集中分页查询符合条件的数据记录。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `modelName`（输入，必填） | 数据模型信息对象 | **固定**：从 `getModelList` 取 modelKey，或 `getDataSetList` 取 dataSetId；需确认字段用 `getModelDetail`。查不到→留空+说明，禁止凭名称猜 id | 固定结构，取自工具 |
| `pageIndex`/`pageSize` | 页码/条数 | **灵活**：数字，默认 1/10 | 灵活 |
| `whereConditions`（输入，可选） | 查询条件 `{Logic, Filters:[{Field,Operator,ParamInput}]}` | **半固定**：Field 是数据库字段名(从 getModelDetail 取)；Operator 固定枚举；ParamInput 表达式对象 | 结构固定，Field 取自工具 |
| `queryResults`（输出，必填） | 查询结果变量名。键名固定 `queryResults` | **灵活**：变量名自己起；值为表达式对象 `paramTypes:"custom"`，`value`/`code`/`label` 填变量名，`dataType:"array"` | 自定义 |
| `dataCount`（输出，可选） | 数据总数变量名 | **灵活**：真实数据中常省略，只在需要时填 | 自定义 |

> `queryResults` 产出局部变量，下游引用用 `paramTypes:"localVariable"`。常配合 ForEachArray 遍历。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| modelName | object | 是 | 数据集选择 |
| pageIndex | number | 否 | 页码（默认1） |
| pageSize | number | 否 | 每页条数（默认10） |
| whereConditions | object | 否 | 查询条件 |

### 输出参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| queryResults | array | 是 | 查询结果数组 |
| dataCount | number | 是 | 数据总数 |

## 使用示例
```
{queryResults, dataCount} = 数据集查询(数据集="xxx", 页码=1, 每页=10)
```

## 注意事项
- 查询结果为数组，通常配合 FOR_EACH 遍历
- 支持分页，默认每页10条

## 自动补全（expand 层）
本元件支持 expand 自动补全，模型**只需给设计意图字段**，以下壳字段由工具自动补全，**不要手写**：
- `whereConditions` 及每个 Filter 的 `Id`
- `modelName`/表达式对象缺失的 `value`/`dataType`
模型给：`modelName` + `pageIndex`/`pageSize` + `whereConditions`(Field/Operator/ParamInput 条件树) + `queryResults`(结果变量名)。
