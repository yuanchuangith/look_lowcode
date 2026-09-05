# 最近两轮优化独立复核报告

> 修复后续（2026-09-05）：七类问题的修复与验收见 `docs/optimization-repair-results.md`，五轮性能采样见 `docs/optimization-repair-benchmark.json`。本文保留独立复核时的历史结论。

> 复核日期：2026-09-05（本机时间）  
> 方法：Git 差异审阅、当前完整单测、7 组隔离反向探针、真实 F 盘源码只读解析与黄金链复查。  
> 边界：保留已有工作区变更与原评估报告；本次只新增复核报告和探针、补充规划记录，插件实现、安装配置及前后端业务仓库均保持原状。未执行开发数据库全量刷新、远程策略修改或页面运行验收。

## 1. 先给结论

**方向总体正向，但“能力增加”不等于“可信度提升”；当前存在已复现的局部负向回归。**

| 对象 | 收益判断 | 准确性判断 | 综合结论 |
|---|---|---|---|
| 2026-09-02，d7e596a，优化生成树 | 嵌套控制块、条件 AST、三态场景分析、结构化定位明显增强 | 发现旧符号操作符兼容性回归；当前测试覆盖主要结构场景 | **总体正向，附一项局部回归** |
| 2026-09-05，39e5b0a，数据库关系图添加 | 本地 Schema、聚合验证、共享否决和 TTL 复用有实际价值 | 部分候选验证失败及跨机器恢复后存在可信门禁缺口 | **有条件正向，关系结果仍需核查** |
| 当前未提交的源码证据工具，对应用户提供的报告 | 已知组件/API/DTO/Service 的定位能力增强 | 注释伪请求、旧证据精确化、指纹漏变更、错误短名连边均已复现 | **作为候选定位工具正向；作为确定根因依据存在负向影响，可信验收暂未达标** |

“最近两次”有两种口径：按 Git 是生成树与数据库关系图；按近期工作轮次及参考报告，则是数据库关系图与源码工具。本报告同时覆盖，避免把尚未提交的源码实现误算为最近一次提交。

用户给出的 F:\Desktop\git\look\_lowcode\docs 路径在本机未命中，实际参考文件位于当前仓库 docs/source-evidence-tools-evaluation-report.md。

## 2. 实测证据与统计口径

### 2.1 当前回归

- 执行：安装运行时 Python + PYTHONPATH=mcp，unittest discover -s tests -v。
- 结果：**共运行 113 项，其中 110 项通过、3 项 opt-in live 跳过，零失败**，本次运行耗时约 5.4 秒。
- 这证明已有用例通过，不代表未知业务场景正确率；新增反向探针复现了现有单测覆盖之外的问题。
- 原报告的“112 项通过”属于既有记录，本次采用实际测试输出，不沿用旧计数。

### 2.2 真实源码复查

对 F:\cpm\gxp2.components 与 F:\cpm\gxp2.web 运行现有扫描器，仅在内存中解析，不更新已安装索引。

| 项目 | 本次结果 |
|---|---:|
| 前端文件数 | 2,591 |
| 请求记录数 | 967 |
| 行注释中的伪请求 | 17 |
| function 缺失的请求 | 185 |
| HTTP method 缺失的请求 | 457 |
| 后端文件数 | 543 |
| 后端 Endpoint 数 | 593 |
| 后端调用边数 | 7,572 |

17 条只是本次识别的行注释数量，不是全部误报率；457 条方法缺失也不等于 457 条错误请求。

黄金链复查结果：

- /api/datasets/save → DataSetServices.BatchSaveData，status=ok。
- /api/datasets/search → DataSetServices.QueryDataCenter，status=ok。
- 两者均保留 contract_status=wrapper_unresolved，未把前端包装对象直接判定为最终 HTTP JSON。
- BatchSaveData 的 10 条调用边仍混有 Any、IsNullOrWhiteSpace、NewGuid 等基础调用；ctx.Insert 与 ctx.Update 的 data_access 均为 null；Update 列出 4 个短名候选，与原报告一致。

### 2.3 性能评价的限制

本次单次内存解析耗时：前端约 15.365 秒，后端约 3.989 秒；仅记录扫描耗时，未包含索引落盘，也未做冷/热缓存控制及旧版同输入对照。因此既不据此宣称性能提升，也不把它与原报告约 3.1 秒的索引记录直接比较为性能退化。

