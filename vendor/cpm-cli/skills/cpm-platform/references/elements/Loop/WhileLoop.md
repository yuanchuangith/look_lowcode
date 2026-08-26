> 来源：action-design-tools/nodes/Loop/WhileLoop/knowledge.md（同步于 2026-08-25）

# While 条件循环

> 元件 Key: `WhileLoop`

## 适用场景
需要根据条件动态控制循环次数时使用。当条件为真时持续执行循环体，直到条件为假时退出。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `condition`（输入，必填） | 循环条件树，**格式同 IfCondition.condition** | **半固定**：`{Logic, Filters:[{target, equalTo, value}]}`。target/value 是表达式对象（取值来源同 IfCondition，见其参数逐条说明）；`Logic` 固定枚举 And/Or | 结构固定，内容灵活 |

> 无输出参数。块级元件，**需 `addNode(LoopEnd)` 显式关闭**。condition 的 target/value 取值规则、localVariable 引用、objectAttribute 取属性写法，**完全同 IfCondition**（见 IfCondition/knowledge.md）。**确保循环体内有使条件最终为假的逻辑，避免死循环**。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| condition | object | 是 | 条件配置，格式同 IfCondition: `{ Logic: "And"/"Or", Filters: [...] }` |

### 条件格式
每个 Filter 包含:
- `target`: 左侧值（变量/常量/组件属性）
- `equalTo`: 比较运算符（Equal/NotEqual/GreaterThan/LessThan/Contains 等）
- `value`: 右侧值

### 输出参数
无

## 使用示例

```
WHILE (计数器 < 10) {
  设置变量(变量=计数器, 值=计数器 + 1)
}
```

## 注意事项
- **需 `addNode(LoopEnd)` 显式关闭**（不再自动生成结束标记）
- 确保循环体内有使条件最终为假的逻辑，避免死循环
- 删除循环时会级联删除内部所有子节点
