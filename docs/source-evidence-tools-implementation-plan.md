# GXP 源码证据与业务链工具实现计划

## 1. 目标

在保留现有低代码、CPM 快照、开发库 Schema 和可信关系能力的基础上，增加一套仅在本地运行的源码索引与业务链解析能力，使 `gxp-lowcode-debug` 能够从已经确认的组件、API、Controller、Service、异常栈或数据集锚点出发，稳定返回可审计的前后端源码链。

本次实现遵循以下边界：

- 前后端源码仓库保持只读，不执行 `npm`、`dotnet build`、格式化或代码修改。
- 源码索引、路径、符号和调用边只保存在本机，不上传远程服务。
- 公网 HTTP MCP 继续只注册现有 16 个 Look 工具。
- 新增能力只注册到本地 stdio MCP。
- 静态源码证据只证明“代码中存在这条链”，不表述为页面运行已经验证。
- 普通表名、字段名、`CallAction` 或 `CallPublicAction` 仍不能单独触发源码扫描。

## 2. 多电脑仓库解析

### 2.1 默认候选路径

两套路径同时保留，并允许用户在其他电脑配置额外绝对路径：

```text
frontend:
  - F:\cpm\gxp2.components
  - G:\hoyi\updateComponents\gxp2.components

backend:
  - F:\cpm\gxp2.web
  - G:\hoyi\updateWeb\gxp2.web
```

新增无凭据配置文件：

```text
%APPDATA%/GxpLowcodeReadonly/source-repositories.json
```

macOS 和 Linux 使用现有 `_config_root()` 规则。配置只保存候选绝对路径及可选的 `preferred_frontend`、`preferred_backend`，不保存源码或凭据。

### 2.2 选择规则

1. 只检查配置中的绝对路径和内置 F/G 候选，不向父目录、其他盘符或用户目录扩散搜索。
2. 候选必须是可读目录，且 `git rev-parse --show-toplevel` 必须等于候选本身。
3. 每个候选记录 `path`、`branch`、`commit`、`remote_fingerprint` 和 `dirty_file_count`。
4. 仅一个有效候选时直接选择。
5. 多个候选指向同一 remote 且 commit 相同时，按显式 preferred、配置顺序、内置顺序选择，并返回其余 mirror。
6. 多个候选 commit 不同时：
   - 已配置 preferred 时选择 preferred，并在响应中标记 `alternates_present=true`；
   - 未配置 preferred 时返回 `REPOSITORY_AMBIGUOUS`，不默认使用较旧或路径排序第一的副本。
7. 所有候选均不可用时返回 `REPOSITORY_NOT_FOUND` 和已检查路径，不扩大范围。

### 2.3 新增配置入口

- `scripts/configure_source_repositories.py`
- `scripts/configure_source_repositories.ps1`
- `scripts/configure_source_repositories.sh`

安装器不要求源码仓库必须存在；安装后首次调用源码工具时按上述候选解析。配置脚本用于两套路径同时存在或使用自定义路径的情况。

## 3. 本地源码索引

### 3.1 文件位置

复用现有运行数据目录、文件锁、临时目录和原子替换机制：

```text
GxpLowcodeReadonly/source-index/
├── manifest.json
├── repositories.json
├── frontend/
│   ├── components.json
│   ├── component-contracts.json
│   ├── requests.json
│   └── symbols.json
├── backend/
│   ├── routes.json
│   ├── symbols.json
│   ├── dto-contracts.json
│   └── service-bindings.json
└── graph/
    ├── call-edges.json
    └── route-edges.json
```

索引只保存：仓库指纹、相对路径、符号名、行号、路由、组件契约、DTO 字段和结构化调用边。不保存完整源码正文。需要上下文时从当前选中的仓库实时有界读取。

### 3.2 新鲜度

索引新鲜度以仓库指纹为准，不使用固定每日 TTL：

```text
SHA-256(
  index_version + selected_root + HEAD_commit +
  relevant_dirty_file_paths_and_metadata
)
```

