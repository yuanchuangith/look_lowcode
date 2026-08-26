> 来源：action-design-tools/nodes/Condition/FlowIsComplate/knowledge.md（同步于 2026-08-25）

# 流程是否完成

> 元件 Key: `FlowIsComplate`

## 适用场景
需要判断当前流程是否已经完成时使用。常用于流程结束后的后续处理逻辑。

## 参数逐条说明

无输入参数、无输出参数。自动判断当前流程整体状态。块级元件，配合 Else 使用。

## 参数说明

### 输入参数
无

### 输出参数
无

## 使用示例

```
IF_FLOW_COMPLETE {
  消息提示(内容="流程已完成")
}
```

## 注意事项
- 添加流程完成判断时会自动生成 IfEnd 结束标记
- 该元件无需输入参数，自动获取当前流程状态
