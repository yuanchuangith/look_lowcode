# 接口管理（interfaces/）详解

集成-接口管理：平台对外/对内 HTTP 接口的定义（本快照 113 个）。每接口一 JSON（平台原始行全量保真，`requestBody`/`responseBody` 已 parse 展开为对象，parse 失败时保留原始字符串）。

## 目录形态

按分组分目录，目录层级还原平台分组树的嵌套（如 `测试1/CESHI12/`）；README.md 是权威索引表（文件 | 接口 | 模式 | 方法 | 路径/表 | 鉴权）。`未挂载/` = 无分组或分组已删除的孤儿接口（平台侧脏数据）。

## 两种模式（`modeType`）

| 模式 | 语义 | 判定与字段 | 本快照 |
|------|------|-----------|--------|
| 物理（physical） | 手写 URL 转发：`requestUrl` 是完整路径/URL，可含 `$RequestLimitNum$`、`$DateFormat$` 等变量占位 | `modeType:"physical"`，`modeTable` 为空 | 96 |
| 动态（dynamic） | 绑定物理表自动生成 CRUD：增删改查由平台按表结构生成 | `modeType:"dynamic"`，`modeTable`=物理表名（如 `org_department`），`requestUrl`=模型 code | 11 |
| 未配置 | 草稿接口（无模式/方法/路径，README 表中「-」） | `modeType` 缺失 | 6 |

## 关键字段

| 字段 | 语义 |
|------|------|
| `name` / `code` | 接口名 / 短码 |
| `modeType` / `modeTable` | 模式（上表）/ 动态模式的物理表名 |
| `requestType` | HTTP 方法（GET/POST/PAGEGET 分页查询…） |
| `requestUrl` | 物理=请求路径；动态=模型 code |
| `isAuth` / `timeout` | 是否鉴权 / 超时 |
| `categoryId` | 分组 id（决定目录归属） |

## requestBody / responseBody 内部结构

`requestBody`：`headers[]`/`queryParams[]`/`pathParams[]`/`bodyParams[]`/`bodyFormData[]`（各项 `name/value/type/required/description`，动态模式参数可带 `alias` 映射列名）+ `contentType` + `rawBodyContent`（原始报文）+ `nodes[]`（树形结构定义，物理接口的请求体 schema）。

`responseBody`：`responseType`（text/json）+ `responseText` + `responseJsonNodes[]`（响应 schema 树）。

## 典型查询路径

1. **找某功能的集成接口**：README.md 按分组浏览，或全局 grep 接口名
2. **看接口入参**：JSON 的 `requestBody.queryParams/bodyParams`（动态模式参数 `alias` = 表列名）
3. **判断接口怎么实现**：`modeType`——物理改 URL/报文，动态看 `modeTable` 对应模型的 `models/` 定义
4. **与页面代码的关系**：接口管理面向外部/跨系统调用（组织同步、第三方对接）；页面 bizflows 里的 `inbiz.request('/gxp2/api/…')` 是直调平台内置端点，**不经过**这里定义的接口——排查页面请求问题时别混淆
