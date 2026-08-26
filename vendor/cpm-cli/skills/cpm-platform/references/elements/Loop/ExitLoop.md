> 来源：action-design-tools/nodes/Loop/ExitLoop/knowledge.md（同步于 2026-08-25）

# 退出循环

> 元件 Key: `ExitLoop`

## 适用场景
需要在循环体内提前退出循环时使用。相当于编程语言中的 `break` 语句。

## 参数逐条说明

无输入参数、无输出参数。纯结构节点，相当于编程语言中的 `break`。

## 使用示例

```
FOR (item IN orderList) {
  IF (item.amount > 1000) {
    退出循环        // 立即跳出循环，不再执行后续迭代
  }
}
```

## 注意事项
- 只能在循环体（ForEachArray/WhileLoop/ForLoop 等）内使用
- 执行后立即跳出**当前**循环，不再执行后续迭代
- 与 `ContinueLoop` 区别：ExitLoop 是跳出整个循环；ContinueLoop 是跳过本次、继续下一次
