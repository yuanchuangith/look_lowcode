> 来源：action-design-tools/nodes/Components/DetailDataFilter/knowledge.md（同步于 2026-08-25）

# 明细数据过滤

> 元件 Key: `DetailDataFilter`

## 适用场景
给明细（从表/子表）组件的数据源新增过滤条件。结构与 `DataFilter` 一致，区别在于针对的是明细/子表组件。常用于主从表联动——主表选中行后给从表叠加过滤条件。

> ⚠️ 本元件无真实样本，下列结构按 DataFilter 形态对齐，待取到样本后核实。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `name`（输入，必填） | 目标明细组件引用 `{label, value, modelkey}` | **固定**：从 `getPageComponents` 取明细/子表组件 ref；`modelkey` 平台派生 | 固定结构，取自工具 |
| `whereConditions`（输入，必填） | 过滤条件树 `{Logic, Filters:[{Field,Operator,ParamInput}]}` | **半固定**：结构同 DataFilter；Field 是数据库字段名，从 getModelDetail 取 | 结构固定，Field 取自工具 |

> 无输出参数。给明细组件数据源叠加过滤条件。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| name | object | 是 | true | 目标明细组件引用 `{label, value, modelkey}`。从 getPageComponents 取 |
| whereConditions | object | 是 | false（结构对象） | 过滤条件树（见下） |

#### whereConditions 条件树
`{Logic, Filters}` 结构，支持递归嵌套（Filters 项可为子组）：
```jsonc
{
  "Logic": "And",
  "Filters": [
    { "Field": "表.字段", "Operator": "Equal", "ParamInput": { "paramTypes": "custom", "code": "...", "label": "...", "dataType": "string" } }
  ]
}
```

### 输出参数
无。

## 使用示例
```
result = 明细数据过滤(数据源=子表明细, 配置="masterId=局部变量-selectedId")
```

## 注意事项
- `name` 是组件引用（表达式对象），从 getPageComponents 取。
- Field 是数据库字段名（`表.列`）；Operator 用 PascalCase 枚举。
- **平台自动生成、模型不要手写**：每条 Filter 的 `Id`、`whereConditions.Id`、`type`、`value`（代码形态）、`modelkey`。
