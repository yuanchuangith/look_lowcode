> 来源：schema-tools/components/ProcessAuditMatrix/knowledge.md（同步于 2026-08-25）

# 审核矩阵

> 组件 Key: `ProcessAuditMatrix`

## 适用场景
在表单中以表格形式展示流程审核信息。适合需要查看多维度审核数据、审核意见汇总的场景。

## 属性
> 公共属性（label、name、display）由系统自动注入。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| panelTitle | string | `''` | 面板标题 |
| massageAlertSwitch | boolean | `false` | 消息提醒开关 |

## 放置规则
- GridColumn
- GxpCard（直接放置）
- FormTab.TabPane

## 注意事项
- 审核矩阵数据由流程引擎提供
- 使用 Container 装饰器（非 FormItem）
