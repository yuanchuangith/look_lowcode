> 来源：action-design-tools/nodes/Document/DocumentPrintCsharp/knowledge.md（同步于 2026-08-25）

# 文档打印（后端）

> 元件 Key: `DocumentPrintCsharp`

## 适用场景
在后端（C#）进行文档打印，通常接收前端 DocumentPrint 节点产出的打印参数，返回条码等结果。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `printParameters`（输入，必填） | 打印参数，表达式对象 | **灵活**：通常由前端 DocumentPrint 产出的 printingParameters 派生（如 `JObject.FromObject(printInfo)`），用 `paramTypes:"localVariable"` 引用 | 灵活 |
| `requestResult`（输出，可选） | 后端打印结果变量名 | **灵活**：变量名自己起；值为表达式对象 | 自定义 |

> 输出为局部变量，下游引用用 `paramTypes:"localVariable"`。与 DocumentPrint 配合：前端打印产出参数 → 后端打印执行。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| printParams | object | 是 | true | 打印参数（表达式对象，通常由前端 DocumentPrint 的 printingParameters 派生，如 JObject.FromObject(printInfo)） |

### 输出参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| barcodes | object | 否 | true | 打印结果变量名（paramTypes:custom），通常为条码数组 |

## 参数示例
```json
{
  "elementKey": "DocumentPrintCsharp",
  "params": {
    "inputs": { "printParams": { "paramTypes": "custom", "code": "JObject.FromObject(printInfo)", "label": "JObject.FromObject(printInfo)" } },
    "outputs": { "barcodes": { "paramTypes": "custom", "code": "barcodes", "label": "barcodes" } }
  }
}
```

## 使用示例
```
barcodes = 文档打印-后端(参数="JObject.FromObject(printInfo)")
```
