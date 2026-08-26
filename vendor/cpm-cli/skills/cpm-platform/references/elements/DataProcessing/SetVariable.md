> 来源：action-design-tools/nodes/DataProcessing/SetVariable/knowledge.md（同步于 2026-08-25）

# 定义变量

> 元件 Key: `SetVariable`

## 适用场景
创建一个局部变量并赋初始值。变量定义后在后续元件中可用（引用方式见下文）。

> 本元件【产生】一个局部变量；若要改已有变量的值，请用 SetVariableValue（它不产生新变量）。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `variableType` | 变量类型枚举值（单个字符串） | **固定枚举**：`string` / `number` / `double` / `boolean` / `object` / `dictionary` / `array` / `dateTime` / `any` | 固定（取自工具） |
| `variableValue` | 变量的初始值，表达式对象 `{paramTypes,value,code,label,dataType}` | code 可填：字面量(`0`/`"张三"`/`true`/`[]`/`{}`)、组件值 `inbiz('id').value`、表达式、全局变量 `self.globalVariables['x']`、上游局部变量（用 `paramTypes:"localVariable"`） | 灵活（模型自定义） |
| `variableName`（输出，必填） | 新变量名绑定：键名固定为 `variableName`；值为表达式对象 `paramTypes:"custom"`，`value`/`code`/`label` 都填变量名，`dataType` 与 `variableType` 一致 | 模型按语义自行命名，全编排不重复（重名时不报错，而是赋值给同名变量） | 灵活（模型自定义） |

> 命名、作用域、跨动作共享等通用规则见 prompt.md「变量与作用域」。

## 真实数据样本（循环内取 item 字段定义变量 sort）
```json
{
  "elementKey": "SetVariable",
  "params": {
    "inputs": {
      "variableType": "string",
      "variableValue": { "paramTypes": "custom", "value": "item[\"sort\"]", "code": "item[\"sort\"]", "label": "item[\"sort\"]", "dataType": "" }
    },
    "outputs": {
      "variableName": { "paramTypes": "custom", "value": "sort", "code": "sort", "label": "sort", "dataType": "string" }
    }
  }
}
```

## 参数示例（addNode 完整调用）
```json
{
  "elementKey": "SetVariable",
  "params": {
    "inputs": {
      "variableType": "number",
      "variableValue": { "paramTypes": "custom", "value": "0", "code": "0", "label": "0", "dataType": "number" }
    },
    "outputs": {
      "variableName": { "paramTypes": "custom", "value": "totalCount", "code": "totalCount", "label": "totalCount", "dataType": "number" }
    }
  }
}
```

## JS 表达式写法（variableValue 的 code 字段）
- 字面量：`0`、`"张三"`、`true`、`[]`、`{}`
- 组件值：`inbiz('EformNumber').value`
- 表达式：`inbiz('EformNumber').value * 1.1`（如打九折）
- 全局变量：`self.globalVariables['amount']`
- 上游局部变量：用 `paramTypes:"localVariable"`（不要自己拼 custom code）

不确定可用 code 时取现成引用对象：组件/列从 getPageComponents.ref、输入/输出参数从 getActionDetail.inputParamRefs/outputParamRefs、字典从 getDictionaryList 选分组→getDictionaryDetail 查字典项、全局变量从 getVariableList。

## 下游引用本变量
本元件产出的变量（如 `sort`）是局部变量，下游引用用 `paramTypes:"localVariable"`：
```json
{ "paramTypes": "localVariable", "value": "localVariable-sort", "label": "局部变量-sort", "code": "sort", "dataType": "string" }
```

## 使用示例
```
用户："定义个数字变量 count 初始0"
→ addNode(SetVariable, variableType="number", variableValue=0, variableName="count")
用户："把数字框的值乘1.1存到变量"
→ addNode(SetVariable, variableType="number", variableValue={paramTypes:custom, code:"inbiz('EformNumber').value * 1.1"}, variableName="discounted")
```

## 注意事项
- variableValue 必须用表达式对象，不能填裸数字/字符串
- variableName 用 paramTypes:custom，value/code/label 填变量名，dataType 与 variableType 一致
- 本元件产生新变量；改已有变量用 SetVariableValue（不产生新变量）
- 变量定义后，后续元件引用它时用 `{paramTypes:"localVariable", value:"localVariable-变量名", label:"局部变量-变量名", code:"变量名"}`