- clean 且 commit 未变化：直接复用索引。
- commit 变化：全量重建对应仓库索引。
- dirty 文件集合或相关文件大小/修改时间变化：至少重建受影响文件及其边；首版允许全量重建，但必须在 manifest 标明原因。
- 构建中断或解析异常时保留旧索引，并将结果标为 `stale`；stale 索引不得支持精确行号结论，只能返回候选后实时复核源文件。

### 3.3 扫描范围

前端默认只扫描：

- `src/core/components/**/*.ts|tsx`
- `src/core/common/**/*.ts|tsx`
- `src/core/entry/**/*.ts|tsx`
- `src/basic/**/*.ts|tsx`

后端默认只扫描：

- `GxP2.Web/Controllers/**/*.cs`
- `GxP2.Web/Program.cs`
- `GxP2.Web/RegistrationServices.cs`
- `GxP2.Web/BasicExtension.cs`
- `GxP2.IServices/**/*.cs`
- `GxP2.Services/**/*.cs`
- `GxP2.Model/Dto/**/*.cs`
- 与命中链有关的 `GxP2.Model/Model/**/*.cs`

固定排除 `.git`、`.vs`、`.dist`、`node_modules`、`dist`、`bin`、`obj`、`build`、`out`、`generated`、`coverage`、`wwwroot`、`DBInit`、压缩包、source map、字体和二进制资源。Plugin/PrintClient 默认不进入主平台索引，只有锚点明确命中对应命名空间时才作为独立 scope 检查。

### 3.4 解析策略

不依赖项目构建结果，也不依赖仓库 `node_modules`。使用有界词法扫描器处理字符串、注释和括号边界；只有结构闭合且身份唯一时写入 exact 边，否则写入 candidate 或跳过。

前端索引提取：

- `createBehavior`、`createResource`、`Behavior.name`、selector 和 `x-component`。
- 组件目录、designer Schema、web/wap preview、API、props、events、methods 和 locale。
- `request.get/post/put/patch/delete` 的 HTTP 方法、静态 URL 模板、调用函数和请求表达式。
- `form.createField`、`form.setValues`、`initialValues`、model/dataset 配置项。
- `dynamicFilter`、`conditionFilter`、组件公开 `setFilter`/`setConditionFilter` 实现。
- import/export 和组件本地直接调用边。

后端索引提取：

- Controller 类 `[Route]` 与方法 `[HttpGet/Post/Put/Patch/Delete]`。
- `[controller]`、`{controller}`、前导 `/`、绝对方法路由、占位参数和可选参数。
- Controller 方法参数、`[FromBody]`、DTO 类型和返回类型。
- interface、class、继承、实现关系和构造器注入。
- 反射式 `ServicesBase` 注册约定以及显式 `AddScoped/AddTransient/AddSingleton`。
- 方法内对注入服务的直接调用、同类方法调用以及 FreeSql/ZeroEntity 数据操作类别。
- DTO 属性、继承、嵌套类型、集合、可空类型和序列化名称；递归深度上限 3，循环引用显式截断。

## 4. 修复现有源码提示与搜索器

### 4.1 `source_hints` 修复

- `SERVICE_SYMBOL` 和 `_symbol_source_terms` 同时识别 `Service`、`Services`、`ServiceBase`、接口前缀 `I...Service(s)`。
- 从真实 `GxP2.*` 栈提取完整类型、短类型、方法名和源码文件名。
- `confidence=high` 时必须至少存在一个可搜索 exact term；否则降为 `medium` 并增加 `missing_search_term` 原因码。
- API Route 同时生成标准化路径和末级 endpoint 片段，但字段名、表名仍只作为 anchors，不单独触发源码层。
- 补充来源字段 `hint_version`，便于索引与 Skill 检查契约版本。

### 4.2 `search_source_evidence.py` 兼容修复

