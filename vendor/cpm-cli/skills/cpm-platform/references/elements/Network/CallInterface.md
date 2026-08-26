> 来源：action-design-tools/nodes/Network/CallInterface/knowledge.md（同步于 2026-08-25）

# 调用接口

> 元件 Key: `CallInterface`

## 适用场景
调用外部 REST API 或系统内部接口，返回请求结果。支持 GET/POST/PUT/DELETE，支持 headers/query/path/body 参数。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `apiInfo`（输入，必填） | 接口配置对象 `{setting, headers, queryParams, pathParams, bodyParams}` | **半固定**：见下方子表。`setting.id` 从接口配置取，参数定义从接口详情取；各参数桶的值是表达式对象 | 结构固定，id/参数定义取自配置 |
| `requestResult`（输出，必填） | 请求结果变量名。键名固定 `requestResult` | **灵活**：变量名自己起；值为表达式对象 `paramTypes:"custom"`，`dataType:"object"` | 自定义 |

> `requestResult` 产出局部变量，下游引用用 `paramTypes:"localVariable"`。

### apiInfo 各子项

| 子项 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `setting` | 接口基本信息 `{id, name, url, method}` | **固定**：除 `id`(从接口配置取)外，`name`/`url`/`method` 由 expand 层按 id 自动补全，**不要手写** | id 取自配置，其余平台填 |
| `headers` | 请求头，每项值为表达式对象 | **半固定**：key 从接口详情的入参定义取，值灵活 | 键名取自配置，值灵活 |
| `queryParams` | URL 查询参数，每项值为表达式对象 | 同 headers | 同上 |
| `pathParams` | URL 路径参数（{id} 占位），每项值为表达式对象 | 同 headers | 同上 |
| `bodyParams` | 请求体，每项值为表达式对象 | 同 headers | 同上 |

#### apiInfo 结构
```jsonc
{
  "setting": {                          // 接口基本信息
    "id": "接口id",                      // 从接口配置获取
    "name": "接口名",
    "url": "/api/xxx",                   // 请求地址（含 {pathParam} 占位符）
    "method": "POST"                     // GET/POST/PUT/DELETE
  },
  "headers": {                          // 请求头（每项值为表达式对象）
    "Authorization": { "paramTypes": "custom", "code": "'Bearer ' + inbiz.userInfo.token", "label": "...", "dataType": "string" }
  },
  "queryParams": {                       // URL 查询参数（每项值为表达式对象）
    "page": { "paramTypes": "custom", "code": "1", "label": "1", "dataType": "number" }
  },
  "pathParams": {                        // URL 路径参数 {id}（每项值为表达式对象）
    "id": { "paramTypes": "componentsVariable", "code": "inbiz.queryData.recordId", "label": "记录ID", "dataType": "string" }
  },
  "bodyParams": {                        // 请求体（每项值为表达式对象）
    "name": { "paramTypes": "componentsVariable", "code": "inbiz('EformInput').value", "label": "输入框", "dataType": "string" }
  }
}
```

### 输出参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| requestResult | object | 否 | **true**（表达式对象） | 请求结果变量名（paramTypes:custom，code 为变量名） |

## 参数示例（addNode 完整调用）
```json
{
  "elementKey": "CallInterface",
  "params": {
    "inputs": {
      "apiInfo": {
        "setting": { "id": "xxx", "url": "/api/orders", "method": "POST" },
        "bodyParams": {
          "amount": { "paramTypes": "componentsVariable", "code": "inbiz('EformNumber').value", "label": "金额", "dataType": "number" }
        }
      }
    },
    "outputs": {
      "requestResult": { "paramTypes": "custom", "code": "result", "label": "result", "dataType": "object" }
    }
  }
}
```

## JS 表达式写法（code 字段）
- headers/query/path/body 每项的 code 可填：
  - 组件值：`inbiz('EformInput').value`
  - 全局变量：`self.globalVariables['amount']`
  - 当前用户：`inbiz.userInfo.guid`、`inbiz.userInfo.token`
  - 字面量：`1`、`"待审"`、`true`
  - 表达式：`'Bearer ' + inbiz.userInfo.token`

## 使用示例
```
用户："调用审批接口，把当前用户ID传进去"
→ 先从接口配置找到接口id，再看接口详情获取参数定义
→ addNode(CallInterface, apiInfo={setting:{id:"xxx", method:"POST"}, bodyParams:{userId:{paramTypes:systemVariable, code:"inbiz.userInfo.guid"}}})
```

## 注意事项
- 接口 id 必须从接口配置获取，参数定义从接口详情获取
- 每个子参数值都必须是表达式对象，不能填裸字符串
- requestResult 用 paramTypes:custom，code 为结果变量名
- 接口异常会被捕获到外层 Try-Catch（若有）

## 自动补全（expand 层）
本元件支持 expand 自动补全，模型**只需给设计意图字段**，以下壳字段由工具自动补全，**不要手写**：
- `apiInfo.setting` 整块（除 id 外的 name/code/requestType/requestUrl/requestBody/responseBody 等——按接口 id 查接口详情补全）
- 各参数桶（headers/queryParams/pathParams/bodyParams/bodyFormData）的 key 集合（按接口参数定义补全）
- `rawBodyContent`（补空串）
模型给：`apiInfo.setting.id`(接口 id) + 各桶的 `{参数名: 值表达式}`。
