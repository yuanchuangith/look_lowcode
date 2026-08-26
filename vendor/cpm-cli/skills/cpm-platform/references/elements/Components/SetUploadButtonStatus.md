> 来源：action-design-tools/nodes/Components/SetUploadButtonStatus/knowledge.md（同步于 2026-08-25）

# 设置上传按钮状态

> 元件 Key: `SetUploadButtonStatus`

## 适用场景
需要动态控制上传组件按钮的可用状态时使用。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `name`（输入，必填） | 组件名称字面量 | **固定**：从 `getPageComponents` 取上传组件标识 | 固定值，取自工具 |
| `status`（输入，必填） | 状态字面量 | **固定**：可用状态枚举（如 enabled/disabled） | 固定枚举 |

> 无输出参数。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| name | string | 是 | 组件名称 |
| status | string | 是 | 状态值（如 disabled/enabled） |

### 输出参数
无

## 使用示例
```
设置上传按钮状态(组件="xxx", 状态="disabled")
```
