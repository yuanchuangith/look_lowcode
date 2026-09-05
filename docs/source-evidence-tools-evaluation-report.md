# 源码证据与业务链工具优化评估报告

> 修复后续（2026-09-05）：实现、回归、性能和发布验收见 `docs/optimization-repair-results.md`；本文保留修复前评估，不覆盖历史证据。

> 评估日期：2026-09-05  
> 评估对象：`docs/source-evidence-tools-implementation-plan.md` 对应的本地源码索引、API 契约、组件源码与后端调用链实现  
> 评估方式：实现对照、真实 F 盘仓库索引抽查、黄金链验证、反向误判探针；本次评估未修改前后端业务仓库或工具实现

## 1. 执行摘要

本次改动总体属于**有条件的正优化**，综合评估约为 **70/100（B-）**。

它显著提高了已知业务锚点的定位效率，已经能够稳定连接部分“前端调用 → API → Controller → DTO → Service”链路，并且本地索引、双路径仓库解析、远端工具隔离等基础设计方向正确。

但当前实现尚未达到计划定义的“可信源码证据系统”标准。最重要的问题不是覆盖率不足，而是两个准确性门禁没有真正闭合：

1. 仓库歧义或缺失时，旧索引仍可能以 `exact` 置信度返回精确行号。
2. 前端注释中的请求会被索引为真实 API 调用。

此外，后端调用链目前混入较多通用语言/API 调用，同时对实际数据访问存在漏标。因此当前版本适合作为**快速定位和候选生成工具**，不适合在没有源码复核的情况下直接输出确定业务根因。

## 2. 评估范围与证据标准

### 2.1 评估范围

- 本地前后端仓库解析与 F/G 双路径选择。
- 本地 metadata-only 源码索引。
- `inspect_component_source`。
- `trace_api_contract`。
- `trace_backend_call_chain`。
- Skill 中的源码证据路由与置信度约束。
- 本地 stdio 与远程 HTTP MCP 的工具隔离。

不在本报告范围内：

- 页面浏览器运行验收。
- 生产环境部署行为。
- 开发数据库 Schema/可信表关系算法本身。
- 对前后端业务代码质量的全面评审。

### 2.2 证据等级

本报告沿用 Skill 的证据分级：

- `exact`：当前唯一仓库、当前指纹下的精确源码定义或行号。
- `structural`：由静态结构直接支持，但未经过运行验证。
- `candidate`：存在同名、动态行为、外部包装器或解析不完整，只能作为候选。
- `unresolved`：当前静态证据不足以形成唯一结论。

评估原则：工具一旦在 `stale`、仓库歧义或解析不完整的情况下继续输出 `exact`，即判定为可信度门禁缺陷，而不只是功能覆盖不足。

## 3. 已确认的正向收益

### 3.1 本地索引性能和边界符合预期

既有验收记录显示，真实 F 盘仓库首次索引约 **3.1 秒**，明显低于计划中的 60 秒上限：

| 指标 | 结果 |
|---|---:|
| 前端文件 | 2,591 |
| 前端组件 | 139 |
| 前端路由出现次数 | 967 |
| 后端文件 | 543 |
| ASP.NET Endpoint | 593 |
| DTO | 362 |
| 后端调用边 | 7,572 |

索引只保存仓库指纹、相对路径、符号、路由、DTO 和结构化调用边，没有把完整源码正文放入索引或远端服务，方向符合本地证据边界。

### 3.2 双路径仓库解析有效

实现保留了两组默认仓库位置，并支持显式 preferred：

- 前端：`F:\cpm\gxp2.components`、`G:\hoyi\updateComponents\gxp2.components`
- 后端：`F:\cpm\gxp2.web`、`G:\hoyi\updateWeb\gxp2.web`

仓库解析能够比较 branch、commit、remote 和 dirty 状态；当两个副本身份不一致且没有 preferred 时可以产生 `REPOSITORY_AMBIGUOUS`，避免静默选错仓库。缺陷在于这一错误还没有贯穿到所有分析工具的最终证据门禁，见第 4.1 节。

### 3.3 黄金 API 链能够正确闭合

真实索引对 `/api/datasets/save` 的定位结果正确包含：

- 3 个前端 `dataSave` 调用者。
- `DataSetController.DataSave`。
- `DataSaveDto`。
- `DataSetServices.BatchSaveData`。

