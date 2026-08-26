> 来源：schema-tools/components/EformMemberSelect/knowledge.md（同步于 2026-08-25）

# 成员选择

> 组件 Key: `EformMemberSelect`

## 适用场景

在表单中选择组织架构中的成员，支持机构、部门、职位、用户、角色和自定义成员（默认 5 种 tab 自动注入，无需配置）。提供搜索输入和组织架构弹窗两种选择方式。
与 TreeSelect 区别：专门针对组织架构成员，内置搜索、弹窗、跨公司选择等功能。

## 属性

> 大多数参数都有合理默认值，**只需设置下表「关键参数」**，其余不传即可。
> 公共属性（label、name、display、pattern、required）由系统自动注入。

### 关键参数（设计时需考虑）

| 名称 | 类型 | 默认值 | 何时设置 |
|------|------|--------|----------|
| multiple | `boolean` | `false` | 多选成员时设 `true` |
| collectivization | `boolean` | `false` | 需要跨公司选择时设 `true` |
| memberTypes | `string[]` | 全部可选 | 限制可选成员类型时设，如 `['user']` 只能选用户、`['user','department']` 可选用户和部门。工具据此自动隐藏其他类型，无需手写 tabs。取值：`institution`/`department`/`position`/`user`/`role`/`custom` |
| defaultValueType | `'department' \| 'position' \| 'user' \| 'role' \| 'institution' \| 'custom' \| 'variable'` | | 需要预填默认值时设（如 `user` 预填当前用户） |

### 其余参数（有默认值，无明确需求不用设）

| 名称 | 默认值 | 说明 |
|------|--------|------|
| placeholder / modalTitle / pageSize / multipleMaxHeight / allowClear | 平台默认值 | 交互外观类，通常不用动 |
| departments / roles / departmentFilteringRules / roleFilteringRules | 空 / `'selected'` | 候选范围过滤；需限定可选部门/角色范围时设 |
| childModelConfig / storageConfig | `false` | 选中数据存子表时启用 |
| auditMatrixConfig | | 审核矩阵场景 |
| readOnly / disabled | `false` | 状态控制 |

> 业务过滤属性（collectivization、departments、roles 等）运行时位于独立的 `x-component-biz-props` 容器，工具会自动写入正确分层，按上表参数名传入即可。

## 复杂类型定义

### StorageConfig

```typescript
interface StorageConfig {
  business: string;              // 业务模型标识
  tableData: {                   // 字段映射配置
    componentAttr: string;
    modelAttr: string;
  }[];
}
```

### AuditMatrixConfig

```typescript
interface AuditMatrixConfig {
  id: string;
  auditType: string;            // '1' 或 '2' 时启用审核矩阵模式
  isMultiple: boolean;
  memberSelectData: any[];
}
```

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 选中值以数组存储（schema `type` 为 `Array`），字段绑定类型为 `string`：选中成员以 JSON 字符串形式存入，包含成员完整信息。
- 默认 5 种成员类型（用户/部门/职位/角色/自定义）自动注入，含机构时为 6 种，**通常无需配置 tabs**。
- 搜索输入有 300ms 防抖。
- collectivization=true 时可跨公司选择成员。
- childModelConfig=true 时需配合 storageConfig 指定子表存储。
