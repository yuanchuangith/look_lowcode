# 最近优化修复验收报告

> 后续边界复核：见 `docs/post-repair-optimization-review.md`。新增 URL 写入和超大响应探针暴露尚待补齐的边界；本报告的通过结论限于当时已执行的用例。后端 593→592 的差异现已定位为一个注释伪端点清理及四条方法路由纠正。

> 验收日期：2026-09-05。历史评估保留原结论，本报告记录后续修复与发布结果。
> 范围：本地插件与远程关系策略模块；保留原有未提交变更，未修改前后端业务仓库，未迁移业务数据库。

## 1. 结论

本次修复已完成代码、自动化回归、兼容策略升级、本地安装及独立进程冒烟验收。已知七类负向行为在对应回归与真实源码只读抽查中得到修复；生成控制树、本地 Schema、源码索引和黄金链保留。证据不足仍返回 candidate/unresolved，静态链路不等同于页面运行验证。

- 完整测试：148 项，145 通过，3 项显式启用的 live 测试跳过，零失败；较修复前 113 项增加 35 项。
- 远程策略模块：6 项隔离存储测试通过；线上只做健康、GET 协议和工具发现检查，未用生产关系执行测试性否决/恢复。
- 最终五轮对照：源码修复后最终采样：完整重建中位数约 6.32 秒、黄金查询批次约 1.08 秒；其中环境波动较上一轮明显，详见 follow-up 原始采样，不改变 60 秒上限与响应预算结论。
- 已确认的行注释伪请求 17 → 0；抽测最大响应 24,534 字节，低于 64 KiB。
- 新进程发现本地 35 项、远程 HTTP 16 项工具；新增源码与 Schema 工具保持本地边界。

## 2. 七类修复与证据

| 问题 | 修复结果 | 主要回归文件 |
|---|---|---|
| Git 变更漏检 | NUL 原始字节解析状态及重命名双路径；内容摘要覆盖同长度重写、中文与空格路径 | tests/test_repair_regressions.py、tests/test_source_config.py |
| 旧索引生成精确证据 | 索引 v2、按层门禁、构建前后指纹、读取代次最多重试一次；失败层不供应 exact，健康层保留 | tests/test_source_freshness_contracts.py、tests/test_repair_regressions.py |
| 不完整验证被当作唯一关系 | 保存完整候选状态与截断；超时/异常/未决不作为排除证明；显式目标标记 explicit_target | tests/test_repair_policy_contracts.py、tests/test_repair_regressions.py |
| 跨机器恢复及策略竞态 | 逐关系恢复版本、持久恢复记录、完成后同步、同组竞争候选失效、旧协议保守降级、突变后完整 ETag 同步 | tests/test_relation_policy.py、tests/test_repair_policy_contracts.py、tests/test_repair_regressions.py |
| 前端伪请求与函数串归属 | 共享词法边界区分注释/字符串/模板/作用域；真实调用与路由候选分离；重赋值降级；组件锚点同样过滤注释 | tests/test_source_lexical_contracts.py |
| 后端短名称误连 | 类型及签名身份、receiver 与工厂类型证据、候选停止递归；真实 ZeroDbContext 调用标为数据访问 | tests/test_source_lexical_contracts.py、tests/test_source_tools.py |
| 历史符号操作符退化 | 显式恢复 =、==、!=、<>；未知操作符保留 unknown | tests/test_repair_regressions.py |

发布冒烟额外发现 Windows Git 继承 MCP 输入管道造成卡顿：通过隔离实验确认后，为 Git 设置 DEVNULL 输入及 10 秒单命令超时，超时转换为结构化仓库错误。新增两项先失败后通过的回归，重新安装后原生 stdio 调用通过，未依赖运行时 monkeypatch。

## 3. 保留的正向能力

- TestPaper 组件精确身份与静态契约继续返回 ok。
- datasets save：保留 3 个前端调用者与 DataSetServices.BatchSaveData；datasets search：保留 2 个调用者与 DataSetServices.QueryDataCenter。
- API 契约仍显示 wrapper_unresolved，不把包装器前的 {data: payload} 当作最终 HTTP 请求体。
- DataFilter 保留历史映射 dynamicWhere → conditionFilter（SQL）、staticWhere → dynamicFilter（JSON）。
- GetZeroDbContext 的真实工厂证据定位到 GxP2.Services/Base/ServicesBase.cs:391，ctx.Insert/Update 归为数据访问，而非按 ctx 名称猜测。
- 嵌套控制树及既有非 live 回归通过；两个真实业务仓库最终 git status --short 均为空。

