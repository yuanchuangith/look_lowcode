> 来源：action-design-tools/nodes/Control/CallEvents/knowledge.md（同步于 2026-08-25）

# 发送事件通知

> 元件 Key: `CallEvents`

## 适用场景
向系统**发送一个事件通知**（可携带参数），触发所有订阅该事件的绑定动作。例如文件作废时发送 `文件作废事件`，携带 file_id/file_name/file_code 等参数。

> 区别于 `ComponentEvent`（给组件事件绑定动作）：CallEvents 是"发送方"，广播一个事件；ComponentEvent 是"绑定方"，声明某组件事件触发时执行什么。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `conf`（输入，必填） | 事件通知配置 `{event, paramSettings}` | **半固定**：见下方子结构。`event` 从已注册事件清单取；`paramSettings` 随事件定义变化 | 结构固定，内容随事件 |
| `conf.event` | 要发送的事件 `{eventCode, eventName}` | **固定**：`eventCode`/`eventName` 从 `getEventList` 取真实值，**不要凭名字猜** | 固定值，取自工具 |
| `conf.paramSettings[]` | 随事件传递的参数数组，每项 `{id, name, value}` | **半固定**：`name` 是参数名(随事件定义)；`value` 是表达式对象(灵活)；`id` 平台自动填 | 结构固定，name 随事件 |

> 无输出参数。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| conf | object | 是 | false（结构对象） | 事件通知配置（见下） |

#### conf 结构
```jsonc
{
  "event": { "eventCode": "DocumentInvalid", "eventName": "文件作废事件" },  // 要发送的事件
  "paramSettings": [                        // 随事件传递的参数（可变个数）
    {
      "id": "<平台生成>",
      "name": "file_id",                    // 参数名
      "value": {                            // 参数值（表达式对象）
        "paramTypes": "inputParam", "code": "file_id", "label": "输入参数-file_id", "dataType": "string"
      }
    }
  ]
}
```

### 输出参数
无。

## 参数示例
```json
{
  "elementKey": "CallEvents",
  "params": {
    "inputs": {
      "conf": {
        "event": { "eventCode": "DocumentInvalid", "eventName": "文件作废事件" },
        "paramSettings": [
          { "name": "file_id", "value": { "paramTypes": "inputParam", "code": "file_id", "label": "输入参数-file_id", "dataType": "string" } },
          { "name": "file_name", "value": { "paramTypes": "inputParam", "code": "file_name", "label": "输入参数-file_name", "dataType": "string" } }
        ]
      }
    }
  }
}
```

## 使用示例
```
发送事件通知(事件="文件作废事件", 参数=[file_id=输入参数-file_id, file_name=输入参数-file_name])
```

## 注意事项
- `event.eventCode`/`eventName` 标识要发送的事件（从已注册的事件清单取）。
- `paramSettings` 是**变量参数列表**，个数/名字随事件定义变化，每项一个 `name` + 表达式对象 `value`。
- **平台自动生成、模型不要手写**：`paramSettings[].id`。