- 保留兼容 CLI，但仓库根改由公共 resolver 选择；显式 `--frontend-repo/--backend-repo` 仍可覆盖。
- 使用 `rg --json` 或字节级 JSON 解析，解决 Windows 中文路径和上下文乱码。
- 增加层级相关 include roots、源码扩展名和路径角色权重。
- 排序顺序改为：结构化 exact symbol/route → component runtime/designer → service/controller/DTO → paired terms → 普通源码共现 → knowledge/docs。
- 设置一次调用的总 deadline，超时返回已完成结果与 `truncated_reason=deadline`。
- CLI 只作为未被结构化工具覆盖的窄检索回退，不再承担组件/API 主链解析。

## 5. 新增本地 MCP 工具

新增 `LOCAL_SOURCE_TOOLS`，不加入 `MCP_TOOLS`。

### 5.1 `source_repository_status()`

返回：

- 前后端所有候选及选择结果。
- branch、commit、dirty 数量、索引指纹和索引状态。
- 歧义、缺失、旧索引及最近一次解析失败。

该工具不返回源码正文。

### 5.2 `refresh_source_index(force=false)`

按当前仓库指纹刷新前后端结构索引。使用跨进程文件锁、临时目录和原子替换；一个仓库失败不覆盖其旧索引，另一仓库可独立成功。

响应包含文件数、组件数、路由数、DTO 数、调用边数、解析失败清单和耗时。

### 5.3 `inspect_component_source(component_type, platform="web", focus=None)`

只接受已经由 `source_hints`、CPM 页面组件或用户明确给出的组件 type。

返回：

- 组件精确身份、类别和 web/wap 可用性。
- designer Schema、runtime preview、API、props/events/methods 注册文件及精确行。
- 模型绑定的读取、创建、更新和提交位置。
- 数据集配置角色、过滤字段和调用的共享前端服务。
- `dynamicFilter`/`conditionFilter` 的设置端与消费端。
- 直接 HTTP 请求和下一步可传给 `trace_api_contract` 的 route。

同名组件或多实现无法消歧时返回 `ambiguous`，不默认选择第一项。

### 5.4 `trace_api_contract(route, method=None, frontend_symbol=None)`

固定链路：

```text
前端调用者
→ 共享请求函数
→ 标准化 HTTP method + route template
→ Controller + action
→ 请求 DTO
→ 注入 Service 接口
→ Service 实现方法
→ 数据访问类别
```

契约比较输出区分：

- `matched`：可静态证明字段形状一致。
- `mismatch_candidate`：静态字段存在明确冲突。
- `wrapper_unresolved`：请求包装器不在可读源码范围内，不能确认实际 HTTP body。
- `dynamic_route`：URL 含未解析表达式。
- `ambiguous`：多个 endpoint 或调用者同时匹配。

工具不得把 `{data: payload}` 自动等同于最终 HTTP JSON；若 `@inbiz/utils` 包装器实现不在仓库中，必须保留 `wrapper_unresolved`。

### 5.5 `trace_backend_call_chain(symbol_or_stack, max_depth=6)`

支持完整异常栈、Controller 方法、Service 接口或实现方法。返回结构化调用树、接口实现映射、DTO、数据库操作、catch/rethrow/吞异常位置和循环截断。

只跟踪有源文件和符号证据的直接调用边；动态反射、字符串方法名和运行时 DI 多实现标为 `unresolved`。

### 5.6 `inspect_dataset_usage(dataset_key, include_drafts=false)`

复用 CPM 快照与现有只读数据库查询思想，不调用生成报告、发布或其他写入端点。返回：

- 数据集定义和模型候选。
- 使用它的页面、组件路径、control id 和配置角色。
- 当前发布表单动作、当前发布公共动作和工作台引用。
- `include_drafts=true` 时单独列出草稿引用，明确标记“不影响运行”。
- 可确认的表名只作为下一步 Schema 查询锚点；跨表关系仍必须由 `declared_fk`、`data_verified` 或 `live_database` 工具确认。

