> 来源：action-design-tools/nodes/Control/ExitAction/knowledge.md（同步于 2026-08-25）

# 退出动作

> 元件 Key: `ExitAction`

## 适用场景
提前终止当前动作的执行（相当于编程语言中的 `return`）。常用于校验不通过时中断、达到条件时提前返回。可携带返回值供调用方（CallAction）接收。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `returnValue`（输入，可选） | 退出时携带的返回值，表达式对象 | **灵活**：字面量（如 `true`/`false`/`null`）、局部变量（用 `paramTypes:"localVariable"`）、组件值等。省略则无返回值 | 灵活 |

> 无输出参数。本元件**终止当前动作**，其后的节点不再执行。

### 真实数据样本（校验拦截，返回 true）
```json
{
  "elementKey": "ExitAction",
  "params": {
    "inputs": {
      "returnValue": { "paramTypes": "custom", "value": "true", "code": "true", "label": "true", "dataType": "" }
    }
  }
}
```

## 使用示例
```
用户："校验不过就退出"
→ addNode(IfCondition, 条件=校验不通过)
→ [IF 块内] addNode(ExitAction, returnValue=true)
用户："直接退出，不返回值"
→ addNode(ExitAction)
```
伪代码：
```
IF (校验不通过) {
  退出动作(返回值=true)   // 之后的节点不再执行
}
```

## 注意事项
- 执行后立即终止当前动作，后续元件不再执行
- `returnValue` 可选，不需要返回值时省略整个参数；它是表达式对象（非裸值）
- 携带的返回值可被 `CallAction` 的输出参数接收
- 与 `OpenMessageDialog` 区别：消息提示只是弹窗、动作继续执行；`ExitAction` 是真正退出
