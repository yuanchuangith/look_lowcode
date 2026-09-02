# gxp-lowcode-readonly

GXP 低代码只读诊断 MCP。服务不会执行数据库写入、画布保存或发布。Windows/macOS/Linux 本地 stdio 在 16 个 Look 工具之外增加 5 个 CPM 快照工具；公网 Streamable HTTP 8890 只注册 16 个 Look 工具，不能读取本地 CPM 凭据、调用 CLI 或触发刷新。当前工具明确区分同一动作的可编辑草稿副本与运行发布副本，并支持页面反查、动作名称、控制流树、依赖关系图、组件过滤、字段和历史发布快照定位。

## CPM 本地快照定位

CPM 快照补充页面全貌、菜单、组件、模型、数据集、字典、事件、审批流程、接口和公共动作定位；Look 当前发布副本、画布节点、生成 C#、历史异常和业务记录仍是运行结论的权威证据。

- `cpm_snapshot_status()`：查看成功检查时间、CLI 版本、刷新错误和 30 分钟 TTL。
- `refresh_cpm_snapshot(force=false, page_identifier=null)`：刷新本地快照；完整基线存在时可安全更新单页。
- `search_platform_snapshot(...)`：有界搜索平台资源。
- `inspect_page_snapshot(...)`：按 Route/Id/OutId 检查页面结构、绑定和规则文件。
- `get_cpm_knowledge(...)`：只读快照中 `cpm-platform` 技能的一个白名单主题。

快照超过 1800 秒时工具会同步等待刷新，单次最多 300 秒。刷新在临时副本完成后才原子换入；超时或失败保留旧快照。平台密码只从 Windows Credential Manager 固定目标 `Codex.GxpLowcodeReadonly.Cpm` 读取，并仅通过子进程环境变量传给 CLI。

## 页面与组件定位

- `search_pages(query, limit=20)`：先按 Route/Id/OutId、中文显示名精确或包含匹配；无结果时只在命中中文二元词的有界候选中排序，不读取整个应用页面列表。
- `list_page_actions(page_identifier, limit=50)`：接收精确 Route、Id 或 OutId，列出页面全部未删除表单动作及 code、RefId、显示名称。
- `inspect_component_filters(identifier, component, ...)`：聚合同一组件跨分组的全部 `DataFilter` 写入点，返回执行阶段、完整过滤事实、父级分支和相邻节点；不返回生成 C#。

`inspect_action` 为每个命中节点增量返回最小 `control_flow` 配对元数据。`inspect_control_flow(identifier, ...)` 先解析完整动作分组，再按节点或范围裁剪最小完整控制块，可返回结构化块、文本树、控制流 Mermaid、数据依赖 Mermaid，以及最多 20 个命名场景的三态静态路径。它覆盖 IF/ElseIf/Else、循环和 Try/Catch/Finally；结构漂移、孤立分支、闭合错误或未知插件块会显式返回 `valid | partial | invalid`，不会把不完整窗口伪装成确定配对。

`inspect_action` 默认 `include_generated_csharp=false`，新增 `max_nodes=20`。传入 `terms` 不再隐式搜索生成 C#；旧调用方必须显式传 `include_generated_csharp=true`。精确 `csharp_line` 不受该默认值影响。节点超过 `max_nodes`、生成 C# 超过 20 处或完整参数命中超过 10 个节点时，响应返回截断/缩小范围元数据。

## 命中驱动源码排查

`diagnose_codex_input`、`inspect_action`、`inspect_component_filters` 和 `trace_dynamic_exception` 会增量返回不超过 4 KB 的 `source_hints`。它只包含动作、设计、组件、API、Service/Controller、精确词和组合词等逻辑锚点，不读取本机源码，也不会绕过生成 C# 的显式开关。

- 组件身份建议前端层；普通字段名或表名不会单独触发源码扫描。
- API Route、Service/Controller 或真实 `GxP2.*` 后端栈建议后端层。
- `CallAction`/`CallPublicAction` 只建议继续追踪低代码动作。
- 动态生成类名不会进入本地源码关键词。

Skill 仅在低代码证据不足且 `source_hints.candidate_layers` 非空时调用 `skills/gxp-lowcode-debug/scripts/search_source_evidence.py`。脚本固定只读 `G:\hoyi\updateComponents\gxp2.components` 与 `G:\hoyi\updateWeb\gxp2.web`，使用 `rg` 搜索，排除依赖、构建、缓存和生成目录；最多返回 20 个文件、前 5 个文件上下文，JSON 不超过 32 KB。它不联网、不构建、不修改文件，也不会在无命中时扩大目录。

## 运行方式

### 本地 stdio

Windows 本地注册见 [.mcp.json](.mcp.json)。首次使用：

```powershell
./scripts/setup.ps1
./scripts/configure_connection.ps1
./scripts/configure_cpm.ps1
./scripts/start_mcp.ps1
```

数据库元数据默认保存到 `%APPDATA%/GxpLowcodeReadonly/database.json`，密码保存到 Windows Credential Manager，不进入插件目录。

