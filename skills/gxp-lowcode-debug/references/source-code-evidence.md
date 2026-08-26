# 命中驱动源码证据

只在 `SKILL.md` 的源码升级门禁成立时读取和执行本流程。低代码配置已经解释问题时立即停止，不读取源码仓库。

## 固定只读仓库

- 前端：`G:\hoyi\updateComponents\gxp2.components`
- 后端：`G:\hoyi\updateWeb\gxp2.web`

不得从仓库路径向上扫描，不得自动搜索其他盘符或目录。源码排查默认不联网、不构建、不修改、不格式化。

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

组件 type/key/model key 可以触发前端；普通字段名和表名不能。API、Controller、Service、方法或非动态 `GxP2.*` 栈可以触发后端。`CallAction` 和 `CallPublicAction` 只用于继续追踪低代码。动态生成类名不能作为源码关键词。

## 受限搜索脚本

脚本位置：`scripts/search_source_evidence.py`

示例：

```powershell
python scripts/search_source_evidence.py `
  --layer frontend `
  --term <组件类型或方法名> `
  --term <MCP返回的精确词> `
  --pair <同一过滤或映射中的字段A> <字段B>
```

只有 `source_hints.candidate_layers` 包含对应层时才能选择该 `--layer`。重复传 `--term` 或 `--pair FIRST SECOND`；不要自行补充宽泛词。`--pair` 只在两个词位于同一文件时形成组合命中并提高排序；已有 `--term` 的精确命中文件不会仅因缺少组合词而被丢弃。

脚本使用 `rg` 固定字符串搜索，排除 `.git`、`node_modules`、`dist`、`bin`、`obj`、缓存和生成目录。结果按同一文件命中的不同关键词数量降序排列：最多返回 20 个文件，只给前 5 个文件的上下文，响应不超过 32 KB。输出包含仓库、branch、commit、dirty 文件数、搜索词、命中文件、上下文和截断状态。

仓库不存在、`rg` 不可用或无结果时返回紧凑错误，`scope_expanded=false`。此时不得搜索其他目录，也不得把“未命中”写成“源码不存在”。

## 证据分层与结论

- `低代码`：ActionDesign、草稿/发布、画布节点、完整参数、生成 C# 和只读表数据。
- `前端源码`：组件取值、事件、请求构造、过滤应用和运行状态映射。
- `后端源码`：API Route、Controller、Service、请求 DTO、查询和异常路径。
- `业务数据`：当前记录和关联数据是否满足配置条件。
- `页面运行`：实际 XHR/Fetch、控制台、组件状态和用户交互。
- `尚未验证`：静态证据无法证明的部署、缓存、真实请求或浏览器行为。

低代码、前端和后端静态证据可以定位矛盾，但不能替代浏览器运行验收。没有运行证据时明确写“静态检查完成，页面运行尚未验证”。
