> 来源：schema-tools/components/RelatedProcess/knowledge.md（同步于 2026-08-25）

# 关联流程

> 组件 Key: `RelatedProcess`

## 适用场景

以下拉选择 + 表格弹窗的形式选择流程总表数据，支持单选/多选模式，可配置流程状态过滤、流程分组筛选。选中后可查看流程详情。

## 属性

> 公共属性（label、name、display、pattern、required）由系统自动注入。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| placeholder | `string` | `'请选择'` | 占位提示 |
| selectType | `boolean` | `false` | 是否多选 |
| autoLoading | `boolean` | `true` | 是否自动加载数据 |
| pageSize | `number` | `10` | 每页条数（5-100） |
| incidentStates | `number[]` | `[0, 1, 2]` | 流程状态过滤。`0` 审批中，`1` 审批完成，`2` 已终止 |
| displayFields | `string[]` | `['incidentID', 'processName']` | 表格展示字段 |
| displayValueFields | `string[]` | `['incidentID', 'processName']` | 显示值字段 |
| processGroups | `string[]` | `[]` | 流程分组筛选 |
| dropdownWidth | `number` | `600` | 下拉框宽度（px，300-1200） |
| openMode | `'currentPage' \| 'popUp' \| 'newPage'` | `'popUp'` | 流程详情打开方式 |
| readOnly | `boolean` | `false` | 是否只读 |
| disabled | `boolean` | `false` | 是否禁用 |

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 流程数据通过 `/api/ProcessCenter/processmonitor` 接口获取
- 选中值以 JSON 字符串存储
- 标签可点击查看流程详情
- 只读或禁用模式下组件不可操作
