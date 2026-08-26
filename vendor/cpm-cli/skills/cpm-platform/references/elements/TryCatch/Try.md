> 来源：action-design-tools/nodes/TryCatch/Try/knowledge.md（同步于 2026-08-25）

# TRY 异常处理

> 元件 Key: `Try`

## 适用场景
需要对可能出错的操作进行异常捕获和处理时使用。提供完整的 TRY-CATCH-FINALLY 结构，确保异常不会导致整个动作崩溃。

## 参数逐条说明

无输入参数、无输出参数。纯结构节点（块级，**需 `addNode(EndTry)` 显式关闭**）。CATCH 分支内可通过 `err` 对象访问异常信息（如 `err.message`）。

## 结构说明
Try 元件会生成完整的异常处理结构，包含三个分支：
- **TRY 分支**：放置可能出错的逻辑
- **CATCH 分支**：异常发生时执行的逻辑，可访问错误信息 err
- **FINALLY 分支**：无论是否异常都会执行的清理逻辑

## 使用示例

```
TRY {
  数据 = 查询数据(条件={...})
  设置变量(变量=result, 值=数据)
} CATCH (err) {
  消息提示(内容="查询失败: " + err.message)
} FINALLY {
  设置变量(变量=loading, 值=false)
}
```

## 注意事项
- **需 `addNode(EndTry)` 显式关闭**（不再自动生成结束标记）
- CATCH 分支中可通过 err 对象获取异常信息
- FINALLY 分支中的操作一定会执行，适合做资源清理
