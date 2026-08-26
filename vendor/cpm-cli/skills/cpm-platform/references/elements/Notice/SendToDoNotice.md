> 来源：action-design-tools/nodes/Notice/SendToDoNotice/knowledge.md（同步于 2026-08-25）

# 发送待办通知

> 元件 Key: `SendToDoNotice`

## 适用场景
向指定用户发送待办任务通知（待办提醒、任务指派通知等）。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `noticeConfig`（输入，必填） | 通知配置对象，包含接收人、标题、内容等 | **半固定**：配置对象，具体字段结构以实际使用时 `getElementDetail` 返回的 schema 为准。接收人通常引用用户 id 变量（`paramTypes:"localVariable"`） | 结构以 schema 为准 |

> 无输出参数。

## 使用示例
```
用户："给审批人发个待办通知"
→ addNode(SendToDoNotice, noticeConfig={接收人=用户id变量, 标题="...", 内容="..."})
```

## 注意事项
- `noticeConfig` 是配置对象；不确定字段结构时先调 `getElementDetail` 查 inputParams 的 schema
- 接收人引用用户 id 时用变量引用对象，不要硬编码用户名
- 与 `PushMessage` 区别：PushMessage 按消息模板推送（需模板 id）；SendToDoNotice 发待办通知
