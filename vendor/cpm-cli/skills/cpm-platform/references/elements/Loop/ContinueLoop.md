> 来源：action-design-tools/nodes/Loop/ContinueLoop/knowledge.md（同步于 2026-08-25）

# 继续下一次循环

> 元件 Key: `ContinueLoop`

## 适用场景
需要在循环体内跳过当前迭代，直接进入下一次循环时使用。相当于编程语言中的 `continue` 语句。

## 参数逐条说明

无输入参数、无输出参数。纯结构节点，相当于编程语言中的 `continue`。

## 使用示例

```
FOR (item IN orderList) {
  IF (item.status == "已取消") {
    继续下一次循环      // 跳过本次剩余操作，进入下一次
  }
  // 处理未取消的订单
}
```

## 注意事项
- 只能在循环体（ForEachArray/WhileLoop/ForLoop 等）内使用
- 执行后跳过当前迭代剩余操作，直接进入下一次循环
- 与 `ExitLoop` 区别：ContinueLoop 跳过本次继续循环；ExitLoop 跳出整个循环
