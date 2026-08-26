> 来源：schema-tools/components/CustomUpload/knowledge.md（同步于 2026-08-25）

# 导入

> 组件 Key: `CustomUpload`

## 适用场景
通过上传 Excel 文件导入数据，适用于批量数据导入。

## 属性

> 公共属性（label、name、display）由系统自动注入。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| templateUrl | `string` | | 导入模板下载地址 |

## 放置规则

- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 配置 templateUrl 后，用户可在导入前下载模板
- 支持上传前和上传后事件拦截