同时保留 `wrapper_unresolved`，没有把 `@inbiz/utils` 包装器下的 `{data: payload}` 直接等同于最终 HTTP JSON。这符合实施计划中的包装器不确定性门禁。

`/api/datasets/search` 也能够定位 `DataSetController.Search`、`DataCenterQueryDto` 和 `DataSetServices.QueryDataCenter`。

### 3.4 已知组件和历史兼容语义得到增强

- `TestPaper` 的主要设计器、运行时和 API 文件可以定位。
- `DataSetServices` 复数后缀可被识别。
- DataFilter 历史命名反转可以明确展示：
  - `dynamicWhere → conditionFilter`
  - `staticWhere → dynamicFilter`
- 中文路径与源码上下文读取不再依赖 PowerShell 文本管道，降低了乱码和路径解析问题。

### 3.5 工具暴露边界保持正确

安装后的本地 stdio MCP 暴露 35 个工具，远程 HTTP MCP 保持 16 个工具，没有把本地源码、Schema 或仓库元数据工具暴露到远端。

既有完整回归记录为 **112 项通过、3 项 opt-in live 跳过**。该结果证明既有能力没有出现大范围回归，但并未覆盖本报告发现的 stale、注释和同名调用链反向场景。

## 4. 已确认的问题

### 4.1 P0：stale 索引仍可产生精确结论

**性质：已复现的准确性缺陷。**

反向探针构造“旧索引存在，但当前仓库解析出现歧义”的状态，然后调用：

```text
inspect_component_source("TestPaper")
```

实际返回同时出现：

```text
status = ok
index.stale = true
exact evidence = 18
errors = [REPOSITORY_AMBIGUOUS]
```

这与实施计划第 3.3 节的要求冲突：stale 索引只能生成候选并实时复核，不能支持精确行号结论。

根因链：

- `mcp/gxp_core/source_index.py` 第 402–426 行：仓库解析异常只写入 `errors`，对应 layer 不进入 `repositories`。
- 同文件第 512–518 行：`ensure_source_index()` 只检查已经出现在 `repositories` 中的 `stale`；仓库异常导致集合为空时不会触发有效刷新或阻断。
- `mcp/gxp_core/source_analysis.py` 第 100 行起：`inspect_component_source()` 虽能算出 `index.stale=true`，仍继续读取旧 JSON 并输出 `exact`/`structural` 证据。

**影响：** 当代码已经变化、仓库副本切换或 preferred 配置异常时，Skill 可能引用旧文件和旧行号，并把它描述成当前仓库事实。这会直接降低排查结论可信度。

### 4.2 P0：前端注释被索引为真实请求

**性质：已在真实仓库复现的误报。**

当前前端索引统计：

```text
请求记录总数：967
确认来自注释的请求：17
HTTP method 未确认：457
```

示例：

```text
src/core/common/base/service.ts:337
// return await request.get(`/inbiz/api/services/modelengine/...`)
```

该注释仍被索引为有效 GET 请求。其他已抽查误报包括：

- `StaticDataText/index.tsx:45`
- `PersonalInfo/preview/web/services/index.ts:60`
- `AuditMatrixConfiguration/preview/web/service.ts:37`
- `DictionaryConfig/preview/web/service.ts:54`

根因位于 `mcp/gxp_core/source_index.py` 第 159–179 行：扫描器逐行直接对原始文本运行 `TS_ROUTE`，没有先处理 `//`、`/* ... */` 注释状态和字符串边界。

**影响：** 已删除或暂时屏蔽的旧接口可能继续进入 API 契约结果；当同一路由还存在真实调用时，会制造虚假的多调用者或错误方法归属。

### 4.3 P1：后端调用链噪声高且数据访问漏标

**性质：真实结果中的精度和召回问题。**

对 `DataSetServices.BatchSaveData` 的实测结果包含 10 条调用边：

```text
Any
IsNullOrWhiteSpace（3 次）
Find
ContainsKey
NewGuid
Insert
AddOrUpdate
Update
```

这些行大多确实位于当前方法体内，但不少只是基础库或集合调用，对“业务链”价值很低。`Update` 仅按短方法名找到 4 个不相关目标：

- `IModelsServices.Update`
- `ModelsServices.Update`
- `ModelsController.Update`
- `IntegrationAppController.Update`

