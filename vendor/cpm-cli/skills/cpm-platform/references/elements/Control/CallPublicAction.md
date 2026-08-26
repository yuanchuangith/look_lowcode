> 来源：action-design-tools/nodes/Control/CallPublicAction/knowledge.md（同步于 2026-08-25）

# 调用公共动作

> 元件 Key: `CallPublicAction`

## 适用场景
调用系统中已配置的全局公共动作（跨页面共享的可复用逻辑单元），可传递动态实参并绑定返回值。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `actionName`（输入，必填） | 公共动作选择，完整元数据对象 `{id, code, label, name, controlCode, ...}` | **固定**：从 `getActionList` 取；`label`/`name`(中文名)是设计意图，其余为平台元数据，**不要手写** | 固定结构，取自工具 |
| `param_<形参名>`（输入，可选） | 动态实参，键名为 GUID(平台生成) | **半固定**：值为表达式对象且**必须带 `paramName`(对应公共动作形参名)**；paramName/paramTypes/code 从 `getActionDetail` 取 | 键名平台生成，paramName 取自工具 |
| `_dynamicOutput`（输出，可选） | 公共动作返回值绑定 | **灵活**：按被调动作 outputParams 定义绑定变量名；值为表达式对象 | 自定义 |

> 形参清单从 `getActionDetail` 取（同 CallAction）。输出为局部变量。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| actionName | object | 是 | 公共动作引用 `{value(动作id), label, ...}`，从 getActionList 取 |
| param_<参数名> | object | 否 | 【动态实参】每个被调动作的形参一个键，键名为 `param_<形参名>`，值为表达式对象。形参名从公共动作定义获取 |

### 输出参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| param_<返回名> | object | 否 | 【动态返回绑定】按公共动作返回参数绑定变量名 |

## 使用示例
```
调用公共动作("发送通知", 参数=[userId=局部变量-creatorId, content=输入参数-msg])
```

## 注意事项
- 调用前需确保目标公共动作已在系统中配置
- 公共动作可跨页面调用，与子动作（仅限当前页面）不同
- 动态实参键名用 `param_<形参名>`（语义化），形参名从公共动作定义获取

## 自动补全（expand 层）
本元件支持 expand 自动补全，模型**只需给设计意图字段**，以下壳字段由工具自动补全，**不要手写**：
- 动态实参/返回值的 GUID 键（模型用 `param_<参数名>` 语义键，expand 补随机 GUID 键）
- 实参/返回值表达式对象缺失的 `value`/`dataType`
模型给：`actionName` + `param_<参数名>`(每个实参的值表达式) + 输出绑定（若有返回值）。
