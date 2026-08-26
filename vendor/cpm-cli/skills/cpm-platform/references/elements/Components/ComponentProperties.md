> 来源：action-design-tools/nodes/Components/ComponentProperties/knowledge.md（同步于 2026-08-25）

# 组件属性

> 元件 Key: `ComponentProperties`

## 适用场景
读取或设置页面组件的属性值（如 display/visible/data 等）。get 读取属性、set 设置属性。常用于动态控制组件显示、取组件内部数据等。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `type`（输入，必填） | 操作类型枚举字面量 | **固定枚举**：`get`(读取) / `set`(设置) | 固定枚举 |
| `name`（输入，必填） | 目标组件引用，**表达式对象** | **固定**：从 `getPageComponents` 取组件 ref 粘贴，`paramTypes:"componentsVariable"` | 固定结构，取自工具 |
| `propertyName`（输入，必填） | 属性名，字符串字面量 | **固定**：组件支持的属性名（如 `display`/`visible`/`data`/`disabled`），从 `getComponentInfo` 查属性清单 | 固定值，取自工具 |
| `propertyValue`（输入，set 时必填） | 属性值，表达式对象 | **灵活**：按值内容填，`paramTypes:"custom"`(字面量) 或引用变量。仅 set 时填 | 灵活 |
| `returnValue`（输出，get 时返回） | 读取到的属性值变量名。键名固定 `returnValue` | **灵活**：变量名自己起；值为表达式对象 `paramTypes:"custom"`。仅 get 时产出 | 自定义 |

> get 操作产出局部变量（`returnValue`），下游引用用 `paramTypes:"localVariable"`。

### 真实数据样本（set：设置组件 display 属性为 visible）
```json
{
  "elementKey": "ComponentProperties",
  "params": {
    "inputs": {
      "type": "set",
      "name": { "paramTypes": "componentsVariable", "value": "componentsVariable-QualityInfoNo", "dataType": "EformInput", "label": "页面组件-质量信息编号", "code": "inbiz('QualityInfoNo')" },
      "propertyName": "display",
      "propertyValue": { "paramTypes": "custom", "value": "'visible'", "code": "'visible'", "label": "'visible'", "dataType": "" }
    }
  }
}
```

## 使用示例
```
用户："获取表格数据存到变量"
→ getPageComponents 找表格组件 ref
→ addNode(ComponentProperties, type="get", name=组件ref, propertyName="data", returnValue="tableData")

用户："隐藏某个组件"
→ addNode(ComponentProperties, type="set", name=组件ref, propertyName="display", propertyValue="'none'")
```

## 注意事项
- `name` 是**组件引用表达式对象**（`paramTypes:"componentsVariable"`，从 getPageComponents 取），不是裸字符串
- `propertyName` 是字符串字面量，从 `getComponentInfo` 查组件支持的属性
- `propertyValue`（set）/`returnValue`（get）是表达式对象
- 与 `ComponentStatus` 区别：ComponentStatus 专门控制显示/隐藏/只读/必填（语义化状态）；ComponentProperties 是通用的属性读写（更底层，可操作任意属性）
