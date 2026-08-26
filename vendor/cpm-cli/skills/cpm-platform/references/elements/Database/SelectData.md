> 来源：action-design-tools/nodes/Database/SelectData/knowledge.md（同步于 2026-08-25）

# 查询数据

> 元件 Key: `SelectData`

## 适用场景
从数据模型或数据集中查询符合条件的数据记录，返回数组。常配合 ForEachArray 遍历处理。

## 两种使用方式（由 dataType 判别，真实数据两套字段完全互斥）

SelectData 通过 `dataType` 区分两种使用方式，模型只需选用其一：

| 使用方式 | 何时用 | 关键入参 | dataType |
|---------|--------|---------|----------|
| **查询模型** | 按数据模型查询，最常见（生产数据约半数走这条） | `modelName` + `whereConditions`（单层直接挂入参）或 `modelName` + `selectDataConfig` | 不传或非 `"dataSet"` |
| **查询数据集** | 数据源是数据集（视图/列表），需分页 | `dataType:"dataSet"` + `dataSetName` + `pageIndex` + `pageSize` + `whereConditions`（双层包裹） | `"dataSet"` |

> 查询模型是两种方式里更常见的。两套字段完全互斥：给了 `modelName` 就不要 `dataType/dataSetName/pageIndex/pageSize`，反之亦然。
> 平台壳字段（`modelId`/`group`、`Id`/`id` GUID、`queryField` 等）运行时由平台补全，校验不强制——你只需保证设计意图字段正确。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 | 适用方式 |
|------|--------|----------|------|---------|
| `modelName` | 数据模型信息对象 | **固定**：从 `getModelList` 取，关注 `modelComment`(中文名)/`modelName`(英文表名)；需查字段用 `getModelDetail`。查不到→留空+说明，禁止猜 | 固定结构，取自工具 | 查询模型 |
| `selectDataConfig` | 配置包 `{whereConditions, sort}` | **半固定**：whereConditions 用数据库 Filter 形状（见下），sort 为排序数组 | 结构固定，内容灵活 | 查询模型（需排序时） |
| `whereConditions`（查询模型直接挂入参） | 查询条件 `{Logic, Filters:[{Field,Operator,ParamInput}]}`（单层） | **半固定**：`Field` 是数据库字段名(裸列名，从 `getModelDetail` 取)；`Operator` 固定枚举；`ParamInput` 是表达式对象 | 结构固定，Field 取自工具 | 查询模型 |
| `dataType` | 固定字面量 `"dataSet"` | **固定**：出现即走数据集方式 | 固定值 | 查询数据集 |
| `dataSetName` | 数据集信息对象 | **半固定**：`dataSetName`(中文名) 与 `modelname`(英文表名) 是设计意图，**你应提供**（modelname 与底层模型表名一致）；`value`/`selectedGroup`(GUID)、`primaryKey`、`queryField` 平台自动填，不要手写 | 中文名/表名提供，其余平台填 | 查询数据集 |
| `pageIndex`/`pageSize` | 页码/条数 | **灵活**：数字或表达式对象，默认 1/40 | 灵活 | 查询数据集 |
| `whereConditions`（查询数据集） | 查询条件（双层包裹）`{whereConditions:{Logic,Filters:[{Field,Operator,ParamInput}]}, sort:[]}` | **半固定**：`Field` 是数据库字段名(`表.列`，从 `getModelDetail`/`getDataSetDetail` 取)；外层 `id`、`Filters[].Id`、`sort[].id` 平台自动填 | 结构固定，Field 取自工具 | 查询数据集 |
| `rows`（输出，必填） | 查询结果变量名绑定。键名固定 `rows` | **灵活**：变量名自己起（数组类型，有语义、不重复）；值为表达式对象 `paramTypes:"custom"`，`value`/`code`/`label` 填变量名 | 自定义 | 两种方式 |

> `rows` 产出的是局部变量，下游引用用 `paramTypes:"localVariable"`（见 prompt.md「变量与作用域」）。常配合 ForEachArray 遍历。

## 参数说明

### 输入参数（按使用方式分组）

**通用**
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| rows（出参） | object | 是 | true | 查询结果变量名，paramTypes:custom |

**查询模型**
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| modelName | object | 是 | true | 数据模型（从 getModelList 选择，关注 modelComment/modelName） |
| selectDataConfig | object | 否 | false | 需排序时的配置包：`{whereConditions:{Logic,Filters}, sort:[]}` |
| whereConditions | object | 否 | true | 直接查询条件（单层） |

**查询数据集**
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| dataType | string | 是 | false | 固定 `"dataSet"`（出现即走数据集方式） |
| dataSetName | object | 是 | true | 数据集信息，关注 `dataSetName`(中文名) 与 `modelname`(表名) |
| pageIndex | number | 否 | true | 页码，默认 1 |
| pageSize | number | 否 | true | 每页条数，默认 40 |

