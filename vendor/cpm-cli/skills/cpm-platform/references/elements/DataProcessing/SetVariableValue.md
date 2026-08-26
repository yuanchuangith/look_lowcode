> 来源：action-design-tools/nodes/DataProcessing/SetVariableValue/knowledge.md（同步于 2026-08-25）

# 设置变量值

> 元件 Key: `SetVariableValue`

## 适用场景
修改已有变量（用 SetVariable 定义的局部变量，或全局变量）的值，或其某个属性。

> 本元件【修改】已有变量，不产生新变量（无输出参数）。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `variableName` | 要改的已有变量的引用对象（表达式对象） | 局部变量用 `paramTypes:"localVariable"`（`value:"localVariable-{变量名}"`，`code:"{变量名}"`，`dataType` 同变量类型）；全局变量用 `paramTypes:"globalVariable"`（从 getVariableList 取）。**不要用 custom 自己拼变量名** | 固定（取自已存在的变量） |
| `attributeName` | 属性名（仅当变量为 object/array 时填，如 `name` 或 `["key"]`） | 取自该变量的结构（已存在的属性/键名） | 半固定（依变量结构；非 object/array 时留空） |
| `attributeValue` | 要设置的新值，表达式对象 `{paramTypes,value,code,label,dataType}` | code 可填：字面量(`100`/`"张三"`/`true`/`[]`/`{}`)、组件值 `inbiz('id').value`、表达式、其它变量 `otherVar` | 灵活（模型自定义） |

> 无输出参数。本元件修改已有变量，不产生新变量。

## 真实数据样本（改局部变量 tempChangeDetails 的值为排序后列表）
```json
{
  "elementKey": "SetVariableValue",
  "params": {
    "inputs": {
      "variableName": { "paramTypes": "localVariable", "value": "localVariable-tempChangeDetails", "dataType": "object", "label": "局部变量-tempChangeDetails", "code": "tempChangeDetails" },
      "attributeValue": { "paramTypes": "custom", "value": "tempChangeDetails.OrderBy(...).ToList()", "code": "tempChangeDetails.OrderBy(...).ToList()", "label": "...", "dataType": "" }
    }
  }
}
```

### 设置对象属性的场景（生成 `user.name = "李四"`）
```json
{
  "inputs": {
    "variableName": { "paramTypes": "localVariable", "value": "localVariable-user", "code": "user", "label": "局部变量-user", "dataType": "object" },
    "attributeName": "name",
    "attributeValue": { "paramTypes": "custom", "code": "\"李四\"", "label": "李四", "dataType": "string" }
  }
}
```

## 参数示例（addNode 完整调用）
```json
{
  "elementKey": "SetVariableValue",
  "params": {
    "inputs": {
      "variableName": { "paramTypes": "localVariable", "value": "localVariable-totalCount", "code": "totalCount", "label": "totalCount", "dataType": "number" },
      "attributeValue": { "paramTypes": "custom", "value": "100", "code": "100", "label": "100", "dataType": "number" }
    }
  }
}
```

## JS 表达式写法（code 字段）
- variableName 用 localVariable/globalVariable 引用对象；局部变量 code 即变量名，全局变量从 getVariableList 查
- attributeValue 的 code 可填：
  - 字面量：`100`、`"张三"`、`true`、`[]`、`{}`
  - 组件值：`inbiz('EformNumber').value`
  - 表达式：`inbiz('EformNumber').value + inbiz('EformNumber2').value`
  - 其它变量：`otherVar`（建议也用 localVariable 引用对象而非 custom）

## 使用示例
```
用户："把 count 设成 100"
→ addNode(SetVariableValue, variableName={localVariable引用count}, attributeValue=100)
用户："把 user 的 name 改成张三"
→ addNode(SetVariableValue, variableName={localVariable引用user}, attributeName="name", attributeValue="张三")
用户："把 count 加上数字框的值"
→ addNode(SetVariableValue, variableName={localVariable引用count}, attributeValue={paramTypes:custom, code:"count + inbiz('EformNumber').value"})
```

## 注意事项
- variableName 必须是已存在的变量（先 SetVariable 定义或为全局变量），用 localVariable/globalVariable 引用对象，**不要用 custom 自己拼**
- attributeName 仅当变量是 object/array 时有意义，会生成 `变量.属性 = 值` 或 `变量[key] = 值`
- attributeValue 必须用表达式对象