## 4. 性能口径与限制

详见 docs/optimization-repair-benchmark.json，脚本为 scripts/benchmark_source_repair.py。保留修复前实现副本，在相同 Python、真实仓库和查询输入下顺序执行各 5 次强制构建、各 5 次热查询批次，使用临时索引。最终对照运行期间未并行执行安装器。

| 项目 | 修复前中位数 | 修复后中位数 | 变化 | 门槛 |
|---|---:|---:|---:|---|
| 完整重建 | 3.0146 秒 | 3.3303 秒 | +10.47% | 中位数增幅 <20%，五次均 <60 秒 |
| 热查询批次 | 1.4769 秒 | 1.0023 秒 | −32.14% | clean 索引复用，不重建 |

最终修复版五次重建最大约 3.415 秒。初次保存的原始基线中位数为 3.0046/1.4901 秒，仍保留在 JSON 内；最终修复版相对该原始基线同样通过 20% 门槛。配对复测基线首轮约 40.215 秒，其具体原因未隔离，保留原样参加中位数计算，没有删除异常样本。

一次与插件安装重叠的中间测量出现约 4.052 秒重建中位数；该轮作为环境受干扰记录保留，未用作最终受控比较。早期实现的词法重复扫描等耗时已通过按需词法化、减少重复类型推导和 Git 调用完成优化。

当前真实扫描覆盖前端 2,591、后端 543 个文件，解析失败记录为零；这不代表支持完整 TypeScript/C# 语法。请求记录总数 967 → 461 仅是索引输出变化，不作为准确率或固定验收目标。后端端点计数 593 → 592 的单条差异未逐端点独立归因，本次只对指定黄金链和反向用例作通过结论。

原始对照文件保留在 F:/Users/25249/AppData/Local/Temp/look-repair-baseline-JLPILB；仓库 JSON 已保存最终五轮采样、仓库身份、原始基线及黄金结果，避免只依赖临时目录。

## 5. 发布与安装验收

- 远程服务 gxp-lowcode-readonly-http 为 active；只升级兼容 relation_policy.py，未替换其它远程模块。
- 升级前备份位于 /home/ubuntu/gxp-lowcode-readonly/backups/repair-20260905-policy-v2；策略文件权限保持 600。
- 线上 GET 返回 protocol_version=2、revision=0、restore_revisions，ETag 为 "policy-v2-0"；本地与线上策略模块 SHA256 一致。
- 回退仅回退代码，保留最新否决、恢复版本与审计；旧客户端仍需升级，新客户端连接旧服务使用 scope revision 保守规则。
- 本地使用 python -X utf8 scripts/install_codex_plugin.py 安装，最终版本 0.3.1+codex.local-20260905-013149；codex plugin list 显示 installed, enabled。
- 安装目录 source_config/source_index/source_backend/policy_client 和 Skill 的文件哈希与仓库匹配。Skill 与插件校验器通过。
- 独立 stdio 进程实际调用 status、TestPaper、save/search 和 DataFilter 均成功；观测到旧索引 v1 按需升级为 v2，随后前后端 stale=false、parse_incomplete=false。
- 远程 HTTP MCP 完成 initialize/list_tools，确认 16 项；本地 list_tools 确认 35 项，未调用远程业务工具。
- cpm --version 为 0.3.1；cpm status 仍报告原有 snapshot stale=True、failures=3，未触发 CPM 刷新。

## 6. 验收边界与后续

本次完成的验收是代码回归、真实源码只读验证、协议隔离测试和已安装新进程冒烟检查。数据库规模验证使用测试替身；真实开发库全量压测、三个 opt-in live 用例及页面端到端运行未执行，按计划另行安排。其他机器的客户端升级需在各机器执行安装器；本机模拟多客户端/离线周期的自动化通过，不等同于已替其它机器安装。

请新建 Codex 线程进行日常验收，确保会话加载最终安装版本。若发现新的语法覆盖空缺，保留 candidate/unresolved，再补回归，避免恢复旧的错误精确推断。

## 7. 交付索引

- 修复协议：docs/optimization-repair-contract.md。
- 性能原始采样与黄金摘要：docs/optimization-repair-benchmark.json。
- 历史问题：docs/recent-optimizations-independent-review.md、docs/source-evidence-tools-evaluation-report.md。
- 测试入口：运行 unittest discover -s tests，设置 PYTHONPATH 为仓库 mcp 与 tests，使用已安装 Look Python 运行时。
- 工作区已有修改保留；本次未执行 git commit 或创建分支。