数据库优化的历史开发记录显示，刷新曾达到 300 秒上限，调整批量元数据读取与候选生成后约 68 秒完成，TTL 二次访问约 0.016 秒，涉及 915 张表、977 个候选、28 条验证关系。该数据来自 progress.md:39，是历史证据；本次未再次压测开发数据库，且不是两个发布版本的受控 A/B 实验。

## 3. 新增确认：数据库关系可信门禁

### R1：其它候选超时时，单个成功候选仍被升级为确定结果

- 位置：mcp/gxp_core/schema_snapshot.py:166、mcp/gxp_core/schema_snapshot.py:238、mcp/gxp_core/schema_snapshot.py:428。
- 探针：同一个 orders.user_id 对应 user.id 与 users.id 两个候选；前者查询超时，后者验证通过。
- 实际结果：attempts 同时包含 query_timeout 与 data_verified；省略目标表调用 resolve 时返回 data_verified，并选择 users。
- 问题：逻辑只统计通过者数量，没有把同组未完成验证的候选计入不确定状态。另一个候选“尚未验证”与“已验证不匹配”被等价处理。
- 影响：通过者的数据匹配事实可以成立，但“唯一可信目标”的推断证据不完整。
- 优先修复：保留每组候选的完整验证状态；存在 query_timeout、refresh_timeout 或 verification_error 时，将该组唯一性标为 unresolved。显式指定目标的匹配验证与自动选择唯一目标分别表达。

### R2：一台机器恢复关系后，另一台机器旧缓存直接恢复生效

- 位置：mcp/gxp_core/schema_snapshot.py:476、mcp/gxp_core/schema_snapshot.py:427、mcp/gxp_core/policy_client.py:87。
- 探针：两台逻辑机器各有有效快照，共享同一策略；第一台否决后第二台关系隐藏；第一台执行恢复，再由第二台解析关系。
- 实际结果：第二台返回 data_verified，新增验证调用次数为 0；即使设置当前验证结果应为不匹配，也直接复用了旧快照。
- 根因：restore 只移除本机 verified.json 中的旧关系；其它机器同步得到的是当前否决列表与 revision，没有与本地验证时间绑定的恢复失效门禁。
- 影响：违背“恢复后重新验证”的跨机器语义。现有测试只覆盖单机 restore，因而全绿仍会漏掉此问题。
- 优先修复：同步每条关系的恢复版本/时间戳，并让旧验证失效；简化方案是策略版本变化后保守失效相关缓存，再执行验证。

Schema 的正向部分仍然成立：目标唯一键与类型检查、最小 distinct 样本门槛、全量聚合匹配、策略服务失联时隐藏推断关系、刷新失败保留旧快照等均有实现及既有测试支持。但数据匹配关系与业务设计意义上的关系应持续分开标注。

## 4. 源码工具：同意原报告方向，但风险比摘要更广

### S1：已知 stale 仍输出 exact

- 位置：mcp/gxp_core/source_index.py:512、mcp/gxp_core/source_analysis.py:130。
- 仓库歧义、旧索引存在、repositories 为空时，ensure_source_index 的刷新次数为 0。
- inspect_component_source 返回 status=ok、index.stale=true，同时给旧 designer 文件第 7 行标注 exact；顶层还未透出原仓库错误。
- 这是对原报告关键问题的独立复现，不是仅依据报告文字作推测。
- 优先修复：在共用入口按请求 layer 执行门禁；错误、缺失或 stale 时仅返回候选/未解析状态，逐条实时复核后再提升置信度。

### S2：指纹解析会漏掉最前一个未暂存修改文件的后续变更

- 位置：mcp/gxp_core/source_config.py:148、mcp/gxp_core/source_config.py:173。
- Git porcelain 的首行形如“空格 + M + 空格 + service.ts”；_git 的 strip() 去掉开头空格，而后续仍按 line[3:] 截取路径。
- 探针结果：实际文件 service.ts 被解析为 ervice.ts，记录 missing=true；将真实文件改成明显不同的内容和长度后，fingerprint_changed=false。
- 影响：这是 stale 标记之前的漏检。即使修复 S1，单靠现有指纹仍会把旧索引误认为新鲜。
- 优先修复：为状态命令保留原始列格式，并采用 NUL 分隔解析，覆盖未暂存、暂存、重命名、中文路径及重复编辑场景。

### S3：注释、说明字符串和函数边界混淆

