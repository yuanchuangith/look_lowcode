> 来源：action-design-tools/nodes/TryCatch/ThrowError/knowledge.md（同步于 2026-08-25）

# 抛出异常

> 元件 Key: `ThrowError`

## 适用场景
主动抛出异常以中断当前执行流程。抛出的异常可被外层 `Try` 块捕获，未捕获则整个动作失败。常用于业务规则校验失败。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `errorMessage`（输入，必填） | 错误信息，**表达式对象**（不是裸字符串） | **灵活**：通常用 `paramTypes:"custom"`，`value`/`code`/`label` 都填错误消息文本（如 `"金额不能为负数"`）。也可拼接变量 | 灵活 |

> 无输出参数。抛出的异常可被外层 `Try` 块捕获，未捕获则整个动作失败。

### 真实数据片段
```json
"errorMessage": { "paramTypes": "custom", "value": "校验失败", "code": "校验失败", "label": "校验失败", "dataType": "string" }
```

## 使用示例

### 校验失败时抛出异常
```
TRY {
  IF (金额 < 0) {
    抛出异常(信息="金额不能为负数")
  }
} CATCH (err) {
  消息提示(内容=err.message)
}
```

### 业务规则校验
```
IF (库存 < 需求数量) {
  抛出异常(信息="库存不足，无法提交")
}
```

## 注意事项
- `errorMessage` 是**表达式对象**（非裸字符串），用 `paramTypes:"custom"` 填消息文本
- 抛出异常后中断当前执行流程；未被 TRY-CATCH 捕获则整个动作失败
- 与 `ExitAction` 区别：ExitAction 是正常退出（可带返回值）；ThrowError 是异常中断
