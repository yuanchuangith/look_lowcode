> 来源：schema-tools/components/FormTab.TabPane/knowledge.md（同步于 2026-08-25）

# FormTab.TabPane（标签页）

> 组件 Key: `FormTab.TabPane`

标签页是 FormTab 的子容器，每个标签页内可以放置卡片和字段。

## 属性

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| tab | string | - | 标签页名称，如"基本信息" |
| clickable | boolean | true | 是否可点击切换到此标签页 |
| linkType | `'in' \| 'out'` | `'in'` | 链接类型，真实业务数据中普遍为 `in` |

## 使用方式

**方式一：自动创建**
FormTab 创建时会自动生成 TabPane 子节点，无需手动创建。

**方式二：手动添加**
当需要在已有 FormTab 中增加新标签页时，手动添加 TabPane（tab 必填）。

## 层级关系

```
FormTab（选项卡）
  └── FormTab.TabPane（标签页）  ← 可手动添加
        └── GxpCard（卡片区块）
              └── FormGrid（栅格布局）
```

## 注意事项

- TabPane 必须放在 FormTab 内部
- 手动添加 TabPane 后，建议同步更新 FormTab 的 tabs 属性
- clickable 控制该标签页是否可通过点击切换
