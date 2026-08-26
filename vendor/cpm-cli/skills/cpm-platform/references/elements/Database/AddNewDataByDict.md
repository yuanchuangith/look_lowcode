> 来源：action-design-tools/nodes/Database/AddNewDataByDict/knowledge.md（同步于 2026-08-25）

# 按字典新增

> 元件 Key: `AddNewDataByDict`

## 适用场景
按照字典定义向数据模型中新增数据记录，适用于需要按字典规范录入的场景。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `modelName`（输入，必填） | 数据模型信息对象 | **固定**：从 `getModelList` 取 | 固定结构，取自工具 |
| `dictionaryId`（输入，必填） | 字典 ID 字面量 | **固定**：从 `getDictionaryList` 取真实字典分组 id | 固定值，取自工具 |
| `params`（输入，必填） | 属性-值数组 `[{attribute, name}]` | **半固定**：attribute 字段名从字典/模型取；name 值表达式对象 | 结构固定，字段名取自工具 |
| `affectedRows`（输出，必填） | 受影响行数变量名 | **灵活**：变量名自己起；值为表达式对象，`dataType:"number"` | 自定义 |

> 输出为局部变量，下游引用用 `paramTypes:"localVariable"`。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| modelName | object | 是 | 数据模型选择 |
| dictId | string | 是 | 字典ID |
| params | object | 是 | 属性-值表格（字段映射） |

### 输出参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| modelData | number | 是 | 受影响行数 |

## 使用示例
```
affectedRows = 按字典新增(模型="xxx", 字典="yyy")
```

## 注意事项
- 必须提供有效的字典ID
- params 需符合字典定义的字段规范
