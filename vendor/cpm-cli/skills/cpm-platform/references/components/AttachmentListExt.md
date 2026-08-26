> 来源：schema-tools/components/AttachmentListExt/knowledge.md（同步于 2026-08-25）

# 附件列表

> 组件 Key: `AttachmentListExt`

## 适用场景

以表格形式展示和管理附件列表的表单字段组件。支持文件上传、下载、删除、更新、查看历史版本等操作。与文件上传（FileUploadExt）的区别是，附件列表以表格展示，功能更丰富（含版本管理、表格列配置）。

## 属性

> 工具自动补齐平台运行时字段（dataCenter/storageConfig/queryFields/modelkey/controlId/tableListConfig 列定义等），数据源绑定由平台 DataCenter 完成。
> 公共属性（label、name、display、pattern、required）由系统自动注入。

### 关键参数

| 名称 | 类型 | 默认值 | 何时设置 |
|------|------|--------|----------|
| multiple | `boolean` | `false` | 是否允许多选上传 |
| uploadFolder | `boolean` | `false` | 是否支持文件夹上传 |
| showPersonalFolder | `boolean` | `false` | 是否显示个人内容库 |
| nameConflictStrategy | `string` | `'majorUpgrade'` | 重名策略：majorUpgrade / rename / skip |
| uploadList | `string` | `'manual'` | 上传列表关闭方式：manual / autoClose |

### 其余参数（有默认值，无明确需求不用设）

| 名称 | 默认值 | 说明 |
|------|--------|------|
| defaultStrategy | `true` | 是否启用默认重名策略 |
| tablePageSize | `'10'` | 每页记录数 |
| filePermissionType | `1` | 文件类型限制方式（1 允许 / 0 禁止） |
| fileTypeList | `[]` | 文件类型白名单/黑名单 |

## 放置规则
- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项

- 与文件上传组件不同，附件列表以表格形式展示附件，功能更丰富。
- nameConflictStrategy 仅当 defaultStrategy 为 true 时生效。
- 数据源绑定（dataCenter/modelkey/storageConfig）、表格列定义（tableColSettingList）、操作按钮（tableOperationList）等由平台自动生成，**模型不要手写这些**。
