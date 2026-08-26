> 来源：action-design-tools/nodes/Condition/ElseIf/knowledge.md（同步于 2026-08-25）

# ELSEIF 否则如果分支

> 元件 Key: `ElseIf`

## 适用场景
当 IfCondition 的条件不满足时，再判断另一个条件。用于表达多分支判断（if-else if-else 结构）。

## 使用说明
- 必须放在 `IfCondition` 之后、`Else`（如有）之前、`IfEnd` 之前
- 可以连续多个 ElseIf 形成多分支
- 添加 ElseIf 后结构为：`IF (...) {...} ELSEIF (...) {...} ELSE {...} 结束判断`

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `condition`（输入，必填） | 条件树，**结构与取值规则完全同 IfCondition** | **半固定**：`{Logic, Filters:[{target, equalTo, value}]}`。target/value 取值来源、localVariable 引用、objectAttribute 取属性写法，全部见 `IfCondition` 的参数逐条说明 | 结构固定，内容灵活 |

> 无输出参数。`condition` 的所有规则与 IfCondition 完全一致，直接参考 IfCondition/knowledge.md。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| condition | object | 是 | 条件结构 `{Logic:'And'/'Or', Filters:[{target, equalTo, value}]}` |

#### condition 结构（与 IfCondition 相同）
```json
{
  "Logic": "And",
  "Filters": [
    {
      "target": { "paramTypes": "componentsVariable", "code": "inbiz('EformNumber').value", "label": "数字框", "dataType": "number" },
      "equalTo": "GreaterThan",
      "value": { "paramTypes": "custom", "code": "50", "label": "50", "dataType": "number" }
    }
  ]
}
```
- `Logic`: And/Or，多条件连接方式
- `Filters[].target`: 左操作数（表达式对象）
- `Filters[].equalTo`: 比较运算符（Equal/NotEqual/GreaterThan/GreaterThanOrEqual/LessThan/LessThanOrEqual/Contains/EqualNull/NotEqualNull）
- `Filters[].value`: 右操作数（表达式对象）

## 使用示例
```
用户："大于100走A，大于50走B，否则走C"
→ addNode(IfCondition, 条件=金额>100)  + [A流程]
→ addNode(ElseIf, 条件=金额>50)        + [B流程]
→ addNode(Else)                         + [C流程]
```

## 注意事项
- ElseIf 与所属 IfCondition 共享同一个 IfEnd 结束标记
- 多个 ElseIf 按顺序判断，命中第一个满足的即执行其分支

## 自动补全（expand 层）
本元件支持 expand 自动补全（与 IfCondition 同构），模型**只需给设计意图字段**，以下壳字段由工具自动补全，**不要手写**：
- `condition` 条件树每个节点的 `Id`(GUID)
- 叶子节点 `target`/`value` 表达式对象缺失的 `value`/`dataType`
模型给：`condition`(Logic + 叶子 target/equalTo/value 条件树)。