与此同时，`ctx.Insert`、`ctx.Update` 的 `data_access` 都是 `null`。当前 `mcp/gxp_core/source_index.py` 第 334–346 行主要识别 `db.insert`、`.insert<`、`db.update` 等固定文本，没有覆盖实际仓库中的上下文对象调用形态。

**影响：** 工具能展示“这个方法里调用了什么”，但还不能可靠回答“业务最终调用到哪个实现、操作了什么数据”。如果上层忽略 `candidate`，容易把同名方法候选误读为真实链路。

### 4.4 P1：前端函数归属解析不完整

**性质：代码级确认的泛化风险，尚未在黄金链中造成错误。**

`_scan_frontend()` 使用单一 `current_function` 状态：

- 只在行中出现 `function` 时更新。
- 不识别常见箭头函数的函数体边界。
- 函数结束后不清空状态。

真实索引中 967 条请求有 185 条 `function=null`。其余记录中也可能存在“前一个 function 的状态泄漏到后续箭头函数或模块级代码”的情况。

`/api/datasets/search` 和 `/api/datasets/save` 的当前黄金路径归属正确，因此本项目前评为 P1，而不是已经污染黄金链的 P0。

### 4.5 P2：后端多行路由状态存在解析风险

**性质：实现风险；当前真实仓库探针未复现误绑定。**

后端扫描通过 `pending_http` 保存最近一次 `[Http*]`，等后续识别到方法签名后绑定。当前 593 个 Endpoint 中，特性行到 Action 行的最大距离为 4 行，抽查未发现跨方法泄漏。

但扫描器还没有完整处理预处理指令、复杂多行签名、异常特性组合和注释边界。应通过反向测试锁定，而不是仅依赖当前代码风格恰好规整。

## 5. 计划完成度差距

| 计划要求 | 当前状态 | 判断 |
|---|---|---|
| F/G 双路径与 preferred | 已实现 | 达标 |
| 本地 metadata-only 索引 | 已实现 | 达标 |
| 指纹刷新、锁、临时目录、原子替换 | 已实现 | 基本达标 |
| stale 只作候选并实时复核 | 有标志，无强制门禁 | 未达标 |
| 注释、字符串、括号边界词法扫描 | 逐行正则为主 | 未达标 |
| API → Controller → DTO → Service | 黄金链可用 | 基本达标 |
| namespace 级符号身份 | 主要使用短类型名/方法名 | 未达标 |
| 显式 DI、反射注册、多实现 | 仅覆盖部分继承约定 | 部分实现 |
| DTO 继承、嵌套、集合、可空 | 已覆盖主要结构 | 基本达标 |
| DTO 序列化别名 | 未见完整提取 | 未达标 |
| 数据访问操作识别 | 固定文本模式，存在漏标 | 部分实现 |
| 动态行为统一降级 unresolved | 部分场景已降级 | 部分实现 |
| 远端不暴露本地源码工具 | 已实现 | 达标 |

## 6. 量化评分

评分用于表达当前成熟度，不代表运行正确率统计。

| 维度 | 权重 | 得分 | 加权结果 | 说明 |
|---|---:|---:|---:|---|
| 定位能力与覆盖面 | 20% | 85 | 17.0 | 组件、API、DTO、Service 已形成主要链路 |
| 已知黄金链准确性 | 20% | 85 | 17.0 | datasets、TestPaper、DataFilter 表现良好 |
| 未知业务泛化准确性 | 25% | 55 | 13.8 | 注释、函数归属、短方法名降低泛化可信度 |
| 证据门禁符合度 | 20% | 45 | 9.0 | stale 仍输出 exact 是关键扣分项 |
| 性能、隐私和部署边界 | 15% | 90 | 13.5 | 本地索引快，远端隔离正确 |
| **综合** | **100%** |  | **70.3** | **B-：有条件正优化** |

## 7. 修复优先级

### 7.1 第一批：可信度门禁

1. `ensure_source_index()` 按“请求的 layer”判断，不以成功解析出的 `repositories` 集合作为唯一依据。
2. 任何目标 layer 出现 `REPOSITORY_AMBIGUOUS`、`REPOSITORY_NOT_FOUND`、`stale=true` 或指纹不可确认时：
   - 禁止返回 `exact`。
   - 能从唯一当前仓库实时复核时，把复核成功的单条证据升级为 `exact`。
   - 不能实时复核时统一返回 `unresolved`。
