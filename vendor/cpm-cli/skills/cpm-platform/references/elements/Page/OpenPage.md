> 来源：action-design-tools/nodes/Page/OpenPage/knowledge.md（同步于 2026-08-25）

# 打开页面

> 元件 Key: `OpenPage`

## 适用场景
在当前应用中导航到指定页面，支持新页签、弹窗、新页面等打开方式，可携带页面参数。

> ⚠️ **页面引用必须用 `getPageList` 查到的真实值，绝不编造。** `pageInfo.value`（真实 GUID）和 `pageIdentifier`（真实标识）都**禁止留空、禁止用页面名拼音/占位符编**（如 `peixunshixiangqing`、`dingdanxiangqing` 这类拼音）。编造值会让伪代码渲染成"打开页面(页面="")"——空页面，运行时必然失效。查不到真值就**留空 + 向用户说明**，等服务可用后用 `getPageList` 重查。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `pageReferenceType`（输入，必填） | 页面引用类型字面量 | **固定**：`page`=按页面选择 / `identifier`=按标识 | 固定枚举 |
| `pageInfo.value`（输入，page 时必填） | 页面 GUID | **固定**：从 `getPageList` 取真实页面 id。查不到→看错误信息(如 appId 为空去捞 appId)重试→真没有就**留空+向用户说明**，**禁止用页面名拼音/占位符编** | 固定值，取自工具 |
| `pageIdentifier`（输入，identifier 时必填） | 页面标识字面量 | **固定**：从 `getPageList` 或用户提供的标识取真实值。**禁止拼音编造**（如 `peixunshixiugai`） | 固定值，取自工具 |
| `openType`（输入，可选） | 打开方式字面量 | **固定**：`tab`=新页签 / `modal`=弹窗 / `newPage`=新页面 | 固定枚举 |
| `pageParameter`（输入，可选） | 页面参数 `{customPageParameter:[{key, value}]}` | **半固定**：key 是参数名；value 是表达式对象(灵活)；`id` 平台自动填 | 结构固定 |

> ⚠️ 两类引用二选一，**pageInfo.value(真实 GUID) 或 pageIdentifier(真实标识) 都绝不能留空或填编造值**。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| pageReferenceType | string | 是 | 页面引用类型：page=按页面选择 / identifier=按标识 |
| pageInfo | object | 否 | 页面信息（pageReferenceType 为 page 时使用，含页面 GUID） |
| pageIdentifier | string | 否 | 页面标识（pageReferenceType 为 identifier 时使用） |
| openType | string | 否 | 打开方式：tab=新页签 / modal=弹窗 / newPage=新页面 |
| pageParameter | object | 否 | 页面参数 {customPageParameter:[{key, value}]} |

## 参数示例
```json
{
  "elementKey": "OpenPage",
  "params": {
    "inputs": {
      "pageReferenceType": "page",
      "pageInfo": { "value": "<页面GUID>", "label": "订单详情" },
      "openType": "tab",
      "pageParameter": { "customPageParameter": [{ "key": "orderId", "value": { "paramTypes": "custom", "code": "123", "label": "123", "dataType": "string" } }] }
    }
  }
}
```

## 使用示例
```
打开页面(页面="订单详情", 方式="新页签", 参数={orderId: "123"})
打开页面(标识="orderDetail", 方式="弹窗")
```

## 自动补全（expand 层）
本元件支持 expand 自动补全，模型**只需给设计意图字段**，以下壳字段由工具自动补全，**不要手写**：
- `pageParameter.customPageParameter[]` 每项的 `id`
- 各参数值表达式对象缺失的 `value`/`dataType`
模型给：`pageReferenceType` + `pageInfo`/`pageIdentifier` + `openType` + `pageParameter.customPageParameter[]{key, value}`。
