> 来源：action-design-tools/nodes/Control/CallAction/knowledge.md（同步于 2026-08-25）

# 调用子动作

> 元件 Key: `CallAction`

## 适用场景
调用当前页面中已定义的子动作，可传递动态实参、接收其返回值。常用于把复杂逻辑拆成多个子动作再在主动作里按需调用。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `actionName`（输入，必填） | 子动作选择 `{value, label, actionType, isActionSelect}` | **固定**：`value`/`label` 从 `getActionList` 取已存在动作；`actionType`/`isActionSelect` 平台自动填，**不要手写** | 固定结构，取自工具 |
| `param_<形参名>`（输入，可选） | 给被调子动作传实参。键名 `param_` + 形参名 | **半固定**：形参名从 `getActionList` 返回的目标动作项的 `inputParamRefs` 取；实参值是表达式对象且**必须带 `paramName`(=形参名)**。引用当前动作入参时从 `getActionDetail.inputParamRefs` 取现成对象 | 键名取自工具，值灵活 |
| `<返回参数名对应的输出键>`（输出，可选） | 接收被调子动作的返回值 | **灵活**：**被调子动作有几个返回参数，就写几个输出键**，每个键值为表达式对象，`paramName`=返回参数名、`code`=接收变量名。键名用 GUID 或 `out_<返回参数名>` 语义键（expand 层转 GUID） | 自定义 |

## ⚠️ 传实参的正确做法

调用带形参的子动作时，**从 `getActionList` 返回的目标动作项里取 `inputParamRefs`（形参清单）**，从中拿每个形参的 `paramName`。

形参清单 → 实参的映射规则：
- 每个 `inputParamRefs` 项对应一个实参，**键名写 `param_<paramName>`**
- 实参值是表达式对象，**`paramName` 字段必须等于该形参名**（缺失会导致运行时取不到入参值）
- `paramTypes/value/code/dataType/label` 按实参的实际来源填

### 带实参的完整示例
假设 `getActionList` 返回的子动作「数据校验」的 `inputParamRefs` 里有形参 `type`（paramName=type）：
```json
{
  "inputs": {
    "actionName": { "value": "m5jke35ox", "label": "数据校验", "actionType": "js", "isActionSelect": true },
    "param_type": {
      "paramTypes": "inputParam", "value": "<当前动作入参key>", "code": "type", "paramName": "type",
      "label": "输入参数-type", "dataType": "string"
    }
  }
}
```

## ⚠️ 接收返回值的正确做法

调用**有返回值**的子动作时，**从 `getActionDetail` 返回的目标动作项里取 `outputParamRefs`（返回参数清单）**，从中拿每个返回参数的 `paramName`。

返回参数清单 → 输出绑定的映射规则：
- **每个 `outputParamRefs` 项对应一个输出键**（不要把整个返回值塞进单个对象！）
- 每个输出键值为表达式对象，**`paramName` 字段必须等于该返回参数名**（缺失会让前端生成 `returnCodeName['undefined']`，取不到值）
- `code` 字段 = 接收该返回参数的变量名（自己起，有语义、全编排不重复）
- 键名用 GUID 或 `out_<返回参数名>` 语义键（expand 层自动转 GUID）

### 带返回值的完整示例
假设 `getActionDetail` 返回的子动作「生成文件编号」的 `outputParamRefs` 里有返回参数 `code`（paramName=code）：
```json
{
  "inputs": {
    "actionName": { "value": "m4v8wxn2k", "label": "生成文件编号", "actionType": "csharp", "isActionSelect": true }
  },
  "outputs": {
    "out_code": {
      "paramTypes": "custom", "value": "fileCode", "code": "fileCode", "paramName": "code",
      "label": "fileCode", "dataType": "string"
    }
  }
}
```
> 多个返回参数时，每个返回参数写一个输出键（如子动作返回 `success`+`newId`，就写 `out_success` + `out_newId` 两个键）。

## 使用示例
```
调用子动作("数据校验")                         // 无参调用
调用子动作("计算总价", 单价=页面组件-单价框)     // 带实参调用，需先查子动作形参
```

## 注意事项
- 调用前需确保目标子动作已定义；**带形参的子动作，从 `getActionList` 返回项的 `inputParamRefs` 拿形参名**，不要凭子动作名猜形参
- **有返回值的子动作，从 `getActionDetail` 返回项的 `outputParamRefs` 拿返回参数名**，每个返回参数写一个输出键（不要用单个 `_dynamicOutput` 键塞整个返回值，那会让前端取不到具体字段）
- `actionName` 必须通过选择器选择有效的子动作（从 getActionList 取），不能手动输入
- **平台自动生成、模型不要手写**：实参/输出绑定的 GUID 键名（用 `param_<形参名>` / `out_<返回参数名>` 即可，expand 层自动转 GUID）、actionName 的 GUID id/isActionSelect
- **实参/输出绑定的 `paramName` 字段必填**（= 形参名/返回参数名），缺失会被 addNode 校验拦截，运行时也会取不到值
