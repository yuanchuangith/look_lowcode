> 来源：action-design-tools/nodes/DataProcessing/MathCalculation/knowledge.md（同步于 2026-08-25）

# 数学运算

> 元件 Key: `MathCalculation`

## 适用场景
需要对两个数值进行加、减、乘、除、取模运算时使用。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `numValue1`（输入，必填） | 数1，表达式对象 | **灵活**：组件值/局部变量/字面量 | 灵活 |
| `operatorMode`（输入，必填） | 运算符字面量 | **固定**：`+`/`-`/`*`/`/`/`%` 之一 | 固定枚举 |
| `numValue2`（输入，必填） | 数2，表达式对象 | **灵活**：同 numValue1 | 灵活 |
| `decimalDigit`（输入，可选） | 小数位数字面量 | **灵活**：数字，默认 0 | 灵活 |
| `calculationResults`（输出，必填） | 运算结果变量名。键名固定 `calculationResults` | **灵活**：变量名自己起；值为表达式对象 `paramTypes:"custom"` | 自定义 |

> `calculationResults` 产出局部变量，下游引用用 `paramTypes:"localVariable"`。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| numValue1 | number | 是 | 运算数1 |
| operatorMode | string | 是 | 运算符: +, -, *, /, % |
| numValue2 | number | 是 | 运算数2 |
| decimalDigit | number | 否 | 保留小数位数 |

### 输出参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| calculationResults | number | 是 | 运算结果 |

## 使用示例
```
result = 数学运算(数1=10, 运算符="+", 数2=20)
```
