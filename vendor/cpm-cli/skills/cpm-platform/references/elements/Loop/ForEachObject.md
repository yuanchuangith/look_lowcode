> 来源：action-design-tools/nodes/Loop/ForEachObject/knowledge.md（同步于 2026-08-25）

# ForEach 对象遍历

> 元件 Key: `ForEachObject`

## 适用场景
需要遍历对象的所有属性（键值对）时使用。常用于处理动态结构的对象数据。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `object`（输入，必填） | 要遍历的对象，表达式对象 | **固定**：用 `paramTypes:"localVariable"` 引用已有对象 | 固定结构，取自变量 |
| `key`（输出） | 当前键名变量名 | **灵活**：变量名自己起；值为表达式对象，`dataType:"string"` | 自定义 |
| `value`（输出） | 当前键值变量名 | **灵活**：变量名自己起；值为表达式对象 | 自定义 |

> `key`/`value` 在循环体内是局部变量，引用用 `paramTypes:"localVariable"`。块级元件，需用 `addNode(LoopEnd)` 显式关闭。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| target | object | 是 | 要遍历的对象 |

### 输出参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| key | string | 否 | 当前键名变量 |
| value | object | 否 | 当前键值变量 |

## 使用示例

```
FOR_EACH_OBJECT (key, value IN formData) {
  消息提示(内容=key + "=" + value)
}
```

## 注意事项
- **需 `addNode(LoopEnd)` 显式关闭**（不再自动生成结束标记）
- 循环体内可通过 key 获取当前属性名，通过 value 获取当前属性值
- 删除循环时会级联删除内部所有子节点
