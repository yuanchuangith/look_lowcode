# Look + CPM 安装指南（由 Codex / Claude 执行）

本文档面向在新电脑上打开本仓库的 Codex 或 Claude Code。目标是从仓库安装 `gxp-lowcode-readonly` 插件/技能、本地 MCP 运行环境和 `cpm` 命令，不依赖原电脑上的插件缓存或 `deng` 目录。

本文维护安装与验收步骤；日常提问见[使用手册](GXP低代码只读排查使用手册.md)，工具与历史资料见[文档索引](docs/README.md)。插件版本以 [.codex-plugin/plugin.json](.codex-plugin/plugin.json) 为准，CPM CLI 版本单独验收。

## 安全规则

- 不读取、输出、记录或通过命令参数传递平台密码和数据库密码。
- 密码只通过隐藏输入保存到操作系统凭据存储：Windows Credential Manager、macOS Keychain 或 Linux Secret Service。
- Linux 没有可用的安全 keyring 后端时停止配置并提示安装系统 keyring，不得回退到明文文件。
- CPM、开发库 Schema、源码业务链、业务关系图、编辑交接及数据库设置能力仅注册到本地 stdio；HTTP MCP 固定注册 16 个基础 Look 工具，本地 stdio 另含 5 个 CPM、7 个 Schema/可信关系、7 个源码、6 个业务图谱、2 个本机编辑交接和 1 个数据库设置工具，共 44 个。

## 前置检查

确认以下命令可用：

```text
git --version
python --version        # Windows，要求 >= 3.10
python3 --version       # macOS/Linux，要求 >= 3.10
node --version          # 要求 >= 18
codex --version         # 若使用 Codex
```

缺少 Node 时安装当前 LTS；缺少 Python 时安装 3.10 或更高版本。不要使用管理员权限安装本插件。

## 一键安装插件和运行环境

尚未克隆仓库时先执行 `git clone https://github.com/yuanchuangith/look_lowcode.git` 并进入 `look_lowcode`；仓库中的 `AGENTS.md` 会引导 AI 使用本指南，不需要人工复制技能目录。

### 1. 为 Codex 安装

在仓库根目录执行对应命令：

Windows：

```powershell
python .\scripts\install_codex_plugin.py
```

macOS/Linux：

```bash
python3 ./scripts/install_codex_plugin.py
```

安装器会创建 Look 虚拟环境、安装版本化 CPM CLI、安装不依赖仓库路径的 `cpm` 命令，并建立 `look-lowcode-local` marketplace 后安装 `gxp-lowcode-readonly`。macOS/Linux 如果提示 `~/.local/bin` 不在 PATH，将它加入 PATH 后重开终端。最后新建 Codex 会话，使新技能和 MCP 工具生效。

### 2. 为 Claude Code 安装

在仓库根目录执行对应命令：

Windows：

```powershell
python .\scripts\install_claude.py
```

macOS/Linux：

```bash
python3 ./scripts/install_claude.py
```

安装器会自动创建环境、挂载项目级与用户级 `.claude/skills/` 联接、将项目 `.claude/` 自动加入 `.gitignore`、配置项目 `.mcp.json` 与用户 `~/.claude/.mcp.json`，并自检 44 个 MCP 工具的完整注册。重开 Claude Code 会话或重连 MCP 后，输入 `/gxp-lowcode-debug`。

若已有通过 Claude CLI 注册的用户级服务，另核对其实际配置及启动路径；安装器写入上述文件不等于改写 `~/.claude.json` 中既有的用户级注册。

## 首次配置和拉取

凭据不会随 Git 仓库迁移。换电脑后需要重新隐藏输入一次：

Windows：

```powershell
.\scripts\configure_cpm.ps1
```

macOS/Linux：

```bash
sh ./scripts/configure_cpm.sh
```

配置成功会立即完成首次全量拉取。数据库连接是独立可选步骤，仅在用户要求时配置。在任一插件目录运行 `python scripts/database_settings.py`（macOS/Linux 可用 `python3`）打开 Look/Write 统一设置窗口；密码隐藏输入到操作系统凭据库。模型可用本机 `database_settings` 查看非敏感设置、打开窗口或根据用户明确指定的地址、端口、库名及账户进行测试后保存，不接收密码。旧 `configure_connection.ps1` / `configure_connection.sh` 在共享配置存在时转到统一设置窗口；尚未采用共享配置时保留原配置流程。旧编辑流程尚未完成时不得切换目标库。

