> 来源：action-design-tools/nodes/Loop/ForEachDynamicArray/knowledge.md（同步于 2026-08-25）

# ForEach 动态列表循环

> 元件 Key: `ForEachDynamicArray`

## 适用场景
需要遍历动态获取的数组/列表中的每个元素时使用。与 ForEachArray 的区别在于数据源为动态数组（如接口返回的列表）。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `list`（输入，必填） | 要遍历的动态数组，表达式对象 | **固定**：用 `paramTypes:"localVariable"` 引用已有数组（如接口返回结果） | 固定结构，取自变量 |
| `item`（输出） | 当前元素变量名 | **灵活**：变量名自己起；值为表达式对象 `paramTypes:"custom"` | 自定义 |

> `item` 在循环体内是局部变量，引用用 `paramTypes:"localVariable"`。块级元件，需用 `addNode(LoopEnd)` 显式关闭。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| list | object | 是 | 要遍历的动态数组 |

### 输出参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| item | object | 否 | 当前元素变量名 |

## 使用示例

```
FOR_EACH_DYNAMIC (item IN dynamicList) {
  消息提示(内容=item.name)
}
```

## 注意事项
- **需 `addNode(LoopEnd)` 显式关闭**（不再自动生成结束标记）
- list 参数支持动态数据源引用
- 删除循环时会级联删除内部所有子节点
