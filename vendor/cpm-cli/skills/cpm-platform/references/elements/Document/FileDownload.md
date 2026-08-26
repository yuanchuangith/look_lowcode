> 来源：action-design-tools/nodes/Document/FileDownload/knowledge.md（同步于 2026-08-25）

# 文件下载

> 元件 Key: `FileDownload`

## 适用场景
下载指定文件（指定文件列表、文件名、下载方式与类型）。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `fileType`（输入，必填） | 下载文件类型字面量 | **固定**：如 `pdf` | 固定值 |
| `fileList`（输入，必填） | 文件列表，表达式对象 | **灵活**：文件 id 数组变量/组件值 | 灵活 |

> 无输出参数。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| downloadType | string | 是 | false | 下载文件类型（如 pdf） |
| files | object | 是 | true | 要下载的文件列表（表达式对象，通常引用一个数组变量） |
| fileName | object | 是 | true | 下载文件名（表达式对象，可引用字段如 item["FileCode"]） |
| downloadMode | string | 是 | false | 下载方式（如 direct=直接下载） |

### 输出参数
无。

## 参数示例
```json
{
  "elementKey": "FileDownload",
  "params": {
    "inputs": {
      "downloadType": "pdf",
      "files": { "paramTypes": "localVariable", "code": "pdfVerArry", "label": "局部变量-pdfVerArry", "dataType": "array" },
      "fileName": { "paramTypes": "custom", "code": "item[\"FileCode\"]", "label": "item[\"FileCode\"]", "dataType": "" },
      "downloadMode": "direct"
    }
  }
}
```

## 使用示例
```
文件下载(类型="pdf", 方式="direct", 文件="局部变量-pdfVerArry", 文件名="item[\"FileCode\"]")
```
