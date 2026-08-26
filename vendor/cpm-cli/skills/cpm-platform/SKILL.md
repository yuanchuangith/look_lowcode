---
name: cpm-platform
description: CPM 低代码平台项目背景与项目目录快照导读：目录结构、文件作用、复杂文件内部结构、cpm CLI 使用
---

# CPM 低代码平台与快照导读

CPM（GXP/InBiz）低代码平台：业务系统以**配置**而非手写代码构建。本 Skill 介绍平台背景、项目目录（快照平铺于项目根，与 `.cpm/`、`skills/` 同级）的目录结构与各文件作用、复杂文件的内部结构，以及 `cpm` CLI 的使用——目标是让你（AI）能快速理解项目信息、正确定位与读取所需数据。**定位（先读）**：快照项目只用于**分析问题**——快照内所有文件（含业务规则双代码）都是 `cpm pull` 的只读生成产物，不要直接修改；改动不会回写平台，且会被下次拉取覆盖。分析结论的修改动作应在平台 web 设计器中操作，完成后 `cpm pull` 刷新快照再验证。

## 平台背景：页面的三层构成

一个页面 = 三层配置，通过组件 `name` 相互关联：

| 层 | 是什么 | 存在于快照哪里 |
|----|--------|----------------|
| Schema（长相） | 表单组件树（Formily 形态 JSON） | `pages/<页面>/page.json`、`components.json`、`tree.md` |
| 业务规则（行为） | 页面事件逻辑（编排设计器产物），编译为 JS + C# 双代码 | `pages/<页面>/bizflows/` |
| 绑定（数据） | 页面引用的模型/数据集/字典等外部资源 | `pages/<页面>/bindings.md` |

核心机制：组件 `name` 是三层之间的关联键——Schema 里组件叫 `training_theme`，代码里就用 `inbiz('training_theme')` 取它，字段值直接落主模型同名列。

## 项目目录地图（快照根 = 项目根）

入口顺序：`README.md` → `indexes/pages.md`（路由 → 页面目录的**权威映射**）→ 进入具体页面目录。

入口模型：导航（顶栏，应用级）→ 菜单（功能级）→ 页面（载体）——菜单 JSON 的 `pageRoute`（`page/<route>`）挂页面 route，多菜单可挂同一页面，多数页面不经菜单直达（代码跳转/流程表单）。关联字段与查询路径 → `references/menus.md`。

| 路径 | 作用 |
|------|------|
| `manifest.json` | 平台地址、资源计数、**pulledAt（内容最后变化时间）**、changes 变化统计、failures 失败清单 |
| `indexes/pages.md` | 全部页面的权威映射表（路由 → 目录名 → 概述） |
| `indexes/model-usage.md` | 主模型 → 使用它的页面（影响面入口） |
| `indexes/component-usage.md` | 组件类型 → 使用它的页面 |
| `pages/<中文名-route>/page.json` | 页面原始 Schema（大文件，1MB+，需要组件级细节才读） |
| `pages/<中文名-route>/components.json` | 机器可读组件清单 + 主模型（结构见下） |
| `pages/<中文名-route>/tree.md` | 人类可读组件树缩进视图（先读这个了解结构） |
| `pages/<中文名-route>/bindings.md` | 该页全部数据绑定清单（结构见下） |
| `pages/<中文名-route>/bizflows/` | 业务规则：每条规则一个子目录（`描述-code/`），内含 `action.js`/`action.cs`（按平台有无缺席；README.md 是规则清单表） |
| `public-bizflows/` | 公共编排（全页面共享的可复用动作），`中文名-code/`，代码同 bizflows。action.cs 的 `InvokeDynamicMethod("<id>",...)` 以 32 位 id 引用公共编排/规则：拿 id 反查两处 README 的 id 列（公共编排查本目录，页面规则查 `pages/<页面>/bizflows/README.md`）得 code 后定位目录 |
| `public-methods/` | 编排平台公共方法参考源码（CLI 静态资产，非平台拉取）：action.js 的 `relatedAttributes.*` 与 action.cs 的 `_service.*`/`this.*` 在此查签名与语义 |
| `models/`、`datasets/`、`dictionaries/`、`events/` | 数据资源四模块：模型（表，**含 columns 字段清单**）/ 数据集（预置查询，组件 dataSetId 指向）/ 字典（枚举选项集）/ 平台级事件——字段与关联详解 → `references/data-resources.md` |
| `flows/` | 审批工作流（BPMN 引擎，独立于业务规则）：`README.md` 按分组索引，`<分组>/<流程>/{meta.json, process.xml, ext.json}`（结构见下） |
| `menus/` | 菜单树（功能入口，按分组，README 权威索引）；`navigations/` = 顶栏应用入口（两套数据）——字段表、菜单↔页面关联详解 → `references/menus.md` |
| `interfaces/` | 接口管理（物理/动态两模式，分组目录还原嵌套）——字段与查询详解 → `references/interfaces.md` |
| `languages/` | 多语言（按语种 key→文本映射；菜单/页面/导航名 `{multilingual}` 占位的翻译查询处）——详解 → `references/languages.md` |

命名规范：目录/文件名一律 `中文名-短码`（短码 = 平台 route 或 code），中文名缺失时回退纯短码；无 code 的资源与同名撞车兜底用**完整 id**（不截断，保证 AI 可按 id 检索）。例外：`flows/` 下的分组/流程目录用纯中文名（同名撞车才追加完整 id）。

## 复杂文件内部结构

### page.json（原始 Schema）

