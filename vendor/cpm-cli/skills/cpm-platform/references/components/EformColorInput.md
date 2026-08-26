> 来源：schema-tools/components/EformColorInput/knowledge.md（同步于 2026-08-25）

# 颜色框

> 组件 Key: `EformColorInput`

## 适用场景
颜色选择，适用于主题颜色配置、颜色标签设置等。

## 属性

> 公共属性（label、name、display、pattern、required）由系统自动注入。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| defaultValue | `string` | | 默认颜色值 |
| showDefaultColors | `boolean` | `false` | 是否显示默认颜色预设 |

### 颜色格式
- 十六进制：`#ff0000`、`#f00`
- RGB：`rgb(255, 0, 0)`
- RGBA：`rgba(255, 0, 0, 0.5)`

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 开启 showDefaultColors 后显示预设颜色面板，用户可快速选择常用颜色
- 支持十六进制、RGB、RGBA 格式输入