### 5.7 `trace_component_filter_contract(component_type)`

专门串联：

```text
DataFilter 画布参数
→ 生成 JS 属性
→ 组件 setFilter/setConditionFilter
→ 请求中的 filterInfo/conditions
→ 后端 DataCenterQueryDto
```

必须显式展示当前源码中的历史命名反转：`dynamicWhere → conditionFilter`，`staticWhere → dynamicFilter`。不同组件实现分别返回，不能把某个组件的消费方式推广给全部组件。

### 5.8 后续工具：`search_business_concept`

核心工具稳定后再增加。它只能把中文显示名、locale、组件类型、DTO 属性和 CPM 身份组成候选集合，然后要求调用上述精确工具消歧；不得用中文全文共现直接给出根因或业务关系。

完成 5.1 至 5.7 后，本地 stdio 工具数由 28 增至 35；远程 HTTP MCP 保持 16。

## 6. 证据与准确性契约

每个源码工具统一返回：

```text
repository: path / branch / commit / dirty_file_count
index: version / fingerprint / stale
evidence[]:
  layer: frontend | backend | cpm_snapshot | look_database
  kind: definition | route | call | dto | binding | usage
  path: repository-relative path
  line: exact start line
  symbol: normalized identity
  confidence: exact | structural | candidate | ambiguous
runtime_verified: false
unresolved[]: 未能静态证明的环节
```

判定规则：

- 文件名或普通词共现只能是 `candidate`。
- 完整符号定义、闭合 Attribute route、唯一接口实现和确定 import/call 才能是 `exact` 或 `structural`。
- 多命中必须返回候选和消歧字段，不按得分静默选择第一项。
- codemaps、knowledge 和注释只用于路由，必须由当前 commit 的真实源码复核后才能升级证据。
- 所有回答继续分层标记 `低代码`、`CPM快照`、`前端源码`、`后端源码`、`业务数据`、`页面运行`、`尚未验证`。
- 没有浏览器或运行样本时固定返回 `runtime_verified=false`。

## 7. Skill 路由调整

`SKILL.md` 只保留选择规则，不塞入全部解析细节；完整工具契约放入 `references/source-code-evidence.md`，符合渐进加载原则。

更新后的源码升级路由：

1. 组件 type/key/model key 命中：`inspect_component_source`。
2. `DataFilter` 或过滤覆盖问题：先完成低代码 `inspect_component_filters`，需要源码时再调用 `trace_component_filter_contract`。
3. API route 或跨端请求字段问题：`trace_api_contract`。
4. Controller/Service/方法/真实后端栈：`trace_backend_call_chain`。
5. 数据集影响面：`inspect_dataset_usage`。
6. 结构化工具未覆盖但仍有 exact terms：兼容 `search_source_evidence.py`。
7. 无精确锚点且只缺运行状态：升级页面运行证据，不做仓库全文扫描。

`agents/openai.yaml` 只在现有描述确实未覆盖“源码业务链”时做最小更新，不增加会吸引普通开发请求的宽泛描述。

## 8. 实施阶段

### Phase A：路径、提示和兼容搜索修复

- 新增 `source_config.py` 与仓库 resolver。
- 保留并探测 F/G 两套路径。
- 修复 `Services`/接口/真实栈 exact terms。
- 修复 Windows 中文输出、源码范围和排序。
- 增加配置脚本与安装文档。

验收：F-only、G-only、双路径同 commit、双路径不同 commit 和自定义路径均符合选择规则。

### Phase B：原子源码索引

- 新增 `source_index.py`、前后端词法解析器和索引 manifest。
- 接入现有跨平台文件锁、临时目录与原子替换。
- 实现指纹刷新、旧索引保留和有界上下文读取。
- 注册 `source_repository_status`、`refresh_source_index`。

验收：真实仓库首次索引在 60 秒内完成；clean commit 重用查询不触发重建；单次工具响应不超过 64 KB。

