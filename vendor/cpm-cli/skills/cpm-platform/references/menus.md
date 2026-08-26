# 菜单与导航（menus/、navigations/）详解

菜单是用户进入功能的**入口**，页面是功能的**载体**——点菜单打开页面。入口有两套数据：

| 数据 | 是什么 | 目录形态 |
|------|--------|----------|
| `menus/` | 管理端菜单树（应用内功能入口：分组→菜单→子菜单） | 按顶层分组分目录，每菜单一 JSON；README.md 权威索引 |
| `navigations/` | 顶栏应用入口（工作台/文件/记录/培训/QMS…，跨应用级） | 每导航一 JSON + README.md |

menus/ 顶层分组与顶栏导航应用一一对应（`menus/文件/` ↔ `navigations/文件.json`），但两套数据独立维护、id 体系互不引用。README.md 中无菜单的分组（如「工作台」）是空分组，无对应目录。

## 菜单 JSON 关键字段（平台原始行全量保真）

| 字段 | 语义 |
|------|------|
| `name` / `outId` / `parentId` | 菜单名 / 菜单 OutId / **父菜单的 outId**（构建树，顶层为空） |
| `route` | 菜单**自身**路由（短码，≠ 页面 route，别混淆） |
| `pageRoute` | **关联页面**：`page/<页面route>`——去 `page/` 前缀即 `indexes/pages.md` 的 route |
| `pageOutId` / `pageName` | 关联页面 OutId / 页面名（冗余字段，定位以 pageRoute → pages.md 为权威） |
| `linkUrl` / `isInternalLink` / `openType` | 外链地址 / 内外链标记 / 打开方式 |
| `isVisible` / `isHomePage` / `isIconVisible` | 是否可见 / 是否应用首页（每应用一个，本快照 4 个） / 图标可见 |
| `sort` / `icon` | 排序 / 图标（JSON 字符串，内含图片 URL） |
| `menuCount` / `isHaveChild` | 子菜单数量提示（纯分组菜单的 `menuCount` > 0） |
| `cpmAppId` | 所属 CPM 应用 id |

菜单名可能是 `{multilingual}global.i18n-xxx` 占位，翻译查 `languages/`（→ references/languages.md）。目录名前缀体现父级（`基础管理-题库.json` 的父菜单是「基础管理」），目录本身不深层嵌套。

## 菜单↔页面关系（核心）

**关联键 = 菜单 `pageRoute`（`page/<页面route>`）→ `indexes/pages.md` 的 route 列。**

菜单三种形态：

| 形态 | 判定 | 本快照数量 |
|------|------|-----------|
| 内置页面菜单 | `pageRoute` 非空 | 118/143（去重后挂 114 个页面，全部可在 pages.md 命中） |
| 纯分组容器 | `pageRoute` 与 `linkUrl` 皆空，仅作层级节点 | 25 |
| 外链菜单 | `linkUrl` 非空 | 0（字段预留，本快照无实例） |

要点：

- **多对一**：同一页面可被多个菜单挂载（如「题库列表」页面 = 培训分组正主 + 未挂载孤儿双挂）
- **菜单只是页面入口之一**：424 个页面仅 114 个被菜单挂载；其余页面经页面代码跳转、审批流程表单（bindings.md「审批流程」节）、弹窗嵌套等到达——「无菜单挂载」≠ 不可达
- **页面侧无反向指针**：页面数据不记录挂载它的菜单，反查走 menus/README.md 或全局 grep

## 未挂载分组（平台脏数据）

`menus/未挂载/` = parentId 指向的父菜单不在菜单列表（孤儿，本快照 6 条）。其中有与正主菜单重复挂载同一页面者，统计页面挂载情况时注意去重。

## navigations/（顶栏入口）

每导航一 JSON：`name`/`route`（应用短码如 dms/tms/qms）/`cpmAppId`（前 8 位对应 /api/apps 应用）/`sort`/`isHomePage`。顶栏点击切换应用，应用内功能再走该应用的菜单分组——两级入口模型：**导航（应用级）→ 菜单（功能级）→ 页面（载体）**。

## 典型查询路径

1. **功能 → 页面**：menus/README.md 定位菜单行 → 「内置页面/外链」列 `page/xxx` → 去前缀查 `indexes/pages.md`
2. **页面 → 挂载菜单**：在 menus/README.md 搜页面 route（或全局 grep `"pageRoute": "page/<route>"`）
3. **某分组有哪些功能**：README.md 对应分组表（文件/排序号即平台展示顺序）
4. **应用首页**：grep `"isHomePage": true`（每应用一条）
