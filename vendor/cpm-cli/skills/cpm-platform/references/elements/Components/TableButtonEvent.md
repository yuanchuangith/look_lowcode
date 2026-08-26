> 来源：action-design-tools/nodes/Components/TableButtonEvent/knowledge.md（同步于 2026-08-25）

# 表格按钮事件绑定

> 元件 Key: `TableButtonEvent`

## 适用场景
为表格/列表组件的**自定义按钮**绑定点击时执行的动作。一个节点可同时为多个按钮绑定动作（每个按钮→一个动作）。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `conf`（输入，必填） | 绑定配置 `{component, componentName, events}` | **半固定**：见下方子结构 | 结构固定 |
| `conf.component`/`componentName` | 目标表格组件标识/中文名 | **固定**：从 `getPageComponents` 取（组件的 `buttons` 字段含全部按钮 id/title/type） | 固定，取自工具 |
| `conf.events[]` | 按钮→动作绑定数组，每项 `{id, button, action}` | **半固定**：`button.value` 从组件 buttons 取按钮 id；`action.value`/`label` 从 `getActionList` 取已存在动作；`id` 平台自动填 | 结构固定，button/action 取自工具 |

> 无输出参数。`button`/`action` 的 GUID、`button.label`(常为 i18n 键)、`actionType`/`isActionSelect` 平台自动填，**不要手写**。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| conf | object | 是 | false（结构对象） | 绑定配置（见下） |

#### conf 结构
```jsonc
{
  "component": "appendixList",        // 组件标识
  "componentName": "附录文件",         // 组件中文名
  "events": [                          // 按钮→动作绑定列表（可多条）
    {
      "id": "<平台生成>",
      "button": { "label": "<i18n键>", "value": "<按钮id>" },
      "action": { "value": "<动作id>", "label": "附录列表点击事件", "actionType": "js", "isActionSelect": true }
    }
  ]
}
```

### 输出参数
无。

## 参数示例
```json
{
  "elementKey": "TableButtonEvent",
  "params": {
    "inputs": {
      "conf": {
        "component": "appendixList",
        "componentName": "附录文件",
        "events": [
          {
            "button": { "label": "新增", "value": "<按钮id>" },
            "action": { "value": "<动作id>", "label": "附录列表点击事件", "actionType": "js", "isActionSelect": true }
          }
        ]
      }
    }
  }
}
```

## 使用示例
```
表格按钮事件绑定(列表="附录文件", 按钮=[新增→附录列表点击事件])
```

## 注意事项
- `events[]` 是数组，一个节点可绑定多个按钮，每个按钮对应一个动作。
- `action` 引用一个已存在的动作（从 getActionList 取 value/label）；`button` 引用组件内的按钮。
- **平台自动生成、模型不要手写**：`events[].id`、`button.label`（常为 `{multilingual}` i18n 键）、`button.value`/`action.value`（GUID）、`actionType`/`isActionSelect`。
