# 当前会话约束与复核状态

本记录只在当前线程上下文内使用；不保存到项目文件、共享关系库或服务端会话。不要将示例字段固化为业务规则。

## context 接口

diagnose_codex_input(text, at_time?, context?) 接受一个最多32 KiB的 JSON 对象。合法字段为 goal、anchors、rules、exclusions、field_meanings、chosen_approach、findings、corrections。
anchors 最多8项，身份字段 action_code、ref_id、page、group_key、node_key、design_id 都是字符串。只有 action_code/RefId 已确认时才能用于动作复用。规则内容是用户声明，不是数据库已验证事实。

首次调用可以省略 `context`，将用户当前原话放在 `text`。追问复用上次返回结果时，只取 `conversation_context.record` 作为新的 `context`，不要传整个 `conversation_context` 包装对象、完整工具返回值或 `messages/history` 聊天记录。遇到非法字段提示时，按上述八个字段重新整理，保留已有规则、排除项和纠正后重试，不要通过丢弃这些约束绕过校验。

```json
{
  "goal": "本轮复核的目标",
  "anchors": [{"action_code": "ACTION01", "group_key": "group-key", "design_id": "last-read-design"}],
  "rules": [{"statement": "用户确认的无匹配行为", "source": "user"}],
  "exclusions": ["用户明确本轮忽略的功能"],
  "field_meanings": [{"field": "业务字段", "meaning": "最后确认的含义"}],
  "chosen_approach": "用户已选的实现方式",
  "findings": [{"id": "BUG-01", "status": "pending_review", "last_evidence_design": "last-read-design"}],
  "corrections": [{"old": "旧说法", "new": "本轮纠正", "status": "superseded"}]
}
```

## 衔接规则

- 当前消息的明确动作和纠正优先；旧字段含义被替代，不把两个矛盾说法同时执行。
- 短句只有一个有效锚点时直接复核，多个目标返回候选并问一个定位问题。未知的新明确动作编号不要退回旧动作。
- 改了/发布了/再复核：先 compare_designs，再读相关当前设计和节点；旧行号只作查找提示。
- 排除项在用户重新纳入前不再作为问题；换项目、换目标时重新定界，不自动搬运旧规则。
- 用户选择一种实现后，除非证据证明存在缺陷，否则只完善其方案；不要无故往返全局数组、JSON和字符串方案。
- 已有范围限制时，先证明同范围内还能出现冲突，再把缺字段风险升级为缺陷。字段必填缺失应报错时尊重 fail-fast，不默认用空值兜底。
- 生成代码前确认执行端（前端JS/后端C#）、输入栏（JSON默认值/自定义表达式/变量选择器）、类型与空值规则。跨前后端值的类型没有证据时不做后端列表强转。

## 状态与编号

已确认缺陷 BUG-01、条件性风险 RISK-01、可选加固 SUG-01 使用各自稳定编号。已通过没有缺陷编号。用户说解决了记 pending_review，读取对应新设计后记 static_fixed；真实运行证据才记 runtime_verified。
用户说“2、3解决了”先对应上一条回答实际列出的项目；不要把正常项或新章节编号误认成历史缺陷。
撤回误判记 withdrawn，并说明依据；不要为了固定报告格式继续报同一项。

## 证据门禁

输入上下文不替代工具取证；缓存身份不替代当前发布检查；合成场景不替代真实业务运行。参考输出不包含数据库连接信息。

## 输入栏类型示例

先用 get_cpm_knowledge(kind="catalog", name="main", query="变量") 找到本机实际元件和语言主题，再确认元件参数。以下示例仅说明语法类别，不代表当前产品支持该类型。

| 已确认的执行端与输入栏 | 示例 | 前置条件 |
| --- | --- | --- |
| 前端 JS 自定义表达式 | `idsText.split(",").filter(value => value !== "")` | idsText 已确定为字符串；表达式结果是 JS 数组 |
| 后端 C# 自定义表达式 | `idsText.Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries)` | idsText 已确定为非空引用的 string；输出是 string[]；元件接受后端表达式 |
| 字符串变量的 JSON 默认值 | `""` | 输入栏确实按 JSON 解析且声明类型为字符串；这不是 C# 源码栏 |
| 变量选择器 | 在选择器内选择 idsText | 不把声明语句、数组字面量当作变量名称粘贴 |

前后端共享变量先核对实际支持类型及序列化契约；后端局部数组可用不等于共享全局数组可用。空字符串、null、空集合分别处理；保留用户已经明确的必填报错约束，不用默认值掩盖它。字符串集合判断使用拆分后的完整元素比较，不用子串 Contains 代替成员匹配。
