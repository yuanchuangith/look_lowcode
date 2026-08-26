> 来源：schema-tools/components/GridColumn/knowledge.md（同步于 2026-08-25）

# 网格列

> 组件 Key: `GridColumn`

## 适用场景
FormGrid 的子组件，用于定义网格中的每一列。每个 GridColumn 内可放置表单字段组件。

## 属性

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| gridSpan | number | 1 | 跨列数（12列栅格，6=半行，12=整行） |

## 放置规则
- 只能作为 FormGrid 的直接子组件使用

## 子组件
可放置所有 field 类型的表单字段组件。

## 注意事项
- GridColumn 必须嵌套在 FormGrid 内部使用，Schema 中 key 为 `GridColumn`
- `gridSpan` 表示该列跨越的网格列数，12 列栅格系统
- 常用值：`gridSpan: 6`（半行，两列布局）、`gridSpan: 12`（整行，用于文件上传、文本域等宽组件）
- 字段排列原则：短字段（姓名、编号）放半行，长字段（备注、附件）放整行