## 条件结构（whereConditions / selectDataConfig.whereConditions）

> ⚠️ 数据库 Filter 形状（两种方式都用这一种）：

**查询模型 / 查询数据集都用这一种**（数据库 Filter 形状）：
```jsonc
{
  "Logic": "And",            // And | Or，支持递归嵌套（Filters 项可再为 {Logic, Filters}）
  "Filters": [
    {
      "Field": "表.字段",     // ⚠️ 查询模型用裸列名（如 "status"），查询数据集用"表名.列名"（如 "表.change_detail_id"）
      "Operator": "Equal",   // Equal/NotEqual/GreaterThan/.../Contains/Any
      "ParamInput": {        // 比较值（表达式对象）
        "paramTypes": "custom", "code": "'待审'", "label": "待审", "dataType": "string"
      },
      "value": "..."         // 代码形态的值（平台填）
    }
  ]
}
```

查询数据集的 whereConditions 多一层包裹：`{ whereConditions: {id,Logic,Filters}, sort: [] }`（内层根用小写 `id`，查询模型根用大写 `Id`——平台自动填，不要手写）。

> 注：IfCondition/WhileLoop 用的是另一种 `{target, equalTo, value}` 形状，不要混用。

### ParamInput 常见写法

```jsonc
// ① 字面量（自定义值）
"ParamInput": { "paramTypes": "custom", "code": "'待审'", "label": "待审", "dataType": "string" }

// ② 字典值（从 getDictionaryDetail 取现成引用对象，paramTypes 固定 dictionaryVariable）
"ParamInput": { "paramTypes": "dictionaryVariable", "value": "5dce9227-...-DocumentChange", "code": "\"DocumentChange\"", "label": "数据字典-Dms流程类型-...", "dataType": "string" }

// ③ 系统变量
"ParamInput": { "paramTypes": "systemVariable", "value": "OrgId", "code": "this.orgId", "label": "系统变量-机构ID", "dataType": "string" }

// ④ 入参引用
"ParamInput": { "paramTypes": "inputParam", "value": "param-orgId", "code": "orgId", "paramName": "orgId", "label": "机构ID", "dataType": "string" }

// ⑤ 局部变量（上游元件输出）
"ParamInput": { "paramTypes": "localVariable", "value": "localVariable-firstGroupId", "code": "firstGroupId", "label": "局部变量-firstGroupId", "dataType": "string" }
```

## 参数示例

### 查询模型：modelName + 直接条件
```json
{
  "elementKey": "SelectData",
  "params": {
    "inputs": {
      "modelName": { "modelComment": "订单", "modelName": "order", "modelId": "...", "group": "..." },
      "whereConditions": {
        "Logic": "And",
        "Filters": [{ "Field": "order.status", "Operator": "Equal", "ParamInput": { "paramTypes": "custom", "code": "'待审'", "label": "待审", "dataType": "string" } }]
      }
    },
    "outputs": { "rows": { "paramTypes": "custom", "code": "orderList", "label": "orderList", "dataType": "array" } }
  }
}
```

### 查询数据集：dataType:"dataSet" + dataSetName
```json
{
  "elementKey": "SelectData",
  "params": {
    "inputs": {
      "dataType": "dataSet",
      "dataSetName": { "dataSetName": "文件流程效期清单", "modelname": "gxp_dms_document_period_of_validity_list", "value": "<GUID>", "primaryKey": "id", "selectedGroup": "<GUID>", "queryField": [] },
      "pageIndex": { "paramTypes": "custom", "code": "1", "label": "1", "dataType": "number" },
      "pageSize": { "paramTypes": "custom", "code": "40", "label": "40", "dataType": "number" },
      "whereConditions": { "whereConditions": { "Logic": "And", "Filters": [] }, "sort": [] }
    },
    "outputs": { "rows": { "paramTypes": "custom", "code": "rows", "label": "rows", "dataType": "array" } }
  }
}
```

## 注意事项
- 查询模型：从 `getModelList` 获取模型，字段名从 `getModelDetail` 获取。
- 查询数据集：从 `getDataSetList` 获取数据集，字段名从 `getDataSetDetail` 获取。
- 查询结果为数组，通常配合 ForEachArray 遍历（item 即每条记录）。
- **平台自动生成、模型不要手写**：
  - `dataSetName.value/selectedGroup/queryField[]`（GUID / 字段元数据）
  - `modelName.modelId/group`（GUID）
  - `selectDataConfig.whereConditions.Id`（模型方式条件树根标识，大写 Id）
  - `whereConditions.whereConditions.id`（数据集方式条件树根标识，小写 id）
  - 每条 Filter 的 `Id`（GUID）、`value` 字段
- whereConditions 的 Field 是数据库字段名（查询模型用裸列名，查询数据集用 `表.列`），不是组件引用。
