> 来源：action-design-tools/nodes/Condition/Else/knowledge.md（同步于 2026-08-25）

# ELSE 否则分支

> 元件 Key: `Else`

## 适用场景
当 IfCondition 的条件不满足（且所有 ElseIf 也不满足）时执行的逻辑。用于表达 if-else 结构的 else 分支。

## 参数逐条说明

无输入参数、无输出参数。纯结构节点，表达 if-else 的 else 分支。

## 使用说明
- 必须放在 `IfCondition`（或最后一个 `ElseIf`）之后、`IfEnd` 之前
- 一个 IF 块最多有一个 Else
- Else 内部可包含任意元件（包括嵌套 IF/循环等）
- 添加 Else 后，编排结构为：`IF (...) {...} ELSE {...} 结束判断`

## 参数说明
无参数（纯结构节点）。

## 使用示例
```
用户："金额大于100走A流程，否则走B流程"
→ addNode(IfCondition, 条件=金额>100)
→ [A流程元件]
→ addNode(Else)
→ [B流程元件]
```
伪代码：
```
IF (金额 > 100) {
  [A流程]
} ELSE {
  [B流程]
}
```

## 注意事项
- Else 是块级节点，会与所属 IfCondition 共享同一个 IfEnd 结束标记
- 若需多分支判断，用 ElseIf 而非多个 Else