Schema 快照需要本机数据库连接。关系否决、恢复审计和版本元数据只保存在本机 `relation-policy-local.json`，不再连接策略服务器。首次使用导入本机已有的同 scope 旧缓存；旧配置中的远程地址被忽略。需要设置本地 scope 时执行：

```powershell
./scripts/configure_schema.ps1 --scope DEV_DB_SCOPE
```

macOS/Linux 使用 `sh scripts/configure_schema.sh`。首次调用 Schema 工具时生成本地快照，此后按 86400 秒 TTL 刷新。

源码工具默认同时检查以下两套路径，不要求安装时存在：

```text
frontend: F:\cpm\gxp2.components, G:\hoyi\updateComponents\gxp2.components
backend:  F:\cpm\gxp2.web,        G:\hoyi\updateWeb\gxp2.web
```

自定义路径或两个不同 commit 的副本需要显式选择 preferred：

```powershell
./scripts/configure_source_repositories.ps1 --frontend F:\cpm\gxp2.components --frontend G:\hoyi\updateComponents\gxp2.components --preferred-frontend F:\cpm\gxp2.components --backend F:\cpm\gxp2.web --backend G:\hoyi\updateWeb\gxp2.web --preferred-backend F:\cpm\gxp2.web
```

macOS/Linux 使用 `sh scripts/configure_source_repositories.sh` 和对应绝对路径。配置只写系统配置目录；索引只写系统数据目录，不写源码仓库。

## 可信关系与源码索引升级

运行本仓库安装器更新插件即可，无需策略服务器。否决和恢复保留本机逐关系版本，切换前的关系验证按需重验，已有表结构缓存保留。源码索引 v4 按 layer 懒重建，保存实际解析字节的 SHA-256 并绑定 generation；旧索引无需手工迁移。不触发无关 CPM 拉取或全库压力测试。服务器历史文件不自动删除。

## 验收

### Codex 验收

```text
codex plugin list
cpm --version
cpm status
```

通过标准：插件来源为 `look-lowcode-local`，版本前缀与仓库 manifest 一致；`cpm --version` 输出 `0.3.2`，`cpm status` 的 `cli` 也为 `0.3.2`；安装器会把已有托管拉取配置切到新 CLI，保留平台、账户、快照位置和凭据。CPM TTL 默认 5400 秒（普通查询按需刷新，明确重新拉取跳过缓存）。只有需要在线认证检查时另运行 `cpm whoami`，不要把它作为源码/Schema 本地工具的必需步骤。安装成功后新建 Codex 线程。

### Claude Code 验收

```powershell
python .\scripts\install_claude.py --verify-only
```

通过标准：输出 `[OK] MCP initialize / ping / tools/list passed: 44 tools registered.`，且重开 Claude Code 会话后可识别 `/gxp-lowcode-debug`。`--verify-only` 不安装、不改配置；`--skip-runtime` 只跳过依赖安装，仍会执行技能与 MCP 配置步骤。

协议自检不调用业务工具，只证明启动及工具注册可用；不证明数据库连接或真实业务排查已验收。

日常命令：

```text
cpm pull
cpm pull --page <Route或Id或OutId>
cpm pull --if-stale
cpm whoami
```

`cpm pull` 会更新本地 CPM 快照；源码索引和 Schema 快照分别由首次使用或过期后的对应 MCP 工具按需刷新，不会因为插件安装自动执行开发库全量扫描。


## 本地图谱升级与验证

安装器不会刷新 CPM 或写业务数据／平台设计，也不改变凭据。首次使用图工具在系统数据目录初始化 business-graph.sqlite3，原 JSON 和 .legacy-v1.json 保留原样；旧记录缺身份或证据时保留待复核，不补猜。图缓存失败继续只读排查，不双写旧 JSON。

仓库验收可执行 `python scripts/verify_business_graph_stdio.py --server-root <已安装插件目录>`；只使用临时目录和脱敏夹具，验证六个图工具与 A→B→C→D 融合，不向真实图注入测试数据。新建 Codex 线程才能加载更新后的 44 工具和技能。
