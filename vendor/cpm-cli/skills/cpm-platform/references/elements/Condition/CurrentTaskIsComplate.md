> 来源：action-design-tools/nodes/Condition/CurrentTaskIsComplate/knowledge.md（同步于 2026-08-25）

# 当前流程任务是否完成

> 元件 Key: `CurrentTaskIsComplate`

## 适用场景
需要判断当前正在执行的流程任务是否已完成时使用。与 FlowTaskIsComplate 的区别在于无需手动指定任务ID，自动获取当前任务状态。

## 参数逐条说明

无输入参数、无输出参数。自动判断当前流程任务状态（与 FlowTaskIsComplate 区别：无需手动指定任务 ID）。块级元件，配合 Else 使用。

## 参数说明

### 输入参数
无

### 输出参数
无

## 使用示例

```
IF_CURRENT_TASK_COMPLETE {
  消息提示(内容="当前任务已完成")
}
```

## 注意事项
- 添加当前任务完成判断时会自动生成 IfEnd 结束标记
- 该元件无需输入参数，自动获取当前任务状态
