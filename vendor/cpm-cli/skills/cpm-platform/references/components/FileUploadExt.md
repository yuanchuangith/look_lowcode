> 来源：schema-tools/components/FileUploadExt/knowledge.md（同步于 2026-08-25）

# 文件上传

> 组件 Key: `FileUploadExt`

## 适用场景
用于上传各类文件的表单字段组件。支持多文件上传、版本管理，可配置文件类型和大小限制。与图片上传（EformImgUpload）的区别是，文件上传以列表形式展示非图片文件。

## 属性

> 工具自动补齐平台运行时字段（model/modelend/extendBtns 默认 5 按钮/targetFolderType），模型只需提供下方参数。
> 公共属性（label、name、display、pattern、required）由系统自动注入。

### 关键参数

| 名称 | 类型 | 默认值 | 何时设置 |
|------|------|--------|----------|
| multiple | `boolean` | `false` | 是否允许多文件上传 |
| fileSize | `string` | `'100MB'` | 单文件大小限制（如 `'100MB'`、`'1GB'`） |
| maxNumber | `string` | | 最大上传数量（1~500），仅多选时设置 |
| fileType | `object` | | 文件类型限制：`{ mode: 'allow'\|'ban', typeList: ['doc','pdf'] }` |

### 其余参数（有默认值，无明确需求不用设）

| 名称 | 默认值 | 说明 |
|------|--------|------|
| repeatStrategy | `'majorUpgrade'` | 重名策略（大版本升级） |
| extendBtns | 默认 5 按钮 | 扩展按钮（删除/更新/取消/下载/扩展编辑），工具自动注入模板，默认仅删除开启 |
| placeHolderWeb | `'点击或拖拽文件到此处上传'` | Web 端提示 |
| placeHolderWap | `'点击上传文件'` | 移动端提示 |

## 放置规则
- GridColumn
- FormTab.TabPane
- GxpCard（直接放置）

## 注意事项
- 不要与 EformImgUpload 混淆，文件上传用于非图片文件。
- extendBtns 默认注入 5 按钮模板（deleteFile/upgradeFile/cancelFile/downloadFile/extendEdit），默认仅 deleteFile 开启，通常无需配置。
- targetFolderType 放在 `x-component-biz-props`（企业内容库），由工具自动注入。
- 工具自动补齐的平台字段：model/modelend/targetFolderType —— **模型不要手写这些**。