新电脑或 macOS/Linux 使用时，让 Codex 完整读取根目录 `AI-SETUP.md`，然后执行跨平台安装器：Windows 使用 `python scripts/install_codex_plugin.py`，macOS/Linux 使用 `python3 scripts/install_codex_plugin.py`。安装器会建立独立本地 marketplace、安装插件和运行环境；安装后必须新建 Codex 会话。凭据不随仓库迁移，需在新电脑的操作系统钥匙串中重新隐藏输入。

CPM 独立配置保存到 `%APPDATA%/GxpLowcodeReadonly/cpm.json`，不修改 `database.json`。版本化 CLI 安装到 `%LOCALAPPDATA%/GxpLowcodeReadonly/cpm-cli/0.3.1`，快照固定在 `%LOCALAPPDATA%/GxpLowcodeReadonly/cpm-snapshot`。`configure_cpm.ps1` 隐藏输入平台密码，保存凭据后执行首次登录和全量快照；需要有效平台地址、账号和密码才能完成真实验收。

手动拉取使用 Look 的安全包装命令（默认强制刷新，不需要传密码）：

```powershell
./scripts/pull_cpm.ps1                         # 强制全量拉取
./scripts/pull_cpm.ps1 -Page <Route或Id或OutId> # 强制单页拉取
./scripts/pull_cpm.ps1 -IfStale                # 仅超过配置 TTL 时拉取
./scripts/pull_cpm.ps1 -Json                   # 完整 JSON 报告
```

`setup.ps1` 同时在当前用户 PATH 中安装全局 `cpm` 命令，任意目录可运行：

```powershell
cpm status
cpm whoami                         # 轻量在线验证缓存 token
cpm pull
cpm pull --page <Route或Id或OutId>
cpm pull --if-stale
cpm pull --json
cpm --version
```

macOS/Linux 对应入口为 `sh scripts/setup.sh`、`sh scripts/configure_cpm.sh`、`sh scripts/configure_connection.sh` 和 `sh scripts/pull_cpm.sh`。运行数据使用 macOS `~/Library/Application Support/GxpLowcodeReadonly` 或 Linux `${XDG_DATA_HOME:-~/.local/share}/GxpLowcodeReadonly`，配置使用系统标准配置目录；密码只进入 macOS Keychain 或 Linux Secret Service，不提供明文回退。

### Streamable HTTP

[mcp/http_server.py](mcp/http_server.py) 默认监听 `0.0.0.0:8890`，MCP 路径为 `/mcp`：

```bash
python mcp/http_server.py
```

可通过 `GXP_LOWCODE_HTTP_HOST` 和 `GXP_LOWCODE_HTTP_PORT` 覆盖监听地址。当前 ActionDesign 浏览器配置固定为：

```text
id=gxp-lowcode-readonly
transport=streamable_http
url=http://43.135.137.212:8890/mcp
headers={}
timeoutSeconds=30
sseReadTimeoutSeconds=120
enabled=true
```

HTTP 服务只允许精确 Origin `http://cpm.gxp2.com` 与 `https://cpm.gxp2.com`，允许 `POST/GET/DELETE/OPTIONS` 和 MCP Session/Protocol Header，并暴露 `Mcp-Session-Id`。浏览器直接执行 `initialize → notifications/initialized → tools/list → tools/call`，不经过 Gateway MCP 代理。

该 HTTP 入口按当前产品决策不配置 MCP 身份认证。它一旦暴露公网，任何能直接访问端口的客户端都可能调用只读查询工具；精确 CORS 不是身份认证。部署时必须继续使用专用只读数据库账号、网络白名单、最小公网端口和服务端查询限制。

## Linux systemd 部署

[deploy/gxp-lowcode-readonly-http.service](deploy/gxp-lowcode-readonly-http.service) 使用 systemd credential 注入数据库密码：

```text
GXP_LOWCODE_CONFIG=/home/ubuntu/gxp-lowcode-readonly/database.json
GXP_LOWCODE_DB_PASSWORD_FILE=%d/db-password
LoadCredential=db-password:/etc/gxp-lowcode-readonly/db-password
```

`database.json` 只保存 host、port、database、user 和超时等非密码配置。密码不得进入浏览器 MCP Header、Gateway 配置、日志、Prompt、Trace 或 checkpoint。

## 只读边界

- 优先使用结构化工具定位动作、版本、画布、表结构和窄条件记录；`readonly_sql` 只在结构化工具无法表达时使用。
- SQL 仅允许单条 AST 校验后的只读语句，禁止跨库、危险节点和危险函数。
- 数据库会话设置执行超时，查询结果有行数和大小上限；`get_records` 强制窄条件和有界 `limit`。
- MCP 无数据库写入、动作 JSON 修改、保存、发布或历史版本修改工具。

## 验收边界

本机 `initialize/tools/list` 成功只证明服务进程可用。真实浏览器验收还要求：

1. 腾讯云安全组允许所需来源访问 TCP 8890。
2. 数据库白名单/ACL 允许服务主机 `43.135.137.212` 使用专用只读账号连接。
3. CPM 页面 Network 中请求直达 `43.135.137.212:8890/mcp`，完成 Session、CORS 和至少一次真实只读工具调用。

历史服务器验收曾列出 11 个工具；当前本地 stdio 定义为 21 个工具，HTTP 入口固定为 16 个 Look 工具。远程服务需另行部署后才能具备本次能力；公网 8890 与数据库 ACL 仍是外部验收前置条件。
