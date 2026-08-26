> 来源：action-design-tools/nodes/TryCatch/Finally/knowledge.md（同步于 2026-08-25）

# FINALLY 最终执行

> 元件 Key: `Finally`

## 适用场景
无论 Try 块是否抛出异常（无论是否被 Catch 捕获），都会执行的清理逻辑。用于资源释放、状态重置等必须执行的收尾操作。

## 参数逐条说明

无输入参数、无输出参数。纯结构节点（同时是 endMarker 关闭前一个 try/catch body + levelMarker 开启 finally body）。

## 使用说明
- 必须放在 `Catch`（如有）之后、`EndTry` 之前
- 一个 TRY 块最多有一个 Finally
- Finally 内通常放：关闭连接、重置加载状态、隐藏遮罩等
- 添加 Finally 后结构为：`TRY {...} CATCH (err) {...} FINALLY {...} 结束异常处理`

## 参数说明
无参数（纯结构节点）。

## 使用示例
```
用户："不管接口成不成功，最后都把加载动画关掉"
→ addNode(Try)
→ addNode(SetVariable, 值=true)          // 开启加载
→ addNode(CallInterface, ...)
→ addNode(Catch)
→ addNode(OpenMessageDialog, 内容=err)
→ addNode(Finally)
→ addNode(SetVariableValue, 值=false)    // 关闭加载
```
伪代码：
```
TRY {
  loading = 定义变量(值=true)
  result = 调用接口(...)
} CATCH (err) {
  OpenMessageDialog(内容="err")
} FINALLY {
  设置变量值(loading, false)
}
```

## 注意事项
- Finally 与所属 Try 共享同一个 EndTry 结束标记
- 即使 Catch 内再次抛出异常，Finally 仍会执行
- 不需要错误处理的简单场景可只用 Try + Finally（不加 Catch）
