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

检索同时检查 `search_complete/scan_complete`、`stop_reason(s)`、`scanned_count`、`truncated_file_count` 和 `read_failure_count`。达到结果/文件上限、文件正文截断或读取失败时，即使 `ok=true,count=0` 也不能证明当前快照没有匹配项。按 `next_step` 缩窄资源类型与查询，或精确检查返回页面；不要自行构造未经快照绑定的续读偏移。`search_complete=true` 仅描述已选择的本地快照范围，不能证明当前平台不存在。

## 刷新选择

- 快照工具默认 `refresh_if_stale=true`。90 分钟内已有成功检查时直接读取；过期后下次查询同步等待刷新完成，不在后台定时刷新。
- 精确页面检查使用单页刷新。首次初始化、旧基线缺少 `page-meta.json`、全局搜索或基线损坏使用全量刷新。
- 表单清单与结构按每次获取的当前开发版本 `dataVersionId` 拉取，页面请求明确使用 `isOfficialPreview=false`；已保存但未发布的修改可拉取，设计器里尚未保存的修改不可拉取。页面元数据 `designSource` 标明草稿及版本号；旧快照来源未标记时不能称为草稿。
- 用户说“重新拉取／刷新”或“保存草稿后再看看”时调用 `refresh_cpm_snapshot(page_identifier=...)`，默认 `force=true`，跳过90分钟缓存。只有明确允许复用缓存时才传 `force=false`。刷新只写 `%LOCALAPPDATA%` 下本地快照。
- 初次从旧来源快照切换时，单页更新会要求全量基线；包装层自动重试全量。全量拉取失败保留的旧页仍使用原来源标记，不得当作本次已验证草稿。
- 刷新失败或 300 秒超时时保留旧快照。响应中的 `failures`、`refreshed_at`、`refresh_mode` 和 `cli_version` 必须进入证据说明。
- 查询刷新失败且旧快照结构可用时，直接返回 `stale=true`、`stale_reason`、`evidence_scope=snapshot_candidates_only` 与缺口说明；没有可用旧快照仍报错。零命中不能证明当前平台不存在。额外补查按 [有限补查](diagnostic-fallback.md) 执行，不能把默认刷新超时当作30秒补查预算。
- CPM、Schema、源码索引刷新相互独立；调用源码工具不会自动刷新 CPM 或 Schema，也不会执行开发库全量关系验证。CPM 刷新只改本地文件，不修改平台设计、发布状态或业务数据。

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

输出单列 `CPM快照` 层，写清刷新时间、模式与页面 `designSource`。开发修改核对使用草稿；运行问题使用目标时点的 Look 发布证据。草稿快照与发布不同不自动视为异常，应报告未发布差异；数据库不可用时只能写“快照候选，当前发布未确认”。
