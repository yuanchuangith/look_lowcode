> 来源：action-design-tools/nodes/Notice/SubscriptionPageBroadcast/knowledge.md（同步于 2026-08-25）

# 订阅页面广播

> 元件 Key: `SubscriptionPageBroadcast`

## 适用场景
需要监听其他页面发送的广播消息并触发对应动作时使用。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `eventName`（输入，必填） | 要订阅的事件名字面量 | **固定**：约定的事件名（与 SendPageBroadcast 的 eventName 对应） | 固定值 |
| `action`（输入，必填） | 收到广播时触发的动作 `{value, label, ...}` | **固定**：从 `getActionList` 取已存在动作 | 固定结构，取自工具 |

> 无输出参数。声明性绑定（监听事件→执行动作），与 SendPageBroadcast 配合。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| eventName | string | 是 | 事件名 |
| actionName | string | 是 | 触发的动作名称 |

### 输出参数
无

## 使用示例
```
订阅页面广播(事件="xxx", 动作="yyy")
```
