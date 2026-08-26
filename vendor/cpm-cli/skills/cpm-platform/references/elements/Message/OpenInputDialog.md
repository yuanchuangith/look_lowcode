> 来源：action-design-tools/nodes/Message/OpenInputDialog/knowledge.md（同步于 2026-08-25）

# 输入对话框

> 元件 Key: `OpenInputDialog`

## 适用场景
弹出对话框要求用户输入内容，例如填写审批意见、输入备注、输入拒绝原因等。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `title`（输入，可选） | 对话框标题，表达式对象 | **灵活**：字符串文本，用 `paramTypes:"custom"` | 灵活 |
| `inputConfig`（输入，必填） | 输入配置（类型、占位符、默认值等），表达式对象 | **灵活**：按业务填配置 | 灵活 |
| `inputResult`（输出） | 用户输入结果变量名 | **灵活**：变量名自己起；值为表达式对象 `paramTypes:"custom"`，`dataType:"string"` | 自定义 |

> `inputResult` 产出局部变量，下游引用用 `paramTypes:"localVariable"`。

## 使用示例
```
result = 输入对话框(标题="请输入", 配置={placeholder: "请输入审批意见"})
```

## 注意事项
- `title`/`inputConfig` 是表达式对象
- `inputResult` 是局部变量，配合 IfCondition 判断用户是否输入了内容
