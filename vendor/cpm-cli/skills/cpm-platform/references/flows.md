# 审批流程（flows/）详解

CPM 平台的审批工作流由 edoc2Flow 引擎（Camunda/Activiti BPMN）驱动，**独立于页面业务规则**：bizflows 是页面事件代码（js/cs），flows 是审批工作流定义（谁审批、怎么流转）。

快照按分组组织：`flows/<分组名>/<流程名>/`（纯中文名；同名撞车时追加完整 id），顶层 `flows/README.md` 是分组索引（目录 | 版本 | 状态 | 关联页面 | 文件）。

## meta.json 关键字段

| 字段 | 语义 |
|------|------|
| `id` | 流程 id（32 位），平台侧关联键 |
| `name` / `key` | 流程名 / 流程定义 key |
| `actReProcdefId` / `actReProcdefIdRev` | 流程定义 `key:版本:部署id` / 版本号（流程是平台唯一带版本号的资源） |
| `pcPageKey` | **关联页面的 OutId（页面 id，非 route）**——页面目录的权威定位是页面 `bindings.md` 的「审批流程」节；flows/README 的「关联页面」列已反查为 route，反查不到标注「本应用外」 |
| `groupId` / `groupName` | 分组归属 |
| `state` | 状态（1=启用） |

## process.xml（BPMN 2.0 原文）

| BPMN 元素 | 语义 |
|-----------|------|
| `startEvent` / `endEvent` | 开始 / 结束 |
| `userTask` | 审批节点：`name`=节点名；`activiti:assignee`=审批人表达式（`${initiator}` 发起人、`${assignee}` 会签变量、`${scriptServiceImpl.getUser…}` 脚本解析） |
| `sequenceFlow` | 连线（`sourceRef`→`targetRef`）；内嵌 `conditionExpression` 是分支条件 |
| `inclusiveGateway` | 条件网关（分支/汇聚） |
| `multiInstanceLoopCharacteristics` | 会签（`isSequential="false"` 为多实例并行会签） |

## ext.json（节点级配置，四节）

| 节 | 内容 |
|----|------|
| `processDefinition` | 流程级：消息推送开关（到达/超时/催办/驳回/结束/作废）、跳转规则 |
| `userTask[]` | 节点配置（`activityId` 对应 process.xml 的节点 id `task-xxx`） |
| `callActivityTask` | 子流程调用节点 |
| `sequenceFlow` | 连线扩展配置 |

`userTask[]` 单项三块：

- `baseInfo`：`taskName` 节点名、`assignee` 审批人（如 `"QAManager"`；`performerType="vars"` 表示它是流程变量名，运行时解析）、`isCounterSignNode` 会签标记、`performerCategory`
- `buttonSetting`：该节点可用按钮（approve 同意 / cancel 作废 / returnsBack 驳回 / 加签…）
- `senior`：跳过策略（`samePrevActSkip` 等）、推送开关

## 典型查询路径

1. **页面 → 审批链路（双向关联）**：页面 `bindings.md` 的「审批流程」节直接列出关联流程与快照内目录（关联键 = 流程 pcPageKey = 页面 OutId）；或 flows/README.md「关联页面」列（route）反查
2. **某节点谁审批**：ext.json `userTask[].baseInfo`（assignee + performerType）
3. **条件分支怎么走**：process.xml 里 `sequenceFlow` 的 `conditionExpression`
4. **流程版本**：meta.json `actReProcdefIdRev`（README 索引同列）

## 与页面的关系

- 流程绑定页面的权威键：流程 meta.json 的 `pcPageKey` = 页面 OutId（loadTreeList 节点的 OutId，**不是 route**——route 是 qms_capaapplication 这类语义名，OutId 是 32 位随机串）
- 页面上的 `ProcessButton`（流程按钮）/ `GxpProcessCenter`（流程中心）组件负责发起与审批交互；按钮配置在 page.json 组件的 `x-component-props.webbuttonConfig`（action 类型：initiate 发起 / approve / returnsBack / cancel…）
- 页面目录下的 `bizflows/` 子目录是**该页面的业务规则**，与快照根的 `flows/`（审批流程）无关，别混淆