3. 分析工具入口统一应用该门禁，避免每个工具自行解释 stale。
4. stale 状态下不得继续使用旧索引生成确定的组件、路由、DTO 或调用链结论。

### 7.2 第二批：前端有界词法扫描

1. 增加跨行词法状态，至少处理：
   - `//` 行注释。
   - `/* ... */` 块注释。
   - 单引号、双引号、模板字符串。
   - 模板表达式 `${...}`。
2. 只在确认属于请求调用参数的字符串/模板字符串中提取路由。
3. 识别函数声明、函数表达式和箭头函数，并按括号深度关闭函数作用域。
4. 无法确认函数和 HTTP method 时保持 `candidate`，不参与唯一 API 契约闭合。

### 7.3 第三批：后端符号和数据访问

1. 符号主键升级为 `namespace + type + member + signature`。
2. 根据 receiver 的声明类型或构造注入类型约束候选，不再对短方法名做全库等价匹配。
3. 同一接口存在多个实现时返回实现集合与 DI 证据；缺少 DI 证据时保持 `unresolved`。
4. 扩展数据访问识别，覆盖 `ctx.Insert/Update/Delete`、仓储对象、扩展方法和项目实际 ORM 约定。
5. 把 `string.*`、LINQ、集合、`Guid.*` 等基础调用与业务调用分组，默认折叠噪声。

## 8. 修复后验收标准

### 8.1 stale 门禁

- 仓库歧义且旧索引存在时，所有源码工具均不得返回 `exact`。
- 仓库缺失、commit 变化、dirty 指纹变化分别有独立用例。
- 实时复核成功只升级被复核的证据，不整体恢复旧索引可信度。
- 用户切换 preferred 后，旧仓库路径和行号不再出现在新结果中。

### 8.2 前端扫描

- `// request.get('/api/x')` 不进入请求索引。
- `/* request.post('/api/x') */` 不进入请求索引。
- 普通说明字符串中的 `/api/x` 不进入请求索引。
- 模板字符串请求、跨行请求和对象参数请求能够正确识别。
- 箭头函数之间不会继承错误的 `current_function`。
- 当前确认的 17 条注释伪请求清零。

### 8.3 后端链

- `DataSetServices.BatchSaveData` 中 `ctx.Insert/Update` 被标记为数据访问。
- `Update` 不再关联到 Controller 和无关 Service 的同名方法。
- 多实现时结果明确为 `ambiguous/unresolved`，不选择第一个实现。
- namespace 相同短类名冲突、重载方法、扩展方法均有回归用例。
- 基础库调用默认折叠，但保留按需查看能力。

### 8.4 黄金链回归

- `/api/datasets/search` 继续命中 Controller、DTO、Service。
- `/api/datasets/save` 继续命中 3 个前端调用者，并保留 `wrapper_unresolved`。
- `TestPaper` 不误选打印/水印 `PaperConfig`。
- DataFilter 历史命名反转保持正确。
- 本地 stdio 工具数量按新契约更新；远程 HTTP 工具仍保持 16 个且不包含源码工具。

## 9. 最终结论

本次改动不是负优化。它建立了此前缺失的本地源码证据基础设施，并且对已知业务链产生了明确、可复现的效率收益。

但“有索引、有路径、有行号”不等于“证据可信”。stale 精确结论和注释伪 API 会把候选错误升级为事实，这是当前版本距离正式可信使用的核心差距。

建议发布判断为：

```text
内部辅助排查：可使用
输出候选位置：可使用
黄金链静态定位：可使用，保留 unresolved 信息
未知业务自动归因：暂不作为唯一依据
无需人工复核的确定结论：修复 P0 后再启用
```

完成两个 P0 修复并通过第 8 节反向验收后，预计可从当前 B- 提升到 B+/A-，届时才能把该能力定位为“可信源码证据系统”，而不仅是“更快的源码导航器”。

## 10. 相关文件

- [实施计划](source-evidence-tools-implementation-plan.md)
- [源码索引实现](../mcp/gxp_core/source_index.py)
- [源码分析工具](../mcp/gxp_core/source_analysis.py)
- [Skill 源码证据规则](../skills/gxp-lowcode-debug/references/source-code-evidence.md)
- [源码索引测试](../tests/test_source_index.py)
- [源码工具测试](../tests/test_source_tools.py)
