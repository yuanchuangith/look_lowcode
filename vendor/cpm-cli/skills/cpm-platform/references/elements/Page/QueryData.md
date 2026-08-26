> 来源：action-design-tools/nodes/Page/QueryData/knowledge.md（同步于 2026-08-25）

# 获取页面参数

> 元件 Key: `QueryData`

## 适用场景
获取页面参数（页面打开时传入的 URL/上下文参数）的值。例如父页面打开子页面时传入的 `recordId`、`change_details_ids_str` 等。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `queryName`（输入，必填） | 页面参数名字面量 | **固定**：页面定义的参数名（如 `recordId`、`change_details_ids_str`），从页面配置取真实参数名 | 固定值，取自工具 |
| `variableName`（输出，必填） | 参数值变量名 | **灵活**：变量名自己起；值为表达式对象 `paramTypes:"custom"` | 自定义 |

> 输出为局部变量，下游引用用 `paramTypes:"localVariable"`。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| paramName | string | 是 | false | 页面参数名（字符串字面量，如 `change_details_ids_str`） |

### 输出参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| parameterResults | object | 是 | true | 返回值变量名（paramTypes:custom） |

## 参数示例
```json
{
  "elementKey": "QueryData",
  "params": {
    "inputs": { "paramName": "change_details_ids_str" },
    "outputs": { "parameterResults": { "paramTypes": "custom", "code": "change_details_ids_str", "label": "change_details_ids_str", "dataType": "string" } }
  }
}
```

## 使用示例
```
change_details_ids_str = 获取页面参数(参数="change_details_ids_str")
```

## 注意事项
- `paramName` 是页面参数名（字符串），不是表达式对象，直接写字面量。
- 参数名来自页面配置中定义的页面参数清单。