两个关键区：`content.form.model`（页面主模型）与 `content.schema`（组件树根）：
```
{
  "content": {
    "form":  { "model": { ModelKey, Name, Describe, ... } },   ← 页面主模型（唯一的页面级模型绑定）
    "schema": {                                                  ← 组件树根
      "type": "object",
      "properties": {
        "<组件name>": {
          "name": "<组件name>",
          "x-component": "EformInput",                           ← 组件类型（白名单见 components.json）
          "x-component-props": { ... },                          ← 组件配置（绑定字段在此：dataCenter/dictId/…）
          "title": { "value": "{multilingual}global.i18n-xxx" }, ← i18n key（翻译后才是显示名）
          "properties": { ... }                                  ← 子组件（容器才有）
        }
      }
    }
  }
}
```

字段组件的 `name` 即主模型字段路径；子表列名在其 `columnConfig.properties[].attributeName`。

### components.json（机器可读组件清单）

```
{
  "modelInfo": { ModelKey, Name, Describe } | null,   ← 同 page.json 的 form.model
  "componentList": [                                   ← 白名单内组件的压平清单（含子组件递归）
    {
      "id": "training_theme",                          ← 组件 name（inbiz('id') 的 id）
      "title": "培训主题",                             ← 显示名（已解 i18n 优先级：cardTitle > title.value > key）
      "componentType": "EformInput", "componentName": "输入框", "isForm": true,
      "ref":        { paramTypes, value, label, dataType, code: "inbiz('id')" },         ← 组件对象引用
      "valueRef":   { ..., code: "inbiz('id').value" },   ← 仅单值字段类有（读值场景直接粘贴）
      "binding":    { kind: "dataSet|dict|childModel|switchable", dataSetId/modelKey/dictId/... },
      "columns": [ { attributeName, title, dbType, ref: { code: "relatedAttributes.GetFormData('x')" } } ],  ← 仅表格类
      "buttons":  [ { id, title, type, position } ]    ← 仅表格类（列配置的操作按钮）
    }
  ],
  "stats": { containers, fields }
}
```

关键语义：`dataSetId` 指向 `datasets/` 目录；`modelKey` 仅在 switchable（树类）出现；表格取数用 `relatedAttributes.GetFormData('列名')`。

### bindings.md（页面数据绑定清单）

分节：**主模型（form.model）** → 数据集（组件 → 数据集 id+表名）→ 字典 → 子模型存储 → 可切换数据源 → 模型字段（Schema 字段路径）→ **审批流程（以本页为表单的 BPMN 工作流，含快照内目录跳转）** → 公共编排 → 组件引用全集 → 代码引用 inbiz() → ⚠ 失效引用（代码引用了 Schema 里不存在的组件）→ ⚠ i18n 缺失 key。注意：页面**只有 form.model 一个主模型**；子表/下拉组件绑的是**数据集**（不是模型），别混淆。

### 业务规则双代码

`action.js` 是前端执行版（浏览器事件），`action.cs` 是后端执行版（服务端动作）。多数纯前端规则只有 js——这是平台常态，不是拉取缺失。规则 README 表中「（平台无代码）」表示该规则平台本来就没有代码。

运行时坑（实测）：「提交后」类回调（AfterSave/AfterSubmitBackend）里改 formData 无效——数据已提交、`flow_status` 归流程引擎管（改提交数据走「提交前」元件）；详见 `references/elements/Page/AfterSave.md`。

### 审批流程三件套（flows/）

跨页面共享的审批工作流（Camunda BPMN 引擎），与页面业务规则相互独立。每流程一目录按分组组织：`meta.json`（版本；**pcPageKey=页面 OutId**，流程↔页面双向关联见 references/flows.md）→ `process.xml`（BPMN 链路：审批节点/条件/会签）→ `ext.json`（节点审批人/按钮/推送）。页面侧的 `bindings.md` 有「审批流程」节反向列出关联流程。节点对照键：XML 的 `task-xxx` id = ext.json `userTask[].activityId`。元素与字段详解 → `references/flows.md`。

## cpm CLI 速查（AI 优先用 --json）

| 命令 | 用途 |
|------|------|
| `cpm login --url <地址> [--account <账号> --password <密码>]` | 绑定平台并登录（应用/站点用内置默认值，无需传参；凭据也可走 CPM_ACCOUNT/CPM_PASSWORD 环境变量） |
| `cpm whoami --json` | 验证登录态与配置；三命令均支持 `--out <dir>` 指定项目目录（绑定、缓存、快照、skills 全在其中，缺省当前目录） |
| `cpm pull --json` | 全量拉取平台配置到项目目录（快照平铺于项目根；页面/规则/模型/流程/菜单/导航/接口管理/多语言 languages 等全资源；增量写入：内容不变不重写，git diff/mtime 只反映真实变化；报告含 durationMs/stageTimings 耗时统计） |
| `cpm pull --page <route> --json` | 只刷新单个页面 |
| `cpm pull --json --concurrency <n>` | 调全局并发上限（缺省 10；网关压力大时调低） |

pull 输出的 `changes`（新增/更新/删除计数与 removedPaths）告诉你平台侧改了什么；token 失效时按错误提示重新 login。

**时效提醒**：快照是拉取时刻的平台状态（看 `manifest.json` 的 pulledAt 与 changes）。分析结论用于修改决策前，先 `cpm pull` 刷新并核对 failures 清单确认无数据缺失。

## 深入指引（渐进式披露）

- 组件类型能力/属性/事件细节 → `references/components/<组件名>.md`；表单元素/字段语义 → `references/elements/`
- 审批流程 BPMN 元素 → `references/flows.md`；菜单树/导航、菜单↔页面关联 → `references/menus.md`；接口管理 → `references/interfaces.md`；多语言 → `references/languages.md`；数据资源四模块（模型/数据集/字典/事件）→ `references/data-resources.md`
