# gxp-lowcode-readonly

GXP 低代码只读诊断 MCP。stdio 与 Streamable HTTP 共用同一个 `create_mcp()` 工厂和同一组 15 个工具；服务不会执行数据库写入、画布保存或发布。当前工具明确区分同一动作的可编辑草稿副本与运行发布副本，并支持页面反查、动作名称、组件过滤、字段和历史发布快照定位。

## 页面与组件定位

- `search_pages(query, limit=20)`：先按 Route/Id/OutId、中文显示名精确或包含匹配；无结果时只在命中中文二元词的有界候选中排序，不读取整个应用页面列表。
- `list_page_actions(page_identifier, limit=50)`：接收精确 Route、Id 或 OutId，列出页面全部未删除表单动作及 code、RefId、显示名称。
- `inspect_component_filters(identifier, component, ...)`：聚合同一组件跨分组的全部 `DataFilter` 写入点，返回执行阶段、完整过滤事实、父级分支和相邻节点；不返回生成 C#。

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
./scripts/start_mcp.ps1
```

数据库元数据默认保存到 `%APPDATA%/GxpLowcodeReadonly/database.json`，密码保存到 Windows Credential Manager，不进入插件目录。

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

历史服务器验收曾列出 11 个工具；当前本地定义为 15 个工具。远程服务需另行部署后才能具备本次能力；公网 8890 与数据库 ACL 仍是外部验收前置条件。