- 位置：mcp/gxp_core/source_index.py:162、mcp/gxp_core/source_index.py:164。
- 5 行探针只有 1 个真实请求，却输出 4 条：行注释、块注释、说明字符串均进入请求索引。
- 唯一真实箭头函数 actual 的请求被归到已经结束的 previous 函数；说明字符串还从邻近真实请求继承 POST。
- 真实仓库重新解析确认原报告的 17 条行注释伪请求、185 条空函数、457 条空方法计数。
- 优先修复：增加注释/字符串状态与函数作用域边界；只从实际请求调用表达式建立请求契约，路由字面量单独作为候选。

### S4：只有一个同名候选也可能连到无关方法

- 位置：mcp/gxp_core/source_analysis.py:336。
- 探针：OrderServices.Save 中调用 ctx.Update；索引中唯一同名定义是 UnrelatedServices.Update。
- 实际结果：工具把 UnrelatedServices.Update 当作目标，ambiguous=false，调用证据标记 structural，并允许继续沿它展开。
- 这比原报告的“多个短名候选产生噪声”更严重：即使候选数量为 1，也不等于接收对象类型吻合。
- 优先修复：依据 receiver 的类型、namespace、接口实现及签名约束目标；缺少类型证据时保留 candidate/unresolved，避免自动续接业务链。

所以原报告的“有条件正向、适合定位”判断合理，但 70/100 是主观成熟度评分，不是正确率，也不应抵消上述可信门禁的验收失败。

## 5. 生成树优化的局部负向回归

### T1：历史符号操作符从可求值退化为 unknown

- 位置：mcp/gxp_core/canvas.py:224；历史对照：d7e596a^ 的 mcp/gxp_core/diagnostics.py 显式支持 =、==、!=、<>。
- 探针：name=A，右侧字面量为 'A'。
- 当前结果：Equal → true；=、==、!=、<> 全部 → unknown。
- 根因：新 AST 求值器先去掉所有非字母字符，符号操作符归一化后成为空串。
- 影响：使用符号操作符的既有筛选条件静态复核能力下降；当前为解析层复现，未统计真实画布中这些符号的出现频率。
- 修复：在文字归一化前显式映射符号别名，并补旧输入形状的兼容测试。

该回归不足以推翻生成树优化的整体收益。现有测试覆盖嵌套条件配对、同名节点、循环/try 嵌套、缺损结构显式提示、最小完整块、图截断以及三态场景矩阵，结构能力扩展有依据；仍应把静态场景分析与运行执行分开。

## 6. 建议的决策与验收顺序

1. **保留整体架构，不整批回滚。** 生成树、本地 Schema、源码定位各自有实际收益。
2. **优先修复可信门禁。** S1/S2 的新鲜度、R1 的部分验证、R2 的跨机器恢复先闭合，再提升输出置信度。
3. **修复会制造伪业务链的解析。** S3 的注释/作用域、S4 的类型约束，其次补数据访问分类。
4. **单独恢复历史兼容。** T1 应作为小范围兼容修复处理。
5. **用反向用例作为合入门槛。** 本报告的 7 组探针应转为期望正确行为的回归测试；当前探针是复现工具，不是已经通过的修复验收。
6. **性能与业务准确率分别测。** 冷/热索引、同一输入前后版本、工具调用次数、输出体积、误报/漏报分别记录，避免用功能数量或单次耗时替代效果评估。

最终判断：**最近两次提交总体正向，但存在实质性局部回归；若“最近两轮”指 Schema 与源码工具，两者都是有条件正向。源码工具在人工复核的定位阶段有益，直接用来输出确定根因则会引入负向影响。**

## 7. 复现方式

在仓库根目录用已安装依赖的 Look 运行时 Python 执行：

    & "$env:LOCALAPPDATA\GxpLowcodeReadonly\.venv\Scripts\python.exe" docs/recent-optimizations-review-probes.py

脚本输出 7 组 JSON：frontend_comments_and_scope、stale_exact、unrelated_unique_short_name、partial_target_validation、cross_machine_restore、operator_compatibility、dirty_fingerprint。

所有探针只在临时目录操作；数据库和策略使用内存替身，Git 指纹用真实 porcelain 格式的模拟输出。不访问真实数据库、不更新已安装索引、不发送远程策略请求。真实 F 盘源码解析是本次另行执行的只读检查，其观测值记录于第 2 节。
