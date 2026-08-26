> 来源：action-design-tools/nodes/Message/OpenMessageDialog/knowledge.md（同步于 2026-08-25）

# 消息提示

> 元件 Key: `OpenMessageDialog`

## 适用场景
向用户弹出消息提示框（可设置类型与自动关闭延时），常用于操作结果反馈、校验失败提示。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `message`（输入，必填） | 消息内容，表达式对象 | **灵活**：通常是字符串字面量，用 `paramTypes:"custom"`，`value`/`code`/`label` 都填提示文本（如 `"请新增文件信息"`）。也可拼接变量/组件值 | 灵活 |
| `type`（输入，可选） | 消息类型枚举字面量 | **固定枚举**：`success`/`warning`/`error`/`info` 之一 | 固定枚举 |
| `duration`（输入，可选） | 自动关闭延时（秒），表达式对象 | **灵活**：数字，用 `paramTypes:"custom"`，如 `"3"`。省略则用默认值 | 灵活 |

> 无输出参数。消息类型参数名是 `type`（非 `messageType`）。

### 真实数据样本（校验失败提示）
```json
{
  "elementKey": "OpenMessageDialog",
  "params": {
    "inputs": {
      "message": { "paramTypes": "custom", "value": "请新增文件信息", "code": "请新增文件信息", "label": "请新增文件信息", "dataType": "" },
      "type": "error",
      "duration": { "paramTypes": "custom", "value": "3", "code": "3", "label": "3" }
    }
  }
}
```

## 使用示例
```
用户："提示保存成功"
→ addNode(OpenMessageDialog, message="保存成功", type="success")
用户："校验失败提示错误"
→ addNode(OpenMessageDialog, message="请新增文件信息", type="error", duration=3)
```

## 注意事项
- 消息类型参数名是 `type`（非 `messageType`），是固定枚举字面量
- `message` 是表达式对象；`type` 是字符串字面量；`duration` 是表达式对象
- 这是终端提示（执行后继续往下走），要中途退出动作请用 `ExitAction`，二者不要混
