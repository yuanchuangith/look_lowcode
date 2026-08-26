> 来源：action-design-tools/nodes/Page/SetSummaryInfo/knowledge.md（同步于 2026-08-25）

# 设置摘要信息

> 元件 Key: `SetSummaryInfo`

## 适用场景
设置表单或流程实例的摘要信息——取某个组件的当前值作为摘要内容，便于在列表或流程追踪中快速识别。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `name`（输入，必填） | 摘要来源组件引用，表达式对象 | **固定**：从 `getPageComponents` 取组件 ref（`paramTypes:"componentsVariable"`），引用某组件的当前值作为摘要 | 固定结构，取自工具 |

> 无输出参数。取组件当前值设为表单/流程摘要。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| paramName | object | 是 | true | 摘要来源组件引用（表达式对象，paramTypes:componentsVariable，引用某组件的当前值） |

## 参数示例
```json
{
  "elementKey": "SetSummaryInfo",
  "params": {
    "inputs": {
      "paramName": { "paramTypes": "componentsVariable", "value": "EvaluationOverview-value", "code": "inbiz('EvaluationOverview').value", "label": "页面组件-评估概述-当前值", "dataType": "EformTextArea" }
    }
  }
}
```

## 使用示例
```
设置摘要信息(配置="页面组件-评估概述-当前值")
```

## 注意事项
- `paramName` 是组件引用表达式对象（取该组件的 `.value` 作为摘要），不是字符串字面量。
- 无输出参数。
