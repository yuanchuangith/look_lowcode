> 来源：action-design-tools/nodes/Loop/ForEachArray/knowledge.md（同步于 2026-08-25）

# ForEach 列表循环

> 元件 Key: `ForEachArray`

## 适用场景
需要遍历数组/列表中的每个元素时使用。块级元件，需用 `addNode(LoopEnd)` 显式关闭。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `list`（输入，必填） | 要遍历的数组，引用对象 | **固定**：必须是已有数组。上游局部变量用 `paramTypes:"localVariable"`（`value:"localVariable-{数组名}"`）；全局数组用 `paramTypes:"globalVariable"`。**不要用 custom 自己拼数组名** | 固定结构，取自变量源 |
| `item`（输出） | 当前元素的变量名绑定 | **灵活**：变量名自己起（默认 `item`），值为表达式对象 `paramTypes:"custom"`，`value`/`code`/`label` 填变量名。循环体内用 `paramTypes:"localVariable"` 引用 | 自定义 |
| `index`（输出） | 当前索引的变量名绑定 | **灵活**：变量名自己起（默认 `index`），同 item。可省略 | 自定义 |

> `item`/`index` 在循环体内是局部变量，引用用 `paramTypes:"localVariable"`。取元素属性写 `item["name"]`。

## 真实数据样本（遍历上游 items 数组）
```json
{
  "elementKey": "ForEachArray",
  "params": {
    "inputs": {
      "list": { "paramTypes": "localVariable", "value": "localVariable-items", "dataType": "array", "label": "局部变量-items", "code": "items" }
    },
    "outputs": {
      "item": { "paramTypes": "custom", "value": "item", "code": "item", "label": "item", "dataType": "any" },
      "index": { "paramTypes": "custom", "value": "index", "code": "index", "label": "index", "dataType": "number" }
    }
  }
}
```

## 使用示例
```
用户："遍历订单列表，提示每条订单名"
→ 先有数组局部变量 orderList（通常来自 SelectData 的 rows）
→ addNode(ForEachArray, list={localVariable引用orderList}, item="item")
→ 循环体内：消息提示(内容={localVariable引用item, 取属性 item.name})
```
伪代码：
```
FOR (item IN orderList) {
  消息提示(内容=item["name"])
}
```

## 注意事项
- `list` 必须是数组类型的已有变量，用 localVariable/globalVariable 引用，不要用 custom 拼数组名
- 块级元件，**需 `addNode(LoopEnd)` 显式关闭**（不再自动生成）；循环体内容放在 ForEachArray 与 LoopEnd 之间
- 提前退出循环用 `ExitLoop`，跳过本次用 `ContinueLoop`
