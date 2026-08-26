> 来源：action-design-tools/nodes/Page/AfterSubmitBackend/knowledge.md（同步于 2026-08-25）

# 提交后-后端

> 元件 Key: `AfterSubmitBackend`

## 适用场景
在表单数据提交到后端后执行后续服务端逻辑，例如触发审批流程、同步外部系统、记录操作日志等。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `actionName`（输入，必填） | 动作名称字面量 | **固定**：从 `getActionList` 取已存在的动作 | 固定值，取自工具 |

> 声明性钩子节点：绑定一个动作在表单提交后端处理后执行。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| actionName | string | 是 | 动作名称 |

## 使用示例
```
提交后-后端(动作="提交审批")
```

## 运行时注意

⚠️ **回调中修改 formData 无效**（实测）：后端回调收到 formData 时提交已完成、数据已落库，`formData["flow_status"] = "completed"` 之类的赋值不会生效——`flow_status` 由流程引擎（flows）维护。要修改随表单提交的数据，应在「提交前-后端」（BeforeSubmitBackend，与保存同事务）中完成。分析快照代码时，此回调里的 formData 赋值可判定为无效逻辑。
