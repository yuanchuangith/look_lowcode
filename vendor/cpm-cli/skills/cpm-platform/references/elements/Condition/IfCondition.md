> 来源：action-design-tools/nodes/Condition/IfCondition/knowledge.md（同步于 2026-08-25）

# IF 条件判断

> 元件 Key: `IfCondition`

## 适用场景
需要根据条件判断执行不同逻辑时使用。支持多条件 AND/OR 组合、嵌套子条件。配合 ElseIf/Else 实现多分支。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `condition`（输入，必填） | 条件树 `{Logic, Filters:[...]}`，递归结构（Filters 项可为叶子 `{target,equalTo,value}`，也可为子组 `{Logic,Filters}`） | **结构固定**：Logic 固定取 `And`/`Or`；Filters 是数组。容器形状钉死，内容随条件填 | 半固定（结构固定、内容灵活） |
| `Filters[].target` | 左操作数，**表达式对象** `{paramTypes,value,label,code,dataType,objectAttribute?}` | **固定**：**比较单值组件值优先取 `getPageComponents` 返回的 `valueRef`（code 自带 `.value`，别拿组件对象 ref 去 .value 或漏 .value）**；表格/容器类无 valueRef，取值用 ComponentMethod（getData/getSelectedRows）；上游局部变量取 `paramTypes:"localVariable"` 的引用对象。**字段名别凭显示文本猜** | 固定结构，取自工具 |
| `Filters[].equalTo` | 比较运算符枚举（PascalCase） | **固定枚举**：`Equal`/`NotEqual`/`GreaterThan`/`GreaterThanOrEqual`/`LessThan`/`LessThanOrEqual`/`Contains`/`NotContains`/`EqualNull`/`NotEqualNull` | 固定枚举 |
| `Filters[].value` | 右操作数，**表达式对象** `{paramTypes,value,label,code,dataType}` | **灵活**：字面量用 `paramTypes:"custom"`；字典值用 `paramTypes:"dictionaryVariable"`；组件引用/上游局部变量同 target 取法 | 灵活（模型自定义） |

> 无输出参数。IF 块的“输出”是控制流（进入或不进入块体），不是变量。

## condition 完整结构
```jsonc
{
  "Logic": "And",              // 多条件连接：And / Or
  "Filters": [
    {
      "target": {              // 左操作数（表达式对象）
        "paramTypes": "componentsVariable",
        "value": "EformNumber-value",
        "code": "inbiz('EformNumber').value",
        "label": "数字框",
        "dataType": "number"
      },
      "equalTo": "GreaterThan", // 比较运算符枚举
      "value": {               // 右操作数（表达式对象）
        "paramTypes": "custom",
        "value": "100",
        "code": "100",
        "label": "100",
        "dataType": "number"
      }
    }
  ]
}
```

### equalTo 运算符枚举
`Equal`(==) / `NotEqual`(!=) / `GreaterThan`(>) / `GreaterThanOrEqual`(>=) / `LessThan`(<) / `LessThanOrEqual`(<=) / `Contains`(包含) / `NotContains`(不包含) / `EqualNull`(为空) / `NotEqualNull`(不为空)

### 嵌套子条件
Filter 数组项既可以是叶子 `{target, equalTo, value}`，也可以是**子组 `{Logic, Filters}`**，从而递归形成 AND/OR 嵌套树：

```jsonc
{
  "Logic": "And",
  "Filters": [
    { "target": {...}, "equalTo": "Equal", "value": {...} },   // 叶子
    {                                                          // 子组：本组内 OR
      "Logic": "Or",
      "Filters": [
        { "target": {...}, "equalTo": "Equal", "value": {...} },
        { "target": {...}, "equalTo": "Equal", "value": {...} }
      ]
    }
  ]
}
```

### 取属性的特殊写法（objectAttribute）
引用上游局部变量**取属性**（如数组 `.Count`、对象 `.id`）时，**优先用 `objectAttribute` 字段**，不要把 `.xxx` 硬拼进 `code`。真实数据（取局部变量 `checkItems` 的 `.Count`）：

```json
"target": {
  "paramTypes": "localVariable",
  "value": "localVariable-checkItems-attribute",
  "label": "局部变量-checkItems.Count",
  "code": "(checkItems).Count",
  "objectAttribute": ".Count",
  "dataType": "any"
}
```

