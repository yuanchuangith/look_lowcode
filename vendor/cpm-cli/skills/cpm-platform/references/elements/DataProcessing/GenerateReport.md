> 来源：action-design-tools/nodes/DataProcessing/GenerateReport/knowledge.md（同步于 2026-08-25）

# 生成报告

> 元件 Key: `GenerateReport`

## 适用场景
按报告模板生成报告文件（指定模板、数据、标题、返回方式与转换选项）。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `reportTemplate`（输入，必填） | 报告模板，表达式对象（引用模板 id） | **固定**：从报告模板配置取真实模板 id | 固定结构，取自工具 |
| `reportData`（输入，必填） | 报告数据，表达式对象 | **灵活**：数据对象/局部变量 | 灵活 |
| `reportTitle`（输入，可选） | 报告标题，表达式对象 | **灵活**：字面量/变量 | 灵活 |
| `returnType`（输入，可选） | 返回方式 `{id, label, value}` | **固定**：如 `StorageAndReturn`=返回文件ID | 固定枚举 |
| `isTimezoneConvert`/`isDateFormat`/`isExportWord`（输入，可选） | 布尔字面量 | **灵活**：true/false，默认 false | 灵活 |
| `requestResult`（输出，可选） | 生成结果变量名 | **灵活**：变量名自己起；值为表达式对象 | 自定义 |

> 输出为局部变量，下游引用用 `paramTypes:"localVariable"`。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| templateCode | object | 是 | true | 报告模板（表达式对象，引用模板 id） |
| data | object | 是 | true | 报告数据（表达式对象，引用数据对象/变量） |
| title | object | 否 | true | 报告标题（表达式对象） |
| returnMethod | object | 否 | false | 返回方式 {id, label, value}，如 StorageAndReturn=返回文件ID |
| timeZoneConvert | boolean | 否 | false | 是否时区转换，默认 false |
| dateFormatConvert | boolean | 否 | false | 是否日期格式转换，默认 false |
| isExportWord | boolean | 否 | false | 是否导出为 Word，默认 false |

### 输出参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| requestResult | object | 否 | true | 生成结果变量名（paramTypes:custom） |

## 参数示例
```json
{
  "elementKey": "GenerateReport",
  "params": {
    "inputs": {
      "templateCode": { "paramTypes": "custom", "code": "tempFileId", "label": "局部变量-tempFileId", "dataType": "number" },
      "data": { "paramTypes": "custom", "code": "docData", "label": "...", "dataType": "object" },
      "title": { "paramTypes": "custom", "code": "docData[0][\"file_name\"]", "label": "..." },
      "returnMethod": { "id": "StorageAndReturn", "label": "返回文件ID", "value": "StorageAndReturn" },
      "timeZoneConvert": false,
      "isExportWord": false
    },
    "outputs": { "requestResult": { "paramTypes": "custom", "code": "tempResult", "label": "tempResult" } }
  }
}
```

## 使用示例
```
tempResult = 生成报告(模板="局部变量-tempFileId", 标题="...", 返回="返回文件ID")
```
