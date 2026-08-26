> 来源：action-design-tools/nodes/Page/SetQueryData/knowledge.md（同步于 2026-08-25）

# 设置页面参数

> 元件 Key: `SetQueryData`

## 适用场景
设置页面参数的值。常用于打开子页面前给目标页面参数赋值，或在页面内回写参数。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `queryName`（输入，必填） | 页面参数名字面量 | **固定**：页面定义的参数名（如 `recordId`），从页面配置取真实参数名 | 固定值，取自工具 |
| `queryValue`（输入，必填） | 参数值，表达式对象 | **灵活**：组件值/局部变量/字面量 | 灵活 |

> 无输出参数。是 QueryData 的逆操作。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| paramName | string | 是 | false | 页面参数名（字符串字面量，如 `recordId`） |
| paramValue | object | 是 | true | 参数值（表达式对象，引用组件当前值/输入参数等） |

## 参数示例
```json
{
  "elementKey": "SetQueryData",
  "params": {
    "inputs": {
      "paramName": "recordId",
      "paramValue": { "value": "...", "dataType": "any", "label": "输入参数-node[\"id\"]", "code": "(node)[\"id\"]", "objectAttribute": "[\"id\"]" }
    }
  }
}
```

## 使用示例
```
设置页面参数(recordId=输入参数-node["id"])
```

## 注意事项
- `paramName` 是字符串字面量；`paramValue` 是表达式对象。
- 无输出参数。
