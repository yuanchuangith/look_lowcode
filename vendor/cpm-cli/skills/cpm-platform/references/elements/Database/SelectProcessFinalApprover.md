> 来源：action-design-tools/nodes/Database/SelectProcessFinalApprover/knowledge.md（同步于 2026-08-25）

# 获取流程节点审批人

> 元件 Key: `SelectProcessFinalApprover`

## 适用场景
查询指定流程实例（incident）下，某个流程节点（nodeName）的审批人。常用于流程提交前获取未审批人名单做提醒或校验。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `incident`（输入，必填） | 流程实例号，表达式对象 | **灵活**：通常是局部/全局变量（流程实例 id） | 灵活 |
| `nodeName`（输入，必填） | 流程节点名称，表达式对象 | **固定**：值为带引号的节点中文名（如 `"执行结果确认"`），从流程定义取真实节点名 | 固定值，取自工具 |
| `range`（输入，可选） | 范围字面量 | **固定**：`"-1"`=未审批（最常见）/ `"1"`=全部 | 固定枚举 |
| `variableName`（输出，必填） | 审批人查询结果变量名 | **灵活**：变量名自己起；值为表达式对象，值为审批人数组 | 自定义 |

> 输出为数组局部变量，下游引用用 `paramTypes:"localVariable"`。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| incident | object | 是 | true | 流程实例号（表达式对象，通常是局部/全局变量） |
| nodeName | object | 是 | true | 流程节点名称（表达式对象，值为带引号的节点中文名） |
| range | string | 否 | false | 范围：`"-1"`=未审批（最常见），`"1"`=全部 |

### 输出参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| queryResults | object | 是 | true | 审批人查询结果变量名（paramTypes:custom） |

## 参数示例
```json
{
  "elementKey": "SelectProcessFinalApprover",
  "params": {
    "inputs": {
      "incident": { "paramTypes": "localVariable", "value": "localVariable-incident", "code": "incident", "label": "局部变量-incident", "dataType": "string" },
      "nodeName": { "paramTypes": "custom", "value": "\"执行结果确认\"", "code": "\"执行结果确认\"", "label": "\"执行结果确认\"", "dataType": "string" },
      "range": "-1"
    },
    "outputs": { "queryResults": { "paramTypes": "custom", "code": "flow_no_user_ids", "label": "flow_no_user_ids", "dataType": "string" } }
  }
}
```

## 使用示例
```
flow_no_user_ids = 获取流程节点审批人(实例="incident", 节点="执行结果确认", 范围="未审批")
```

## 注意事项
- `incident` 通常来自上游变量（流程实例号），用表达式对象填写。
- `nodeName` 的值是节点中文名，需带引号（作为字符串字面量，paramTypes:custom）。
- `range` 默认 `"-1"`（未审批）；要查全部审批人用 `"1"`。
