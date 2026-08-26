> 来源：action-design-tools/nodes/DataProcessing/GenerateStrategyCode/knowledge.md（同步于 2026-08-25）

# 生成策略编号

> 元件 Key: `GenerateStrategyCode`

## 适用场景
根据编号源和编号策略自动生成编号（如单据编号、流水号、文件变更号等）。

## 两种形态

| 形态 | 何时用 | 关键入参 |
|------|--------|---------|
| ① 编号源 + 策略引用 | 按编号源驱动，引用策略 | `codeStrategySource` + `codeStrategyDesign` + `codeStrategyContext` |
| ② 策略对象 + 规则 | 直接选编号策略（**真实数据中最常见**） | `codeStrategy` + `rule-<策略编码>` |

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 | 形态 |
|------|--------|----------|------|------|
| `codeStrategySource`（输入，可选） | 编号源 `{id, label, name}` | **固定**：`label`/`name` 是设计意图，`id` 平台派生。从编号源配置取 | 固定结构 | ① |
| `codeStrategyDesign`（输入，可选） | 编号策略引用，表达式对象 | **固定**：从编号策略配置取策略引用 | 固定结构 | ① |
| `codeStrategyContext`（输入，可选） | 策略上下文，表达式对象 | **灵活**：按业务填 | 灵活 | ① |
| `codeStrategy`（输入，可选） | 编号策略对象 `{id, label, code, name, strategy, rule, ...}` | **固定**：从编号策略配置取，`label`(策略名) 是设计意图；`strategy`/`rule`/`status` 等为平台策略元数据，**不要手写** | 固定结构 | ② |
| `rule-<策略编码>`（输入，动态键） | 该策略的规则描述文本 | **半固定**：键名 `rule-` + 策略的 `code` 字段（如 `rule-041DDF56`）；值为规则文本，取自策略的 `rule` 字段 | 键名固定，值取自策略 | ② |
| `requestResult`（输出，必填） | 生成的编号结果变量名 | **灵活**：变量名自己起；值为表达式对象。**注意真实数据中可用 `paramTypes:"outputParam"` 绑定到动作输出参数** | 自定义 | ①② |

> 编号策略的 id/code **必须从编号策略配置取真实值**，禁止照搬示例或凭名称猜。

### 真实数据样本（形态②：选"文件变更号"策略）
```json
{
  "elementKey": "GenerateStrategyCode",
  "params": {
    "inputs": {
      "codeStrategy": {
        "id": "6de50ad5ea1c4c0f8e852af7b6aa98ce",
        "label": "文件变更号",
        "code": "041DDF56",
        "name": "文件变更号",
        "status": true,
        "strategy": "[{...}]",
        "rule": "CD-年(4位)月-数字流水号(1位),按【年】重置流水"
      },
      "rule-041DDF56": "CD-年(4位)月-数字流水号(1位),按【年】重置流水"
    },
    "outputs": {
      "requestResult": { "paramTypes": "outputParam", "value": "1DvE3wH3", "dataType": "string", "label": "输出参数-code", "code": "outputParams[\"code\"]" }
    }
  }
}
```
> 注：本样本 `requestResult` 绑定到动作输出参数 `code`（`paramTypes:"outputParam"`），生成的编号作为该动作返回值。也可绑定到普通局部变量（`paramTypes:"custom"`）。

## 使用示例
```
用户："生成文件变更号"
→ 从编号策略配置取"文件变更号"策略的 id/code/label/rule
→ addNode(GenerateStrategyCode, codeStrategy={id,label,code,...}, rule-{code}=rule文本, requestResult=变量名)
```

## 注意事项
- 编号策略的 id/code/rule/strategy **必须从编号策略配置取真实值**，禁止照搬示例或凭名称猜测
- 形态②最常见：给 `codeStrategy`(策略对象) + `rule-<策略code>`(规则文本)
- `codeStrategy.strategy` 是平台生成的 JSON 字符串，**不要手写或修改**
- 有 expand 自动补全：`codeStrategy` 的策略元数据、`rule-*` 会按策略 id 查详情补全，模型只需给策略 id/label 设计意图
