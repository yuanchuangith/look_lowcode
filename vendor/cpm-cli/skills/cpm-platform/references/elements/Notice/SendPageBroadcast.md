> 来源：action-design-tools/nodes/Notice/SendPageBroadcast/knowledge.md（同步于 2026-08-25）

# 发送页面广播

> 元件 Key: `SendPageBroadcast`

## 适用场景
需要跨页面通信，向其他页面发送消息时使用。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `eventName`（输入，必填） | 要广播的事件名字面量 | **固定**：约定的事件名（如 `Document.ReLoadAppendixList`），从已注册广播事件取 | 固定值 |

> 无输出参数。触发订阅了该事件的页面动作（如刷新附录列表）。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| message | string | 是 | 消息内容 |
| targetPage | string | 是 | 目标页面 |

### 输出参数
无

## 使用示例
```
发送页面广播(消息="xxx")
```
