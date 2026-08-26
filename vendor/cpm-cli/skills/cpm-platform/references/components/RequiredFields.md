> 来源：schema-tools/components/RequiredFields/knowledge.md（同步于 2026-08-25）

# RequiredFields（必填校验）

## 说明

必填字段校验节点，每个表单页面的第一个子节点。表单提交时自动校验页面内所有必填字段。

## 使用方式

- 作为 `schema.properties` 下的第一个子节点
- parentRef 传 `"root"`
- 无需 x-decorator

## 放置规则

- root（页面根节点，第一个子节点）

## 注意事项

- 每个页面只需一个 RequiredFields
- 不需要任何属性，传空 props 即可
- 创建新页面时必须包含此节点
