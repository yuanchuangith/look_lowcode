# CPM 快照路由与证据边界

## 何时先查 CPM

| 问题 | 首选工具 | 后续权威复核 |
| --- | --- | --- |
| 页面结构、显示名称、Route、菜单入口 | `search_platform_snapshot` / `inspect_page_snapshot` | `search_pages` 与 `list_page_actions` |
| 组件类型、绑定、事件订阅 | `inspect_page_snapshot` | 目标动作的发布设计与画布节点 |
| 模型影响面、数据集、字典、事件 | `search_platform_snapshot` | 相关动作参数；需要时再查业务记录 |
| 审批流程、接口定义、公共动作候选 | `search_platform_snapshot` | 精确 action code/RefId、当前发布或后端源码锚点 |
| 组件或编排元件参数含义 | `get_cpm_knowledge` | 当前页面/动作实际参数 |

`search_platform_snapshot.resource_types` 只选问题涉及的资源类型，结果保持有界。已知 Route、Id 或 OutId 时直接用 `inspect_page_snapshot`，不要先做全局模糊扫描。

## 刷新选择

- 快照工具默认 `refresh_if_stale=true`。30 分钟内已有成功检查时直接读取；过期后同步等待刷新完成。
- 精确页面检查使用单页刷新。首次初始化、旧基线缺少 `page-meta.json`、全局搜索或基线损坏使用全量刷新。
- 需要明确重新检查平台时调用 `refresh_cpm_snapshot(force=true, ...)`。刷新只写 `%LOCALAPPDATA%` 下本地快照。
- 刷新失败或 300 秒超时时保留旧快照。响应中的 `failures`、`refreshed_at`、`refresh_mode` 和 `cli_version` 必须进入证据说明。

## 知识主题按需读取

- 主技能：`get_cpm_knowledge(kind="skill", name="main")`
- 组件：`get_cpm_knowledge(kind="component", name="<组件名>")`
- 编排元件：`get_cpm_knowledge(kind="element", name="<分类>/<元件名>")`
- 平台专题：`get_cpm_knowledge(kind="reference", name="flows|interfaces|menus|languages|data-resources")`

不要读取任意路径，也不要一次加载全部组件或元件文档。组件文件在快照中的路径是 `skills/cpm-platform/references/components/<组件名>.md`。

## 证据优先级

1. Look 当前发布副本、精确画布节点和当前只读业务记录。
2. 异常时间对应的历史发布副本与生成 C#。
3. CPM 快照中的页面、菜单、组件、模型、流程和接口候选。
4. 静态前端/后端源码和页面运行证据，各自按主技能门禁使用。

输出单列 `CPM快照` 层，写清刷新时间和模式。快照与数据库不一致时，以目标时点的 Look 发布证据为准，并报告差异；数据库不可用时只能写“快照候选，当前发布未确认”。
