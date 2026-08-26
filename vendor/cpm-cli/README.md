# cpm CLI

CPM 低代码平台的 AI 配套 CLI：把平台配置（页面 Schema、业务规则代码、模型字段、字典/数据集等）全量拉取物化为**自包含的项目目录**——快照平铺于项目根，`.cpm/` 缓存与 `skills/cpm-platform/` 技能同在其中，拷走这个目录即可在任意机器/AI 宿主上工作（**增量写入**：内容不变不重写，git diff/mtime 只反映平台真实变化）。

**第一用户是 AI Agent**（不是人类开发者）：输出机器可读（`--json`）、错误信息自带下一步指引、命令 `--help` 自解释。

## 安装

```bash
npm install
npm link          # 全局注册 cpm 命令（可选）
```

要求 Node ≥18。日常开发用 `npm run cpm -- <命令>`（tsx 直跑，无需构建）。

## 快速开始

```bash
# 1. 绑定平台与应用（凭据从环境变量或参数读取，无交互式输入）
export CPM_ACCOUNT=账号 CPM_PASSWORD=密码
npm run cpm -- login --url http://cpm.gxp2.com --app <appId> [--site <siteOutId>]

# 2. 健康检查
npm run cpm -- whoami

# 3. 拉取快照（全量请求 + 增量写入）
npm run cpm -- pull                # 人类可读摘要（含本次变化与各阶段耗时）
npm run cpm -- pull --json         # 机器可读（counts/changes/failures/durationMs/stageTimings）
npm run cpm -- pull --page <路由>  # 单页刷新
npm run cpm -- pull --concurrency 15  # 全局并发上限（缺省 10；网关压力大时调低）

# --out <目录>：指定项目目录（绑定、缓存、快照、skills 全在其中，拷走即用；缺省当前目录）
# 三命令通用：cpm login --out <目录> / cpm whoami --out <目录> / cpm pull --out <目录>

# 4. 打开快照
# 入口：项目目录下 indexes/pages.md（路由 → 目录的权威映射表）
```

升级 cpm-cli 后首次 pull 可能出现一次性格式对齐变化（changes.updated 偏大），二次起恢复零变化，属预期。流程设计按 manifest 的 processVersions 版本表增量跳过（版本未变不重拉 BPMN/节点配置）。

绑定信息存**项目目录**的 `.cpm/`（`config.json` 可提交 git）；凭据优先环境变量 `CPM_ACCOUNT`/`CPM_PASSWORD`，其次项目目录 `.cpm/credentials.json`（自动 gitignore）；token 缓存 `.cpm/token.json`（自动 gitignore）。项目目录 = `--out` 指定目录（缺省当前目录）。

## AI 宿主适配

Skill 已随每次 `cpm pull` 自动同步到项目内 `skills/cpm-platform/`（CLI 是权威源，每次全量同步，本地改动会被覆盖），**无需拷贝到全局 `~/.claude/skills/`**，适配只是指向：

- **Claude Code**：把项目内 `skills/cpm-platform` 拷到项目 `.claude/skills/`，或在项目 `AGENTS.md` 写一句指向 SKILL.md
- **Cursor / 其他**：在项目 `AGENTS.md` 写一句"分析本系统前先读 skills/cpm-platform/SKILL.md"

## 多项目配置

一个目录 = 一个应用，天然隔离。两种等价用法：`cd` 进各自目录分别 `cpm login --app <各自appId>` 后 `cpm pull`；或用 `--out` 显式指定——`cpm login --out D:/apps/qms --app <appId>`、`cpm pull --out D:/apps/qms`。AI 在哪个项目目录工作，读到的就是哪个应用的快照。凭据（环境变量）多项目共享。

## 项目目录结构速览

目录/文件命名一律 `中文名-短码`（短码 = 平台 route 或 8 位 code），人类可直接阅读。

```
D:/apps/qms/                # 项目目录（cpm pull --out D:/apps/qms，或 cd 进去后 cpm pull）
├── .cpm/                   # 绑定与缓存（config.json 可提交 git；token/credentials 自动 gitignore）
├── skills/cpm-platform/    # AI 技能（每次 pull 自动同步；快照数据 ↓ 平铺于项目根）
├── manifest.json           # 内容最后变化时间(pulledAt)/变化统计(changes)/计数/失败清单
├── indexes/pages.md        # ★ 页面定位入口（权威映射表）；model-usage.md 影响面入口
├── pages/<中文名-route>/   # page.json(原始Schema) / components.json(组件清单) / tree.md
│                          # / bindings.md(数据绑定) / bizflows/<描述-code>/(action.js|action.cs)
├── public-bizflows/       # 公共编排（全页面共享；代码两步拉取自 design，C# 在 action.cs）
└── models/ flows/ dictionaries/ datasets/ events/   # 资源定义（models 含 columns 字段清单）
```

关键语义（详见 `skills/cpm-platform/SKILL.md`）：页面主模型在 `page.json` 的 `content.form.model`；子表/下拉组件绑定的 `modelkey`/`dataCenter.value` 是**数据集 id**（指向 datasets/），不是模型 id。

## 常见错误与指引

| 错误输出 | 含义与下一步 |
|----------|--------------|
| `ERROR: 未提供平台凭据...` | 缺账号密码：向用户索要后 `cpm login --account --password` 或设环境变量 |
| `ERROR: 尚未绑定平台...` | 当前目录没 login 过：`cpm login --url <平台地址> --app <appId>` |
| `ERROR: 尚未绑定平台。请先执行 cpm login --out <目录>...` | `--out` 目录没 login 过：按提示命令补全 `--url <平台地址> --app <appId>` 重新 login |
| `ERROR: token 无效或已过期...` | 重新 login（凭据会话过期） |
| `ERROR: 未找到页面 <x>...` | `--page` 参数不对：核对路由或页面 ID，或去掉参数全量拉取 |

## 开发

```bash
npm test                    # vitest 全量
npx vitest run test/xxx     # 单文件
```

- `src/platform/`：HTTP 客户端、登录、资源端点封装（含模型详情/公共编排 design 两步拉取）
- `src/snapshot/`：快照物化（代码提取/组件清单/绑定/索引/增量写入器）
- `src/commands/`：login / whoami / pull
- `scripts/sync-knowledge.ts`：从 D:\code\test 同步组件/元件知识（手动重跑：`npx tsx scripts/sync-knowledge.ts D:/code/test/src/tools skills/cpm-platform`）
- 端点实测结论：`discuss/2026-08-25-endpoint-verification.md`
