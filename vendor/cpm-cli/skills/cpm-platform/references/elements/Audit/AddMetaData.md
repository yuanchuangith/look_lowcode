> 来源：action-design-tools/nodes/Audit/AddMetaData/knowledge.md（同步于 2026-08-25）

# 添加元数据

> 元件 Key: `AddMetaData`

## 适用场景
为流程节点添加键值对元数据（如 fileCode、fileName、reason 等），供后续环节使用。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `paramSettings`（输入，必填） | 元数据配置 `{paramSettings:[]}` | **半固定**：paramSettings 是键值对数组，每项 `{id(平台生成), key(元数据名), value(表达式对象)}` | 结构固定 |
| `paramSettings[].key` | 元数据名（如 fileCode、fileName） | **灵活**：按业务定义的元数据键名 | 灵活 |
| `paramSettings[].value` | 元数据值，表达式对象 | **灵活**：组件值/局部变量/字面量 | 灵活 |

> 无输出参数。`id` 平台自动填，**不要手写**。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| config | object | 是 | false | 元数据配置 {paramSettings:[]}。paramSettings 是键值对数组，每项 {id(平台生成), key(元数据名), value(表达式对象)} |

#### config.paramSettings[] 每项
```jsonc
{ "id": "<平台生成>", "key": "fileCode", "value": { "paramTypes": "localVariable", "code": "fileCode", "label": "局部变量-fileCode", "dataType": "string" } }
```

### 输出参数
无。

## 参数示例
```json
{
  "elementKey": "AddMetaData",
  "params": {
    "inputs": {
      "config": { "paramSettings": [
        { "key": "fileCode", "value": { "paramTypes": "localVariable", "code": "fileCode", "label": "局部变量-fileCode", "dataType": "string" } },
        { "key": "fileName", "value": { "paramTypes": "localVariable", "code": "fileName", "label": "局部变量-fileName", "dataType": "string" } }
      ]}
    }
  }
}
```

## 使用示例
```
添加元数据(配置="fileCode=局部变量-fileCode, fileName=局部变量-fileName")
```

## 注意事项
- `key` 是自定义元数据名（字符串），`value` 是表达式对象。
- **平台自动生成、模型不要手写**：paramSettings 每项的 `id`。
