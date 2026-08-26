> 来源：action-design-tools/nodes/Components/ComponentEvent/knowledge.md（同步于 2026-08-25）

# 绑定事件

> 元件 Key: `ComponentEvent`

## 适用场景
为组件的某个事件**绑定**要执行的动作：当组件触发该事件（如按钮点击前 `onChildrenCustomBeforeClick`）时，执行指定动作。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `name`（输入，必填） | 目标组件引用，表达式对象 | **固定**：从 `getPageComponents` 取组件 ref 粘贴，`paramTypes:"componentsVariable"` | 固定结构，取自工具 |
| `eventName`（输入，必填） | 事件名，字符串字面量 | **固定**：从 `getComponentInfo` 查目标组件的 `events` 数组取真实事件名（如 `Click`、`onSelectedRowsChange`、`onBeforeDelete`）。**别凭常见命名猜**（onClick/onChange 等） | 固定值，取自工具 |
| `action`（输入，必填） | 事件触发时执行的动作引用 `{value, label, actionType, isActionSelect}` | **固定**：`value`/`label` 从 `getActionList` 取已存在动作；`actionType`/`isActionSelect` 平台自动填，**不要手写** | 固定结构，取自工具 |

> 无输出参数。本元件是**声明性绑定**（组件事件 → 动作），通常放在页面初始化动作里。

## 参数示例
```json
{
  "elementKey": "ComponentEvent",
  "params": {
    "inputs": {
      "name": { "paramTypes": "componentsVariable", "value": "componentsVariable-GxpSmartTables_xxx", "code": "inbiz('GxpSmartTables_xxx')", "label": "页面组件-GxpSmartTables_xxx", "dataType": "GxpSmartTables" },
      "eventName": "onChildrenCustomBeforeClick",
      "action": { "value": "<动作id>", "label": "回收子窗体自定义按钮点击前事件", "actionType": "js", "isActionSelect": true }
    }
  }
}
```

## 使用示例
```
绑定事件(组件="页面组件-GxpSmartTables_xxx", 事件="onChildrenCustomBeforeClick", 动作="回收子窗体自定义按钮点击前事件")
```

## 注意事项
- `name` 是组件引用表达式对象（不是字符串）；从 getPageComponents 取。
- `eventName` 是组件支持的事件名（字符串）。
- `action` 引用一个已存在动作，从 getActionList 取 value/label。
- **平台自动生成、模型不要手写**：`action.actionType`、`action.isActionSelect`、动作/组件的 GUID id。
