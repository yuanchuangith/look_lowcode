> 来源：action-design-tools/nodes/Components/ComponentStatus/knowledge.md（同步于 2026-08-25）

# 设置组件状态

> 元件 Key: `ComponentStatus`（编排数据里可能写作 `SetComponentStatus`，二者等价）

## 适用场景
**批量**设置一个或多个组件的显示状态：显示/隐藏/只读/必填等。常用于表单联动（如选择某类型后隐藏部分字段、设为必填等）。一个节点可同时改多个组件。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `params`（输入，必填） | 状态设置项数组 `[{id, name, status}]` | **半固定**：`name` 是组件引用表达式对象(从 `getPageComponents` 取 ref 粘贴，`paramTypes:"componentsVariable"`)；`status` 是固定枚举(见下表)；`id` 平台自动填，**不要手写** | 结构固定，name 取自工具 |

> 无输出参数。`name` 必须用 `paramTypes:"componentsVariable"`（从 getPageComponents 取现成 ref），不能用 custom 拼。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| params | array | 是 | false（结构数组） | 状态设置项列表，每项 `{name, status}` |

#### params[] 每项结构
```jsonc
{
  "id": "<平台生成>",
  "name": {                       // 目标组件引用（表达式对象）
    "paramTypes": "componentsVariable",
    "value": "componentsVariable-FileName",
    "dataType": "EformInput",
    "label": "页面组件-文件名称",
    "code": "inbiz('FileName')"
  },
  "status": "hide"                // 见下表
}
```

### status 取值

| 值 | 含义 |
|----|------|
| `hide` | 隐藏 |
| `show` | 显示 |
| `readonly` | 只读 |
| `required` | 必填 |
| `display-visible\|required-true` | 显示且必填（组合） |
| `display-visible\|readOnly-false` | 显示且可编辑（组合） |
| `display-visible\|readOnly-true` | 显示且只读（组合） |

> 单值（hide/show/readonly/required）最常见；需要同时控制显隐+必填/只读时用组合写法。

### 输出参数
无。

## 参数示例
```json
{
  "elementKey": "ComponentStatus",
  "params": {
    "inputs": {
      "params": [
        { "name": { "paramTypes": "componentsVariable", "value": "componentsVariable-FileName", "code": "inbiz('FileName')", "label": "页面组件-文件名称", "dataType": "EformInput" }, "status": "required" },
        { "name": { "paramTypes": "componentsVariable", "value": "componentsVariable-AppendixBlock", "code": "inbiz('AppendixBlock')", "label": "页面组件-附录文件", "dataType": "GxpCard" }, "status": "hide" }
      ]
    }
  }
}
```

## 使用示例
```
设置组件状态(页面组件-文件名称=required, 页面组件-附录文件=hide)
```

## 注意事项
- `params` 是**数组**，一个节点批量设置多个组件，每项一个 `name` + `status`。
- `name` 是组件引用表达式对象（从 getPageComponents 取），不是字符串。
- **平台自动生成、模型不要手写**：每项的 `id`、`name.value` 内部 id。
