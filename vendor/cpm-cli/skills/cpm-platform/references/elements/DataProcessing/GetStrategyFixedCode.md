> 来源：action-design-tools/nodes/DataProcessing/GetStrategyFixedCode/knowledge.md（同步于 2026-08-25）

# 获取策略固定字符

> 元件 Key: `GetStrategyFixedCode`

## 适用场景
需要获取编号策略中定义的固定字符时使用，常用于编号生成前的预处理。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `codeStrategySource`（输入，必填） | 编号源 `{id, label, name}` | **固定**：`label`/`name` 是设计意图，`id` 平台派生 | 固定结构 |
| `codeStrategyDesign`（输入，必填） | 编号策略引用，表达式对象 | **固定**：从编号策略配置取策略引用 | 固定结构 |
| `codeStrategyContext`（输入，可选） | 策略上下文，表达式对象 | **灵活**：按业务填 | 灵活 |
| `variableName`（输出，必填） | 固定字符结果变量名 | **灵活**：变量名自己起；值为表达式对象，`dataType:"string"` | 自定义 |

> 编号策略引用**必须从编号策略配置取真实值**。输出为局部变量，下游引用用 `paramTypes:"localVariable"`。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| codeStrategySource | string | 是 | 编号源 |
| codeStrategy | string | 是 | 编号策略 |

### 输出参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| requestResult | string | 是 | 固定字符结果 |

## 使用示例
```
result = 获取固定编号(源="订单编号", 策略="年月日流水")
```
