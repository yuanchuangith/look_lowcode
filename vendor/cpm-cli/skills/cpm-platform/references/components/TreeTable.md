> 来源：schema-tools/components/TreeTable/knowledge.md（同步于 2026-08-25）

# 树表格

> 组件 Key: `TreeTable`

## 适用场景

以表格形式展示和管理树形结构数据，包含名称列和描述列。支持节点的新增、编辑、删除操作。名称列支持自动完成输入和数据源下拉选择。

## 属性

> 公共属性（label、name、display、pattern、required）由系统自动注入。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| defaultValue | `string` | | 默认值 |
| placeholder | `string` | `'请选择'` | 占位提示 |
| readOnly | `boolean` | `false` | 是否只读模式 |
| autoGetData | `boolean` | `true` | 是否自动获取数据 |
| autoLoading | `boolean` | `true` | 是否自动加载 |
| pageSize | `number` | `999` | 分页大小 |
| disabled | `boolean` | `false` | 是否禁用组件 |
| value | `ITreeTableData` | | 组件的树形数据值，用于受控模式 |
| style | `React.CSSProperties` | | 组件自定义样式 |
| modelkey | `string` | | 数据模型 Key，绑定数据源后自动获取 |
| showconfig | `object` | | 显示配置对象，包含 `nameField` 和 `allList` |
| processInstanceId | `string` | | 关联流程的流程实例号字段 |
| headerButtons | `ITreeTableButton[]` | `[]` | 表头按钮配置数组 |
| enableHyperlinkView | `boolean` | `false` | 是否启用超链接查看 |
| selectWindowHeight | `number` | `50` | 选择窗口高度（%） |

### ITreeTableButton 结构

| 字段 | 类型 | 描述 |
|------|------|------|
| id | `string` | 按钮唯一标识 |
| text | `string` | 按钮显示文本 |
| icon | `string` | 按钮图标类型 |
| eventKey | `string` | 按钮事件标识 |
| buttonType | `'primary' \| 'default' \| 'dashed' \| 'link' \| 'text'` | 按钮样式类型 |
| disabled | `boolean` | 是否禁用 |
| show | `boolean` | 是否显示 |

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 只读模式下隐藏操作列，名称和描述列不可编辑
- 数据源通过 DataCenter 绑定配置
- 名称列支持自动完成输入和数据源下拉选择
