> 来源：action-design-tools/nodes/Debug/OutputLog/knowledge.md（同步于 2026-08-25）

# 输出日志

> 元件 Key: `OutputLog`

## 适用场景
输出一条调试日志（可拼接多个变量/字面量片段）到控制台。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `params`（输入，必填） | 日志片段数组，每项 `{id, name}` | **半固定**：`name` 是表达式对象（每个日志片段的来源）；`id` 平台自动填，**不要手写**。各片段按顺序拼成一条日志 | 结构固定，name 内容灵活 |

### name 片段的值从哪来
- 字面量文本：`paramTypes:"custom"`，code 填字符串（如 `"orderId="`）
- 上游局部变量：`paramTypes:"localVariable"`（`value:"localVariable-{变量名}"`）
- 组件值/系统变量等：从对应工具取引用对象

### 真实数据样本（拼接两个局部变量）
```json
{
  "elementKey": "OutputLog",
  "params": {
    "inputs": {
      "params": [
        { "name": { "paramTypes": "localVariable", "value": "localVariable-fixKey", "code": "fixKey", "label": "局部变量-fixKey", "dataType": "string" } },
        { "name": { "paramTypes": "localVariable", "value": "localVariable-outKey", "code": "outKey", "label": "局部变量-outKey", "dataType": "string" } }
      ]
    }
  }
}
```

## 参数示例
```json
{
  "elementKey": "OutputLog",
  "params": {
    "inputs": { "params": [{ "name": { "paramTypes": "custom", "code": "\"orderId=\"", "label": "\"orderId=\"" } }, { "name": { "paramTypes": "localVariable", "code": "orderId", "label": "局部变量-orderId" } }] }
  }
}
```

## 使用示例
```
日志输出(内容="orderId=, 局部变量-orderId")
```

## 自动补全（expand 层）
本元件支持 expand 自动补全，模型**只需给设计意图字段**，以下壳字段由工具自动补全，**不要手写**：
- `params[]` 每项的 `id`
- 各 `name` 表达式对象缺失的 `value`/`dataType`
模型给：`params[]{name}`（每个日志片段的来源）。
