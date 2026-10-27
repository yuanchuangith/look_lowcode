---
name: gxp-lowcode-debug
description: Use this skill when the user asks to 排查或复核 GXP 低代码、开发库表结构或可信关系、周期培训、公共动作、表单动作、动作名称或编号定位、流程页面反查、试卷下拉、值被清空、无可选值、文件对应试卷、岗位矩阵申请或修订、岗位培训申请、DataFilter、组件实现、请求参数、API、Controller、Service、后端异常栈、草稿保存、发布同步、动态 C# 异常、字段映射或画布节点，或明确要求查看、更改 Look/Write 数据库连接设置。通过 gxp-lowcode-readonly MCP 输出精确位置、问题证据及有依据的根因和修复建议，留下可复用的诊断材料；编辑端按需使用并自主补证，不要求先完成交接。
---

# GXP Low-Code Debug

通过 `gxp-lowcode-readonly` MCP 从真实 ActionDesign、只读业务证据和本地 metadata-only 源码索引定位问题。先定位节点，再精读相关字段，最后查看差异与证据摘要；不自动遍历全部分页或回传整份配置。

## 环境与安全边界

- 当前配置及其查询结果默认属于开发环境；只有用户明确说明当前连接的环境时才覆盖。“排查生产问题”不表示本机已连接生产库，不能用开发库数据确认生产结论。需要生产证据时，按 [platform-map.md 的生产批量取证规则](references/platform-map.md#生产环境数据按批取证) 给齐当前阶段的只读 SQL。
- 普通诊断不读取或输出连接配置；任何模式都不询问、读取、输出或转述数据库密码。不调用 `mysql.exe`，不拼接连接参数。用户明确要求查看或更改连接时，才按 [database-settings.md](references/database-settings.md) 使用本机 `database_settings`；密码由用户在 `open` 窗口隐藏输入。
- 数据库查询只允许 `SELECT`、`SHOW`、`DESCRIBE`、`EXPLAIN`。优先结构化工具，`readonly_sql` 仅用于结构化工具无法表达的窄查询并说明原因。
- 只读阶段不修改业务数据、表结构、动作 JSON、草稿、发布状态或历史记录。编辑仅按下述授权门禁进行，不用 SQL、CLI 或页面绕过。

## 规则与会话锚点

开始工具检查前锁定三项；未完整确认时只报告当前配置，不判正确或错误：

```text
当前现象：用户实际看到什么或本轮希望复核什么
期望规则：当前目标、范围、允许选择/生成/去重行为
无匹配时行为：留空 / 正常带出 / 跳过 / 报错 / 尚未确认
```

“现在可以选择全部”可能是现象也可能是期望，不自行判断极性。复用已确认的动作、RefId、页面、分组、组件及节点，不因用户只纠正规则而重扫无关证据。多轮纠正、排除项、实现选择或“改了再看看”时读取 [conversation-contract.md](references/conversation-contract.md)，向 `diagnose_codex_input` 传当前会话 `context`；不持久化会话、不硬编码业务字段和不变量。

## 精确排查流程

1. 锁定现象后，先按下节检索本地关系图历史线索；工具不可用时继续只读排查。页面全貌、菜单、组件绑定、模型、审批流程或接口问题，按 [cpm-snapshot-routing.md](references/cpm-snapshot-routing.md) 先查 CPM 快照：已知页面用 `inspect_page_snapshot`，知识只按需用 `get_cpm_knowledge` 读取一个合法主题。快照只能形成候选，不能覆盖当前发布副本。
2. 将用户原始输入完整传给 `diagnose_codex_input`。有 code/RefId 用 `resolve_action`；只有页面名称用 `search_pages` → 确认 Route/Id/OutId → `list_page_actions`；只有业务名称用 `search_actions`。多候选按类型、code、RefId、页面和名称消歧，不默认第一个。
3. 用 `get_design_versions` 读取当前草稿与发布；只有历史异常才 `include_history=true`。动作身份、画布坐标、版本与异常时点规则见 [platform-map.md](references/platform-map.md)。草稿与发布是同一动作的两个副本；只有发布更新运行配置，“已同步”只表示 `data/csharp_code` 一致，不表示逻辑或运行正确。
4. `inspect_action` 第一阶段保持 `include_params=false`、`include_generated_csharp=false`，只读定位和 `facts`；已知字段用 `focus_fields`，区分定义、读取、条件、循环和传参，零命中不证明未使用。明确分组、节点或不超过 10 个节点后才精读参数，以完整 `paramsValue` 为准。只有精确异常 C# 行或节点事实不足时才显式读生成代码，`terms` 不构成授权。
5. 按下表读取命中的参考；沿 `CallPublicAction`、`CallAction` 追到数据库读写、显式返回或首个异常点。需字段传递链时可 `inspect_control_flow(follow_calls=true)`（默认深度 2、最多 8 动作），保留 `call_flow.unresolved`、绑定和版本边界，静态边不等于实际执行或外键。
6. 业务表先 `describe_table`，再 `get_records` 使用索引等值条件、小列集和小 limit。完成结论前读取 [report-contract.md](references/report-contract.md)：结论、完整可见位置、原因、可执行修复及依据、验证边界；不写“同上”，不把静态检查称为运行通过。
7. 只在命中源码或页面升级门禁时补充对应证据；否则说明“低代码证据已足够，无需查源码”。最终确认后按图谱规则留证；导出编辑交接和启动 Write 都不是排查结束的必选步骤。

## 按问题读取参考

| 触发条件 | 必读内容 |
| --- | --- |
| 下拉、`DataFilter`、无可选值、值被清空、过滤被覆盖 | [component-filter-audit.md](references/component-filter-audit.md)：汇总同组件全部相关写入点和父条件，不能凭一个初始化节点下结论 |
| 点击、选择、留空、批量编辑，或修改后仍复现 | [branch-verification.md](references/branch-verification.md)：证明本次交互命中分支和最终写库；无法证明时不给操作性修改方案 |
| 表、字段、备注、索引、约束、跨表关系 | [schema-relations.md](references/schema-relations.md)：开发库 Schema、可信关系、实时验证和本机否决 |
| 摘要、省略、截断、分页、长参数或异常候选 | [diagnostic-output.md](references/diagnostic-output.md)：预算、完整性、记录与顶层元数据续读；`has_more=false` 不单独证明完整，按需补证 |
| 保存、发布复核或动态异常 | [platform-map.md](references/platform-map.md) 的复核顺序与 [report-contract.md](references/report-contract.md) 的输出格式 |
| 已命中组件、API、Controller、Service、后端栈等 `source_hints` 且低代码不足 | [source-code-evidence.md](references/source-code-evidence.md)：按锚点选择前端／后端、本地有界索引与证据新鲜度；不扩大仓库搜索 |
| 静态证据无法解释运行症状，或只在具体页面交互发生 | [runtime-browser-evidence.md](references/runtime-browser-evidence.md)：用户开启页签、六位码授权精确 Origin 后只读取证；不启动新浏览器或使用 9222 |
| 纯 UI 样式、渲染或组件交互实现问题 | 转交可用的 `gxp-component-debug`，不以低代码修复代替组件实现排查 |
| 需保留诊断或编辑端读取已有材料 | [edit-handoff.md](references/edit-handoff.md)：可选本机记录、来源校验和按需补证；无 `handoff_ref` 也能正常排查或独立核对编辑 |

## 嵌套控制流证据门禁

- 两层及以上嵌套，或涉及 `Else`、`ElseIf`、`IfEnd`、循环结束、`Catch`、`Finally` 归属时，必须在当前运行副本调用 `inspect_control_flow`；详细步骤读 [branch-verification.md](references/branch-verification.md)，不得用相邻节点或平铺路径猜配对。
- 回答展示简短 `views.tree_text`，明确 `root_block`、`matched_branch`、`matched_end`。`structure_status != valid` 时只能写“结构候选/待确认”，不得据此判定逻辑 Bug、不可达或给画布修改位置。
- 分支 Bug 必须同时有当前发布、有效结构、用户明确规则，以及覆盖每个业务分支与空值边界的最小 `scenario_matrix`；只有期望路径与三态静态实际路径不一致才判定。`unknown`、表达式、函数和 SQL 均不得补成真实运行结果。

## 本地业务关系图路由

- 开始用 `search_business_logic_graph` 检索案例，已知实体／关键词用 `get_business_graph`；历史仅是线索，当前发布副本始终是本次运行配置的权威。取得 RefId→当前设计 ID 后用 `current_published_designs` 复查，环境不随问题文字重标。
- 最终确认后自动 `upsert_business_logic_graph`，只保存已确认关系；用户确认错误或已确认版本／证据变化才 `invalidate_business_logic_graph`，普通质疑、工具失败不撤销。写入或分析前读取 [business-logic-graph.md](references/business-logic-graph.md)，含稳定身份、完整证据集合、融合分析与有界补查。
- 更新已有案例必须精确读取完整 `case_snapshot`，检查 `complete/replacement_safe`，保留有效事实后带 `expected_case_snapshot` 提交；不要用图邻域或截断结果拼完整案例。缺身份保留待消歧，历史归档不整体重新提交。
- 图只留 metadata-only 定位、结构、抽象结论和证据指纹，禁止凭据、业务记录值、完整参数、SQL／源码正文、完整生成 C#。截断或工作预算耗尽不证明不存在路径、案例或孤岛；只声明已知 scope 覆盖。
- 缓存损坏、锁超时、迁移失败或工具缺失时继续正常只读排查，不双写旧 JSON，不把缓存错误当业务 Bug，不因此调用编辑端或写业务库。每次请求共享 UUID `request_id`；目录补查最多 3 次、1 跳、30 秒，不读业务行、不全量刷新。

## 只读到编辑的显式授权门禁

- 默认先给具体修改与验证方案：目标动作、分组、节点、当前值、拟改值、影响范围，以及仅保存草稿、不发布的边界。
- 输出修改方案不构成编辑授权。用户确认具体修改方案前，不得调用任何 `gxp-lowcode-editor` MCP 工具，也不得创建编辑会话、审批事务或写草稿。
- 用户明确确认已展示的具体修改方案后，该方案的修改范围已获授权；当前 `gxp-lowcode-edit` 要求首次显式调用，尚未启用时不提前调用编辑工具。已启用的同一对话无需重复调用技能或确认同一方案，也不要求先导出 `handoff_ref`。仅确认原因、要求解决方法或含义不清的“继续”不是编辑授权。
- 同一方案在本对话已获授权后，不重复索要确认；目标、内容或影响范围实质变化时，先展示更新方案并确认。
- 授权且显式启用后，先读编辑技能和工具约束；每对话只注册一个 `conversation_id` 并复用。核对当前草稿、版本和节点，证据足够则复用、不足则补查；按工具完成编译与审批，不得绕过工具门禁。
- 只保存授权的现有未发布草稿，不发布、不改业务数据。保存后只读复核实际变化与同步状态，明确草稿不影响运行；编辑工具不可用时说明无法实施，不另找写入路径。

## 工具失败与兼容读取

记录一次准确错误，不重复同一失败路径；优先其他结构化工具，不能表达时才按 [platform-map.md](references/platform-map.md) 使用受控 `readonly_sql`。工具故障不是业务 Bug。

MCP 不可用时仅用插件兼容 CLI（与 MCP 共用只读核心和 SQL 防护）：

```powershell
& "$env:LOCALAPPDATA\GxpLowcodeReadonly\.venv\Scripts\python.exe" `
  "<插件目录>\scripts\codex_input.py" --text -
```

动作兼容检查为 `scripts/inspect_action.py`；不回退到 `mysql.exe`。
