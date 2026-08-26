> 来源：action-design-tools/nodes/DataProcessing/DynamicCalculation/knowledge.md（同步于 2026-08-25）

# 动态计算

> 元件 Key: `DynamicCalculation`

## 适用场景
需要根据动态表达式进行计算时使用，支持包含变量引用的复杂表达式。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `expression`（输入，必填） | 计算表达式，表达式对象 | **灵活**：包含变量引用的计算式，用 `paramTypes:"custom"`，code 填表达式（如 `amount * 0.1 + base`）。变量直接写变量名 | 灵活 |
| `calculationResult`（输出，必填） | 计算结果变量名 | **灵活**：变量名自己起；值为表达式对象 `paramTypes:"custom"` | 自定义 |

> 输出为局部变量，下游引用用 `paramTypes:"localVariable"`。与 MathCalculation 区别：MathCalculation 只做两个数的四则运算；DynamicCalculation 支持含变量和复杂运算符的任意表达式。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| expression | string | 是 | 计算表达式（支持变量引用） |

### 输出参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| result | object | 是 | 计算结果 |

## 使用示例
```
result = 动态计算(表达式="(price * quantity) * discount")
```
