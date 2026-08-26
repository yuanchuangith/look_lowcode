> 来源：schema-tools/components/EformStaticList/knowledge.md（同步于 2026-08-25）

# 静态列表

> 组件 Key: `EformStaticList`

## 适用场景

从预定义选项中选择一个或多个值，数据来源为数据字典。适用于请假类型、审批状态、载体类型等有固定选项的场景。

与动态列表（EformDynamicList）区别：选项固定（数据字典），不从数据库动态查询。
与下拉（showMode=2）区别：showMode=1 为平铺（Radio/Checkbox），showMode=2 为下拉（Select）。

## 属性

> 工具自动补齐平台运行时字段（model/modelend/sourcetype/staticDataList），模型只需提供下方参数。
> 公共属性（label、name、display、pattern、required）由系统自动注入。

### 关键参数

| 名称 | 类型 | 默认值 | 何时设置 |
|------|------|--------|----------|
| selectMode | `boolean` | `false` | 是否多选。`false` 单选，`true` 多选 |
| showMode | `1 \| 2` | `2` | 展示方式。`1` 平铺（适合 3-5 个选项），`2` 下拉（适合多选项） |
| dataGroupId | `string` | | 数据字典的 **key**（GUID），决定选项来源。必填 |

### 其余参数（有默认值，无明确需求不用设）

| 名称 | 默认值 | 说明 |
|------|--------|------|
| defaultValue | | 默认值，多选时为数组 |
| placeholder | `'请选择'` | 占位提示（仅下拉模式） |
| layoutMode | `'transverse'` | 平铺布局：`transverse` 横向 / `portrait` 纵向 |

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- `dataGroupId` 使用数据字典的 **key** 字段（GUID），不是字典名。工具会自动同步写入 `staticDataList`（与 dataGroupId 同值）。
- showMode=1 平铺模式适合选项少的场景，showMode=2 下拉适合选项多的场景。
- 多选（selectMode=true）时，存储值为数组。
