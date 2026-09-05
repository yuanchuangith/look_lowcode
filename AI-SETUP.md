# Look + CPM 安装指南（由 Codex 执行）

本文档面向在新电脑上打开本仓库的 Codex。目标是从仓库安装 `gxp-lowcode-readonly` 插件、本地 MCP 运行环境和 `cpm` 命令，不依赖原电脑上的插件缓存或 `deng` 目录。

## 安全规则

- 不读取、输出、记录或通过命令参数传递平台密码和数据库密码。
- 密码只通过隐藏输入保存到操作系统凭据存储：Windows Credential Manager、macOS Keychain 或 Linux Secret Service。
- Linux 没有可用的安全 keyring 后端时停止配置并提示安装系统 keyring，不得回退到明文文件。
- CPM、开发库 Schema 和源码业务链能力仅注册到本地 stdio；HTTP MCP 注册 16 个 Look 工具，本地 stdio 另含 5 个 CPM、7 个 Schema/可信关系和 7 个源码工具，共 35 个。

## 前置检查

确认以下命令可用：

```text
git --version
python --version        # Windows，要求 >= 3.10
python3 --version       # macOS/Linux，要求 >= 3.10
node --version          # 要求 >= 18
codex --version
```

缺少 Node 时安装当前 LTS；缺少 Python 时安装 3.10 或更高版本。不要使用管理员权限安装本插件。

## 一键安装插件和运行环境

尚未克隆仓库时先执行 `git clone https://github.com/yuanchuangith/look_lowcode.git` 并进入 `look_lowcode`；仓库中的 `AGENTS.md` 会引导 Codex 使用本指南，不需要人工复制技能目录。

在仓库根目录执行一个命令：

Windows：

```powershell
python .\scripts\install_codex_plugin.py
```

macOS/Linux：

```bash
python3 ./scripts/install_codex_plugin.py
```

安装器会创建 Look 虚拟环境、安装版本化 CPM CLI、安装不依赖仓库路径的 `cpm` 命令，并建立 `look-lowcode-local` marketplace 后安装 `gxp-lowcode-readonly`。macOS/Linux 如果提示 `~/.local/bin` 不在 PATH，将它加入 PATH 后重开终端。最后新建 Codex 会话，使新技能和 MCP 工具生效。

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

配置成功会立即完成首次全量拉取。数据库连接是独立可选步骤，使用对应的 `configure_connection.ps1` 或 `configure_connection.sh`。

Schema 快照需要本机数据库连接。远程否定策略使用内置 HTTPS 地址和共享 scope，全部免鉴权；新电脑安装后不需要迁移令牌。需要覆盖默认策略地址或 scope 时执行：

```powershell
./scripts/configure_schema.ps1 --policy-url https://POLICY_HOST --scope DEV_DB_SCOPE
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

先升级兼容协议 v2 的策略服务，再运行本仓库安装器更新插件。策略使用逐关系恢复版本及版本化 ETag；旧客户端缓存不含协议元数据时，新客户端会获取完整快照。源码索引 v3 按 layer 懒重建，旧关系缺少验证版本时按需重验，不触发无关 CPM 拉取或全库压力测试。回退时保留最新策略与审计文件。

## 验收

```text
codex plugin list
cpm --version
cpm status
cpm whoami
```

通过标准：插件来源为 `look-lowcode-local` 且版本为 `0.3.1+codex.*`；`cpm --version` 输出 `0.3.1`；`cpm status` 显示 1800 秒 TTL；`cpm whoami` 发起轻量在线请求并确认 token 有效，失败时退出码非零。

日常命令：

```text
cpm pull
cpm pull --page <Route或Id或OutId>
cpm pull --if-stale
cpm whoami
```