### Phase C：组件与 API 主链

- 实现 `inspect_component_source`。
- 实现 ASP.NET route 组合器和 `trace_api_contract`。
- 实现 DTO 递归、request-wrapper 未确认状态和多 endpoint 消歧。

验收：`TestPaper` 和 `/api/datasets/search|save` 场景返回完整、分层、可审计链路。

### Phase D：后端调用链与数据集影响面

- 实现接口→实现→方法调用边和 `trace_backend_call_chain`。
- 复用 `FormFieldExtractor` 的页面字段解析思想。
- 用只读查询/CPM 快照实现 `inspect_dataset_usage`。
- 实现 `trace_component_filter_contract`。

验收：复数 `DataSetServices` 栈、DataFilter 历史映射、发布/草稿数据集引用均正确区分。

### Phase E：Skill、文档与发布

- 更新 `source-code-evidence.md`、`SKILL.md`、README、使用手册和 `AI-SETUP.md`。
- 更新本地工具数量断言为 35，远程仍断言 16。
- 运行插件安装器完成 cachebuster/reinstall 验证。
- 安装后验证 `codex plugin list`、`cpm --version`、`cpm status`，并在新线程做真实工具发现。

## 9. 测试计划

### 单元测试

- 路径解析：F/G、自定义路径、Git 根不匹配、两个不同 commit、dirty checkout。
- 编码：中文目录、中文源码上下文、UTF-8/Windows 管道输出。
- source hints：`Service`、`Services`、接口、Controller、真实 GxP2 栈、动态生成类排除。
- 前端组件：Behavior/Resource、web/wap、designer/preview、props/events/methods、model 读写。
- 前端请求：字符串、模板字符串、共享函数、动态 URL、外部 URL。
- 后端路由：`[controller]`、`{controller}`、前导 `/`、绝对方法 route、空 method route、占位/可选参数。
- DTO：继承、嵌套、集合、可空、循环、序列化别名。
- Service：反射注册、显式 DI、多实现、接口方法和直接调用。
- 索引：并发刷新一次、失败保留旧索引、commit/dirty 变化失效、原子替换。

### 真实仓库集成测试

- `TestPaper`：设计 Schema、runtime、三个模型绑定、事件、API 和数据集角色完整。
- `DataFilter`：命名反转和不同组件消费端完整。
- `/api/datasets/search`：组件 helper → shared service → Controller → DTO → Service。
- `/api/datasets/save`：三个前端调用者、Controller、`DataSaveDto`、`IDataSetServices`、`DataSetServices`；请求包装器未知时不得误报确定 mismatch。
- `GxP2.Services.Data.DataSetServices.BatchSaveData` 栈：生成非空 exact terms 并定位实现。
- “试卷”中文概念：不得误选水印/打印 `PaperConfig` 作为培训试卷主链。

### 契约与边界测试

- 本地 stdio 35 工具，HTTP MCP 16 工具。
- 远端请求中不出现源码路径、源码正文、符号索引或 Git 元数据。
- 源码仓库执行前后 `git status` 一致。
- 不启动 `npm`、`dotnet`、格式化器或写入业务仓库。
- 无锚点、歧义、stale 索引和动态反射均返回 unresolved，不输出确定根因。

## 10. 完成标准

以下条件全部满足才算实现完成：

1. 两套 F/G 默认路径和自定义路径均通过选择测试。
2. `Services` 栈、中文输出、路由组合和搜索排序的已复现问题全部有回归测试。
3. 5.1 至 5.7 七个本地工具均注册、文档化并在真实仓库场景通过。
4. `TestPaper`、`DataFilter`、datasets search/save 和复数 Service 栈四类链路均返回精确源码锚点。
5. 多候选、动态请求、外部包装器和过期索引不会被描述为确定事实。
6. 全量测试、Python 编译检查和 `git diff --check` 通过。
7. 两个业务源码仓库保持只读且工作树状态不变。

