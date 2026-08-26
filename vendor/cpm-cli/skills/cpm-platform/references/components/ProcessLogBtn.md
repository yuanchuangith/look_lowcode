> 来源：schema-tools/components/ProcessLogBtn/knowledge.md（同步于 2026-08-25）

# 流程日志

> 组件 Key: `ProcessLogBtn`

## 适用场景
在表单中嵌入流程日志查看按钮的字段组件。点击后弹窗展示该流程实例的审批记录和操作历史。以 BPMN 流程图 + 日志列表的双栏形式展示。

## 属性
> 公共属性（label、name、display、pattern）由系统自动注入。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| processQueryData | object | `{ instanceId: '', processId: '' }` | 流程查询参数，含 instanceId 和 processId |
| type | string | 'primary' | 按钮类型（仅设计态使用） |
| text | string | 'button' | 按钮文本（仅设计态使用） |
| minWidth | number | 100 | 最小宽度 |
| maxWidth | string | '' | 最大宽度 |
| prefixCls | string | - | 组件样式名前缀 |
| className | string | - | 扩展样式名 |

## 放置规则
- GridColumn
- GxpCard（直接放置）
- FormTab.TabPane

## 注意事项
- ProcessLogBtn 是 void 动作组件，装饰器为 Container（非数据字段的 FormItem），节点不带 title / x-validator
- 流程日志数据由流程引擎提供，组件本身不存储数据
- 通常与 ProcessButton 配合使用
- processQueryData 为空时，组件自动从页面数据和路由参数中获取 instanceId 和 processId
