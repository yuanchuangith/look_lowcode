> 来源：action-design-tools/nodes/Document/DocumentPrint/knowledge.md（同步于 2026-08-25）

# 文档打印

> 元件 Key: `DocumentPrint`

## 适用场景
在前端打印文档（指定文件版本、份数、文件名、水印、附件、合并等），结果作为打印参数供后续节点（如 DocumentPrintCsharp）使用。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `fileVersionId`（输入，必填） | 文件版本 id，表达式对象 | **灵活**：局部变量/组件值（文件版本 id） | 灵活 |
| `printingParameters`（输出，必填） | 打印参数变量名 | **灵活**：变量名自己起；值为表达式对象。作为 DocumentPrintCsharp 的入参 | 自定义 |

> 输出的打印参数是局部变量，供后端 DocumentPrintCsharp 使用，下游引用用 `paramTypes:"localVariable"`。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| fileVerId | object | 是 | true | 文件版本 id（表达式对象） |
| copies | object | 否 | true | 打印份数（表达式对象） |
| printCopies | object | 否 | true | 输出份数（表达式对象） |
| fileName | object | 否 | true | 文件名（表达式对象） |
| Watermark | object | 否 | true | 水印配置（表达式对象，通常引用数组变量） |
| AttachFileVerIds | object | 否 | true | 附件文件版本 id 列表（表达式对象，引用数组变量） |
| MergeFiles | object | 否 | true | 是否合并文件（表达式对象） |

### 输出参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| printingParameters | object | 否 | true | 打印参数变量名（paramTypes:custom），供后续打印节点使用 |

## 参数示例
```json
{
  "elementKey": "DocumentPrint",
  "params": {
    "inputs": {
      "fileVerId": { "paramTypes": "custom", "code": "pageInbiz.queryData.file_ver_id", "label": "..." },
      "copies": { "paramTypes": "custom", "code": "1", "label": "1" },
      "fileName": { "paramTypes": "custom", "code": "pageInbiz.queryData.file_name", "label": "..." }
    },
    "outputs": { "printingParameters": { "paramTypes": "custom", "code": "printInfo", "label": "printInfo" } }
  }
}
```

## 使用示例
```
printInfo = 文档打印(文件版本="...", 文件名="...", 份数=1)
```
