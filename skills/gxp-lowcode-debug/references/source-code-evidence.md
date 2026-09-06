# 命中驱动源码证据

只在 `SKILL.md` 的源码升级门禁成立时读取和执行本流程。低代码配置已经解释问题时立即停止，不读取源码仓库。

## 有界只读仓库

- 前端默认候选：`F:\cpm\gxp2.components`、`G:\hoyi\updateComponents\gxp2.components`
- 后端默认候选：`F:\cpm\gxp2.web`、`G:\hoyi\updateWeb\gxp2.web`

`source_repository_status` 只检查上述候选和 `source-repositories.json` 中显式配置的绝对路径，不向父目录、其他盘符或用户目录扩散。多个副本 commit、remote 或相关 dirty 内容不一致且没有 preferred 时返回 `REPOSITORY_AMBIGUOUS`；无关文档和产物仍可显示在 Git 状态中，但不参与源码索引指纹。源码排查默认不联网、不构建、不修改、不格式化；结构化源码工具读取本地仓库并把 metadata-only 索引写入系统数据目录。

自定义或双副本选择使用 `scripts/configure_source_repositories.ps1|sh`。配置只保存仓库路径和 preferred，不保存源码与凭据。

## source_hints 判定

以下四个 MCP 响应可能返回紧凑 `source_hints`：

- `diagnose_codex_input`
- `inspect_action`
- `inspect_component_filters`
- `trace_dynamic_exception`

字段含义：

- `candidate_layers`：只允许 `frontend`、`backend`；为空时不查源码。
- `reason_codes`：说明组件身份、API、服务符号、真实后端栈或跨层契约等触发原因。
- `anchors`：动作、设计、组件、Route 或服务等逻辑身份；未知字段会省略。
- `exact_terms`：最多 8 个精确源码词。
- `paired_terms`：最多 4 组必须在同一文件共同命中的组合词。
- `confidence`：只描述锚点质量，不代表根因已经确认。
- `hint_version`：当前提示契约版本；高置信提示必须至少有一个 `exact_terms`。

组件 type/key/model key 可以触发前端；普通字段名和表名不能。API、Controller、Service、方法或非动态 `GxP2.*` 栈可以触发后端。`CallAction` 和 `CallPublicAction` 只用于继续追踪低代码。动态生成类名不能作为源码关键词。

## 结构化源码工具

索引只保存在本地 `GxpLowcodeReadonly/source-index/`，内容限于相对路径、符号、路由、DTO、组件契约和调用边，不保存源码正文。需要上下文时从当前选中仓库实时有界读取。所有结果固定 `runtime_verified=false`。

- 组件 type/key/model key：先用 `inspect_component_source`，返回 designer、web/wap runtime、API、注册符号、模型绑定、数据集和过滤锚点。
- API Route 或跨端字段：用 `trace_api_contract` 串联前端调用者、组合后的 ASP.NET Route、Controller、DTO、接口和实现。外部 `@inbiz/utils` 包装器未在仓库中时必须保留 `wrapper_unresolved`，不得把 `{data: payload}` 直接当作最终 HTTP body。
- Controller、Service、方法或真实后端栈：用 `trace_backend_call_chain`。多实现、反射或同名方法返回候选，不静默选第一个。
- 数据集影响面：用 `inspect_dataset_usage`。发布引用与草稿引用分开；草稿明确标记不影响运行。返回的表名只作为 Schema 工具锚点。
- DataFilter 覆盖：先完成低代码 `inspect_component_filters`，再用 `trace_component_filter_contract`。必须展示历史反转 `dynamicWhere → conditionFilter（SQL 字符串）`、`staticWhere → dynamicFilter（JSON 条件）`。
- `source_repository_status` 查看路径、branch、commit、dirty 数量和索引新鲜度；`refresh_source_index` 仅刷新本地 metadata-only 索引。当前索引为 v3，按 layer 校验源码/配置依赖；结构化结果采用 64 KiB UTF-8 JSON 硬预算，裁剪时保留未决状态。

每项源码证据都给出 layer、kind、仓库相对 path、行号、symbol 和 confidence。源码索引 v3 对 Git NUL 状态与相关源码/配置文件内容摘要做校验；按工具请求的 layer 刷新，构建期间变更或读取代次持续变化时返回 unresolved。stale、缺失或歧义层的旧索引不参与精确证据输出；健康层保留结果但不形成跨层闭合结论。

请求来自有词法边界的真实 request 调用，普通路由字符串只作候选。函数结束、箭头函数、注释和模板表达式分别处理。后端使用 namespace/type/member/signature 身份与 receiver 类型约束；短名唯一不代表调用目标确定。业务调用、数据访问、基础库和未解析调用分开，基础库默认不递归。ZeroEntity 操作需有字段或工厂返回类型证据。

## 路径、入口和输出预算

- URL 复合写入或未知重赋值使旧字面量推导失效；确定的路径与动态查询分开。query_dynamic/query_status=unresolved 表示查询参数尚未验证，path_confidence 只描述端点路径，包装器仍保留 wrapper_unresolved。
- 已知命名空间和签名时，使用完整 symbol_id 或完整异常栈。短名歧义返回 starts 候选，不自动展开全部分支。
- 源码结果的结构化 JSON（UTF-8、两空格缩进）预算为 64 KiB，不含 MCP 外层封装。response_truncated=true、response_complete=false 时只作部分证据，查看 omitted 与 unresolved，不按截断结果宣称链路闭合。
- 源码指纹只散列该 layer 的源码和配置依赖；无关文档/产物仍显示在 Git 状态但不触发源码重建。同长度重复编辑保留内容摘要检查，不使用仅大小/mtime 的摘要缓存。

## 兼容受限搜索脚本

脚本位置：`scripts/search_source_evidence.py`

示例：

```powershell
python scripts/search_source_evidence.py `
  --layer frontend `
  --term <组件类型或方法名> `
  --term <MCP返回的精确词> `
  --pair <同一过滤或映射中的字段A> <字段B>
```

只在结构化工具尚未覆盖时使用。只有 `source_hints.candidate_layers` 包含对应层时才能选择该 `--layer`。重复传 `--term` 或 `--pair FIRST SECOND`；不要自行补充宽泛词。`--pair` 只在两个词位于同一文件时形成组合命中并提高排序；已有 `--term` 的精确命中文件不会仅因缺少组合词而被丢弃。

脚本与结构化工具共用仓库 resolver，使用字节级 `rg`/JSON 事件读取中文路径和上下文，排除依赖、构建、缓存和生成目录，并优先运行时组件、designer、Controller、Service 与 DTO。最多返回 20 个文件，只给前 5 个文件的上下文，响应不超过 32 KB；总 deadline 到达时返回已完成结果并标记截断。

仓库不存在、`rg` 不可用或无结果时返回紧凑错误，`scope_expanded=false`。此时不得搜索其他目录，也不得把“未命中”写成“源码不存在”。

## 证据分层与结论

- `低代码`：ActionDesign、草稿/发布、画布节点、完整参数、生成 C# 和只读表数据。
- `前端源码`：组件取值、事件、请求构造、过滤应用和运行状态映射。
- `后端源码`：API Route、Controller、Service、请求 DTO、查询和异常路径。
- `业务数据`：当前记录和关联数据是否满足配置条件。
- `页面运行`：实际 XHR/Fetch、控制台、组件状态和用户交互。
- `尚未验证`：静态证据无法证明的部署、缓存、真实请求或浏览器行为。

低代码、前端和后端静态证据可以定位矛盾，但不能替代浏览器运行验收。没有运行证据时明确写“静态检查完成，页面运行尚未验证”。
