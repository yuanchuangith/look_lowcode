> 来源：schema-tools/components/GxpProcessCenter/knowledge.md（同步于 2026-08-25）

# 流程中心

> 组件 Key: `GxpProcessCenter`

## 适用场景

流程中心门户组件，按流程组（如"档案管理"）集中展示该组下的待办、草稿、已申请、已办、归档等分类入口。通常作为独立页面或流程主页的主体。

移动端以宫格形式展示 5 个分类入口（待办/草稿/已申请/已办/归档），模板由工具自动注入，通常无需配置。

## 属性

> 工具自动注入移动端宫格模板（mobiledynamicdata），模型只需提供流程组名称。

| 名称 | 类型 | 默认值 | 何时设置 |
|------|------|--------|----------|
| processGroupName | `string` | `''` | **核心参数**：显示哪个流程组（如 `档案管理`） |
| showTabTitle | `boolean` | `false` | 需要显示 Tab 标题栏时设 `true` |
| openMode | `'currentPage' \| 'popUp' \| 'newPage'` | `'currentPage'` | 流程详情的打开方式 |
| allGroup | `string` | `'all'` | 是否显示全部流程组，`'all'` 为全部 |

## 放置规则

- 页面根节点（直接放置）
- GxpCard（直接放置）

## 注意事项

- `processGroupName` 是唯一需要模型决定的核心参数，决定展示哪个流程组的待办/已办等。
- 移动端宫格配置（mobiledynamicdata）是平台固定模板，工具自动注入，模型通常无需配置。
- 该组件是流程门户，不是数据选择器；数据选择用 EformDynamicList 或 RelatedProcess。
