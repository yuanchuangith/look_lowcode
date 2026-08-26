> 来源：action-design-tools/nodes/Network/PushMessage/knowledge.md（同步于 2026-08-25）

# 推送消息

> 元件 Key: `PushMessage`

## 适用场景
按消息模板向目标用户推送消息通知（邮件/站内信等）。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `messgeTemplate`（输入，必填） | 消息模板引用 `{label, id, messagePlatform, messageContent, ...}` | **固定**：`label`(模板中文名)是设计意图，从消息模板配置取真实模板；`id`(GUID)/`messageContent`/`notificaObject` 等为平台元数据，**不要手写**。⚠️ **键名是 `messgeTemplate`（平台历史拼写，缺一个 a），不是 `messageTemplate`** | 固定结构，label/真实id取自配置 |
| `attachUsers`（输入，必填） | 接收消息的用户，表达式对象 | **灵活**：通常引用用户 id 变量（`paramTypes:"localVariable"`）或系统变量（当前用户ID等） | 灵活 |
| `info`（输入，可选） | 附加信息，表达式对象 | **灵活**：按业务填 | 灵活 |
| `requestResult`（输出） | 推送结果变量名。键名固定 `requestResult` | **灵活**：变量名自己起；值为表达式对象 `paramTypes:"custom"` | 自定义 |

> `requestResult` 产出局部变量，下游引用用 `paramTypes:"localVariable"`。

## 参数示例
```json
{
  "elementKey": "PushMessage",
  "params": {
    "inputs": {
      "messgeTemplate": { "label": "记录状态变更通知", "id": "<从消息模板配置取的真实模板id>", "messagePlatform": "email" },
      "attachUsers": { "paramTypes": "localVariable", "value": "localVariable-creatorId", "code": "creatorId", "label": "局部变量-creatorId", "dataType": "string" }
    },
    "outputs": { "requestResult": { "paramTypes": "custom", "value": "pushResult", "code": "pushResult", "label": "pushResult", "dataType": "string" } }
  }
}
```

## 使用示例
```
用户："用'记录状态变更通知'模板给创建人发消息"
→ 从消息模板配置取真实模板 id
→ addNode(PushMessage, messgeTemplate={label, id}, attachUsers={localVariable引用creatorId})
```

## 注意事项
- ⚠️ 键名是 **`messgeTemplate`**（平台历史拼写，缺一个 a），写成 `messageTemplate` 会失败
- 消息模板 id **必须从消息模板配置取真实值**，禁止凭模板名猜
- **平台自动生成、模型不要手写**：messgeTemplate 的 messageContent/notificaObject/creationTime/creatorId 等元数据、id(GUID)
