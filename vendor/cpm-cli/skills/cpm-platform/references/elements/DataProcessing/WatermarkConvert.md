> 来源：action-design-tools/nodes/DataProcessing/WatermarkConvert/knowledge.md（同步于 2026-08-25）

# 水印转换

> 元件 Key: `WatermarkConvert`

## 适用场景
需要对数据添加水印或进行水印转换处理时使用。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `watermarkConfig`（输入，必填） | 水印配置，表达式对象 | **灵活**：水印配置对象 | 灵活 |
| `sourceData`（输入，必填） | 源数据，表达式对象 | **灵活**：数据对象/局部变量 | 灵活 |
| `variableName`（输出，必填） | 水印转换结果变量名 | **灵活**：变量名自己起；值为表达式对象 | 自定义 |

> 输出为局部变量，下游引用用 `paramTypes:"localVariable"`。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| watermarkConfig | object | 是 | 水印配置（包含水印类型、内容、位置等） |
| sourceData | object | 是 | 源数据 |

### 输出参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| variableName | object | 是 | 水印转换结果 |

## 使用示例
```
result = 水印转换(配置="水印配置项")
```
