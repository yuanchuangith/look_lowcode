> 来源：action-design-tools/nodes/Database/UpdateDataByDict/knowledge.md（同步于 2026-08-25）

# 按字典更新

> 元件 Key: `UpdateDataByDict`

## 适用场景
按照字典定义更新数据模型中符合条件的数据记录。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `modelName`（输入，必填） | 数据模型信息对象 | **固定**：从 `getModelList` 取 | 固定结构，取自工具 |
| `dictionaryId`（输入，必填） | 字典 ID 字面量 | **固定**：从 `getDictionaryList` 取真实字典分组 id | 固定值，取自工具 |
| `updateParams`（输入，必填） | 更新字段数组 `[{attribute, name}]` | **半固定**：attribute 字段名从字典/模型取；name 值表达式对象 | 结构固定，字段名取自工具 |
| `whereConditions`（输入，必填） | 更新条件 `{Logic, Filters:[{Field,Operator,ParamInput}]}` | **半固定**：Field 字段名从模型取；结构同 SelectData | 结构固定，Field 取自工具 |
| `affectedRows`（输出，必填） | 受影响行数变量名 | **灵活**：变量名自己起；值为表达式对象，`dataType:"number"` | 自定义 |

> ⚠️ **必须提供 whereConditions**。输出为局部变量，下游引用用 `paramTypes:"localVariable"`。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| modelName | object | 是 | 数据模型选择 |
| dictId | string | 是 | 字典ID |
| updateParams | object | 是 | 更新字段（属性-值映射） |
| whereConditions | object | 是 | 更新条件 |

### 输出参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| affectedRows | number | 是 | 受影响行数 |

## 使用示例
```
affectedRows = 按字典更新(模型="xxx", 字典="yyy")
```

## 注意事项
- 必须提供有效的字典ID
- 必须提供更新条件，避免全表更新
- updateParams 需符合字典定义的字段规范
