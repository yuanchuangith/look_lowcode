> 来源：schema-tools/components/Tag/knowledge.md（同步于 2026-08-25）

# 标签

> 组件 Key: `Tag`

## 适用场景

将数据以标签形式展示，支持新增、编辑、查看、删除操作。标签支持自定义背景颜色、文本颜色、边框和圆角样式。还支持通过数据字段动态设置颜色。适用于状态标记、分类标签等场景。

## 属性

> 公共属性（label、name、display、pattern、required）由系统自动注入。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| color | `string` | `'#f5f5f5'` | 标签背景颜色 |
| fontColor | `string` | `'#666'` | 标签文本颜色 |
| border | `number` | `1` | 边框宽度（px） |
| radius | `number` | `20` | 圆角大小（px） |
| showField | `string` | | 显示字段，指定标签文本来源 |
| sourceModel | `string` | | 关联的数据模型标识 |
| readOnly | `boolean` | `false` | 只读模式，只读时隐藏所有操作按钮 |
| hidden | `boolean` | `false` | 是否隐藏组件 |
| defaultType | `'Input' \| 'Select'` | `'Input'` | 默认值类型 |
| colorFieldName | `string` | | 颜色字段名，从数据模型中读取颜色 |
| colorField | `string` | | 颜色字段，通过 props 传入 |
| getTagColor | `(item: any, index: number) => string` | | 动态颜色回调函数 |
| operation | `object` | | 操作配置，包含操作类型列表、弹窗尺寸和权限设置 |
| operationType | `'add' \| 'edit' \| 'delete' \| 'read'` | | 操作类型（operation.table 子项） |
| operationName | `string` | | 操作名称（operation.table 子项） |
| link | `string` | | 关联页面，格式为 `页面名称,页面ID`（operation.table 子项） |
| field | `string` | | 关联字段，仅对编辑和查看操作生效（operation.table 子项） |

### operation 结构

| 字段 | 类型 | 描述 |
|------|------|------|
| table | `OperationItem[]` | 操作类型列表 |
| formItems | `object` | 弹窗表单尺寸配置 |
| auth | `string` | 权限标识 |

### OperationItem 结构

| 字段 | 类型 | 描述 |
|------|------|------|
| operationType | `'add' \| 'edit' \| 'delete' \| 'read'` | 操作类型 |
| operationName | `string` | 操作名称 |
| link | `string` | 关联页面 |
| field | `string` | 关联字段 |

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 配置 sourceModel 后自动从数据模型加载标签数据
- 颜色优先级：getTagColor > colorFieldName > colorField > color > 默认主题色
- 只读模式下隐藏所有操作按钮
