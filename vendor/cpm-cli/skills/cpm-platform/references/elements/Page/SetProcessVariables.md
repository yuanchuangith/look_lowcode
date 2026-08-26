> 来源：action-design-tools/nodes/Page/SetProcessVariables/knowledge.md（同步于 2026-08-25）

# 设置流程变量

> 元件 Key: `SetProcessVariables`

## 适用场景
设置流程实例的变量值，用于在流程节点间传递数据。例如在提交前把组件当前值写入流程变量。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `variableName`（输入，必填） | 流程变量名，字符串字面量 | **固定**：从 `getProcessVariables` 取真实流程变量名（如 `IsMahAudit`）。**别凭变量含义猜名字**——流程变量名是流程定义里固定的，查不到→留空+向用户说明 | 固定值，取自工具 |
| `variableValue`（输入，必填） | 变量值，表达式对象 | **灵活**：引用组件值(`paramTypes:"componentsVariable"`)、局部变量(`localVariable`)、字面量等 | 灵活 |

> 无输出参数。本元件把值写入流程实例的变量，供流程节点间传递。

## 参数示例
```json
{
  "elementKey": "SetProcessVariables",
  "params": {
    "inputs": {
      "variableName": "IsMahAudit",
      "variableValue": { "paramTypes": "componentsVariable", "value": "is_mah_audit-value", "code": "inbiz('is_mah_audit').value", "label": "页面组件-是否需要体系外审核-当前值", "dataType": "EformStaticList" }
    }
  }
}
```

## 使用示例
```
用户："提交前把'是否体系外审核'写到流程变量"
→ getProcessVariables 取真实流程变量名
→ getPageComponents 取组件 ref
→ addNode(SetProcessVariables, variableName="IsMahAudit", variableValue=组件ref)
```

## 注意事项
- `variableName` 是字符串字面量，**必须从 `getProcessVariables` 取真实流程变量名**，禁止猜
- `variableValue` 是表达式对象
- 无输出参数