注意：
- 取属性 → `value` 为 `localVariable-{变量名}-attribute`，带 `-attribute` 后缀，且配 `objectAttribute`。
- 不取属性 → `value` 为 `localVariable-{变量名}`，无后缀，无 `objectAttribute`。
- ⚠️ **数组下标不属于 objectAttribute**：`objectAttribute` 只能取 `.属性`（如 `.length`、`.id`、`.Count`），**不要**用它取 `selectedRows[0].id` 这类带 `[下标]` 的写法，也没有 `[0].id` 这种模板。取数组元素属性时，**直接用 `paramTypes:"custom"` 写 code**：
```json
✗ 错误：套 -attribute 后缀 + objectAttribute:"[0].id"（自创写法，运行时取不到值）
  "value": { "paramTypes":"localVariable", "value":"localVariable-selectedRows-attribute", "code":"(selectedRows)[0].id", "objectAttribute":"[0].id" }
✓ 正确：用 custom 写字面量表达式
  "value": { "paramTypes":"custom", "value":"selectedRows[0].id", "code":"selectedRows[0].id", "label":"selectedRows[0].id", "dataType":"any" }
```

## 参数示例（addNode 完整调用）
```json
{
  "elementKey": "IfCondition",
  "params": {
    "inputs": {
      "condition": {
        "Logic": "And",
        "Filters": [
          {
            "target": { "paramTypes": "componentsVariable", "value": "EformNumber-value", "code": "inbiz('EformNumber').value", "label": "数字框", "dataType": "number" },
            "equalTo": "GreaterThan",
            "value": { "paramTypes": "custom", "value": "100", "code": "100", "label": "100", "dataType": "number" }
          }
        ]
      }
    }
  }
}
```

## JS 表达式写法（code 字段）
target/value 的 code 可用：
- 组件值：`inbiz('组件id').value`（单值表单字段类——**直接用 getPageComponents 返回的 valueRef**，不要自己加 .value）
- 全局变量：`self.globalVariables['变量名']`
- 表单字段：`relatedAttributes.GetFormData('字段名')`
- 当前用户ID：`inbiz.userInfo.guid`
- 自定义字面量：直接写值（如 `100`、`"待审"`、`true`）

不确定可用 code 时取现成引用对象：组件对象从 getPageComponents.ref（调方法/设事件用）、**组件值从 getPageComponents.valueRef（比较/赋值/传参用）**、输入/输出参数从 getActionDetail.inputParamRefs/outputParamRefs、字典从 getDictionaryList 选分组→getDictionaryDetail 查字典项。

## 使用示例
```
用户："金额大于1000并且状态是待审就往下走"
→ addNode(IfCondition, condition={Logic:And, Filters:[{target:金额, equalTo:GreaterThan, value:1000}, {target:状态, equalTo:Equal, value:"待审"}]})
```
伪代码：
```
IF (金额 > 1000 AND 状态 == 待审) {
  ...
}
```

## 注意事项
- **IF 块需用 `addNode(IfEnd)` 显式关闭**：块头 IfCondition 不再自动生成结束标记。必须像写代码一样「开 IF → 写块内 → IfEnd 关块」，每个 IfCondition 都要有对应的 IfEnd。漏关会让后续节点全困在块内、层级错乱（伪代码缺 `}` 就是没关）。
- 多分支用 ElseIf（带 condition）和 Else（不带 condition），均在 IfCondition 之后、IfEnd 之前；IF...ELSEIF...ELSE 共用一个 IfEnd 收尾。
- 条件支持 AND/OR 嵌套组合
- target 和 value 都必须是表达式对象，不能填裸字符串
- **target 字段名从对应工具取现成引用对象**（组件/列→getPageComponents；上游局部变量→paramTypes:"localVariable"），字段名别凭显示文本猜
- ⚠️ **作用域**：块头 condition 里引用的变量，必须在 IF 块**外层已定义**——不能引用 IF 块**内**才定义的局部变量（作用域见 prompt.md「变量与作用域」）：
  - ✗ `IF (selectedRows.length == 1) { selectedRows = 组件方法(getSelectedRows) }`（selectedRows 在块内才赋值，块头读不到）
  - ✓ `selectedRows = 组件方法(getSelectedRows); IF (selectedRows.length == 1) { ... }`（先在块外取值，块头才能引用）
