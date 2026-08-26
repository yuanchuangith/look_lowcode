> 来源：action-design-tools/nodes/Loop/ForLoop/knowledge.md（同步于 2026-08-25）

# For 次数循环

> 元件 Key: `ForLoop`

## 适用场景
需要按固定次数或范围执行循环时使用。通过起始值、结束值和步长控制循环范围。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `start`（输入，必填） | 循环起始值，表达式对象 | **灵活**：字面量用 `paramTypes:"custom"`（如 `0`）；变量用 `paramTypes:"localVariable"`。默认 0 | 灵活 |
| `end`（输入，必填） | 循环结束值，表达式对象 | **灵活**：同 start。默认 10 | 灵活 |
| `step`（输入，可选） | 每次递增值，表达式对象 | **灵活**：同 start，可为负（倒序）。默认 1 | 灵活 |
| `loop_index`（输出） | 当前循环值变量名。键名固定 `loop_index` | **灵活**：变量名自己起（如 `i`）；值为表达式对象 `paramTypes:"custom"` | 自定义 |

> `loop_index` 产出局部变量，循环体内引用用 `paramTypes:"localVariable"`。块级元件，需用 `addNode(LoopEnd)` 显式关闭。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| start | number | 是 | **true** | 循环起始值（表达式对象），默认 0 |
| end | number | 是 | **true** | 循环结束值（表达式对象），默认 10 |
| step | number | 否 | **true** | 每次递增值（表达式对象），默认 1，可为负 |

### 输出参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| loop_index | number | 否 | **true** | 当前循环变量名（表达式对象，code 为变量名如 i） |

## 参数示例（addNode 完整调用）
```json
{
  "elementKey": "ForLoop",
  "params": {
    "inputs": {
      "start": { "paramTypes": "custom", "code": "0", "label": "0", "dataType": "number" },
      "end": { "paramTypes": "custom", "code": "10", "label": "10", "dataType": "number" },
      "step": { "paramTypes": "custom", "code": "1", "label": "1", "dataType": "number" }
    },
    "outputs": {
      "loop_index": { "paramTypes": "custom", "code": "i", "label": "i", "dataType": "number" }
    }
  }
}
```

### 用变量控制循环范围
```json
{
  "inputs": {
    "start": { "paramTypes": "custom", "code": "0", "label": "0", "dataType": "number" },
    "end": { "paramTypes": "localVariable", "code": "totalCount", "label": "totalCount", "dataType": "number" },
    "step": { "paramTypes": "custom", "code": "1", "label": "1", "dataType": "number" }
  },
  "outputs": {
    "loop_index": { "paramTypes": "custom", "code": "i", "label": "i", "dataType": "number" }
  }
}
```

## JS 表达式写法
- start/end/step 的 code 可填：
  - 字面量数字：`0`、`10`、`-1`（倒序）
  - 变量引用：`totalCount`、`inbiz('EformNumber').value`
- loop_index 用 paramTypes:custom，code 为循环变量名（如 `i`）

## 使用示例
```
用户："循环10次，每次弹个提示"
→ addNode(ForLoop, start=0, end=10, step=1, loop_index="i")
→ addNode(OpenMessageDialog, 内容=i)
伪代码：
FOR (i = 0 TO 10 STEP 1) {
  消息提示(内容=i)
}
用户："从0循环到数字框的值"
→ addNode(ForLoop, start=0, end={paramTypes:componentsVariable, code:"inbiz('EformNumber').value"}, step=1, loop_index="i")
```

## 注意事项
- **需 `addNode(LoopEnd)` 显式关闭**（不再自动生成结束标记）
- start/end/step 必须用表达式对象（即使是字面量数字也要包成 {paramTypes:custom, code:"0"}）
- 循环体内通过 loop_index 引用当前值（在子元件参数里用 {paramTypes:'localVariable', code:'i'}）
- step 为负可实现倒序循环
