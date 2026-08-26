> 来源：action-design-tools/nodes/Message/OpenConfirmDialog/knowledge.md（同步于 2026-08-25）

# 确认提示框

> 元件 Key: `OpenConfirmDialog`

## 适用场景
执行不可逆操作（删除/提交/审批）前，弹出确认对话框让用户明确确认或取消。返回布尔值表示用户选择，常配合 IfCondition 判断是否继续。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `title`（输入，可选） | 对话框标题，**表达式对象** | **灵活**：字符串文本，用 `paramTypes:"custom"`，`value`/`code`/`label` 填标题文本（如 `"删除"`） | 灵活 |
| `confirmMessage`（输入，必填） | 确认消息内容，**表达式对象** | **灵活**：同 title，填提示文本（如 `"确认要删除吗？"`） | 灵活 |
| `isConfirmed`（输出） | 用户是否确认的变量名。键名固定 `isConfirmed` | **灵活**：变量名自己起（默认 `isConfirmed`）；值为表达式对象 `paramTypes:"custom"`，`dataType:"boolean"`。true=确认、false=取消 | 自定义 |

> `isConfirmed` 产出局部变量，下游引用用 `paramTypes:"localVariable"`。

### 真实数据样本
```json
{
  "elementKey": "OpenConfirmDialog",
  "params": {
    "inputs": {
      "title": { "paramTypes": "custom", "value": "\"删除\"", "code": "\"删除\"", "label": "\"删除\"", "dataType": "" },
      "confirmMessage": { "paramTypes": "custom", "value": "\"确认要删除吗？\"", "code": "\"确认要删除吗？\"", "label": "\"确认要删除吗？\"", "dataType": "" }
    },
    "outputs": {
      "isConfirmed": { "paramTypes": "custom", "value": "isConfirmed", "code": "isConfirmed", "label": "isConfirmed", "dataType": "boolean" }
    }
  }
}
```

## 使用示例
```
用户："删除前确认一下"
→ addNode(OpenConfirmDialog, title="删除", confirmMessage="确认要删除吗？", isConfirmed="isConfirmed")
→ addNode(IfCondition, 条件=isConfirmed==true)
→ [IF 块内] 删除数据...
```
伪代码：
```
isConfirmed = 确认提示框(标题="删除", 内容="确认要删除吗？")
IF (isConfirmed == true) {
  删除数据(...)
}
```

## 注意事项
- `title`/`confirmMessage` 是**表达式对象**（`paramTypes:"custom"`），不是裸字符串
- `isConfirmed` 是局部变量，配合 IfCondition 判断；true=确认、false=取消
- 与 `OpenMessageDialog` 区别：消息提示只是单向告知（无返回值）；确认框需要用户交互选择（返回布尔值）
