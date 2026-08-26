> 来源：action-design-tools/nodes/Database/SelectOrgData/knowledge.md（同步于 2026-08-25）

# 查询组织数据

> 元件 Key: `SelectOrgData`

## 适用场景
按组织关系查询数据：例如查询某个岗位下的所有用户、查询用户本身等。返回结果数组，常配合 ForEachArray 遍历。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `config`（输入，必填） | 组织查询设置 `{panel, queryType, ids, isContainChild}` | **半固定**：见下方子结构 | 结构固定 |
| `config.queryType` | 查询关系字面量 | **固定**：如 `positionToUser`=岗位下用户、`user`=用户本身。决定 panel 的取值 | 固定枚举 |
| `config.panel` | 面板标识字面量 | **固定**：随 queryType 固定（平台约定） | 固定值 |
| `config.ids` | 查询起点 id，表达式对象 | **灵活**：组织/岗位 id 变量 | 灵活 |
| `config.isContainChild` | 是否包含下级布尔字面量 | **灵活**：true/false | 灵活 |
| `variableName`（输出，必填） | 查询结果变量名 | **灵活**：变量名自己起；值为表达式对象，值为结果数组 | 自定义 |

> 输出为数组局部变量，常配合 ForEachArray 遍历，下游引用用 `paramTypes:"localVariable"`。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| querySettings | object | 是 | false（结构对象） | 组织查询设置（见下） |

#### querySettings 结构
```jsonc
{
  "panel": "position",        // 面板标识，随 queryType 固定（positionToUser→position，user→user）
  "queryType": "positionToUser", // 查询关系，见枚举
  "ids": {                      // 查询起点 id（表达式对象）
    "paramTypes": "localVariable", "value": "...", "code": "idDeptMasterPosition", "label": "...", "dataType": "any"
  },
  "isContainChild": false       // 是否包含下级
}
```

**queryType 取值（真实数据已见）**
| queryType | 含义 | panel |
|-----------|------|-------|
| `positionToUser` | 查询岗位下的用户 | position |
| `user` | 查询用户本身 | user |

### 输出参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| queryResults | object | 是 | true | 结果变量名（paramTypes:custom），值为数组 |

## 参数示例
```json
{
  "elementKey": "SelectOrgData",
  "params": {
    "inputs": {
      "querySettings": {
        "panel": "position",
        "queryType": "positionToUser",
        "ids": { "paramTypes": "localVariable", "value": "localVariable-idDeptMasterPosition", "code": "idDeptMasterPosition", "label": "局部变量-idDeptMasterPosition", "dataType": "any" },
        "isContainChild": false
      }
    },
    "outputs": { "queryResults": { "paramTypes": "custom", "code": "master_position_user_data", "label": "master_position_user_data", "dataType": "array" } }
  }
}
```

## 注意事项
- `queryType` 决定查询什么组织关系，是核心设计意图；`panel` 随 queryType 固定，无需单独考虑。
- `ids` 是查询起点（通常是上游变量/局部变量），用表达式对象填写。
- 结果为数组，常配合 ForEachArray 遍历。
