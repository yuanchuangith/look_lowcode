> 来源：schema-tools/components/EformImgUpload/knowledge.md（同步于 2026-08-25）

# 图片上传

> 组件 Key: `EformImgUpload`

## 适用场景
用于上传和展示图片的表单字段组件。支持单张或多张图片上传，可配置图片格式、大小限制和尺寸约束。与文件上传的区别是，图片上传以图片卡片形式展示预览。

## 属性
> 公共属性（label、name、display、pattern、required）由系统自动注入。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| multiple | boolean | false | 是否允许多张上传 |
| accept | string | - | 接受的图片格式，如 'png,jpg,jpeg'（映射到 imgType，自动添加/去除 image/ 前缀） |
| imgSize | string | '1MB' | 单张图片大小限制，如 '1MB'、'500KB' |
| imgHeight | number | - | 图片高度限制（像素），超过此高度将不允许上传 |
| imgWidth | number | - | 图片宽度限制（像素），超过此宽度将不允许上传 |
| folderName | string | - | 上传到的服务端文件夹名称 |
| placeHolder | string | '上传图片' | 上传区域占位提示文字 |

## 放置规则
- GridColumn
- FormTab.TabPane
- FormCollapse（直接放置）
- GxpCard（直接放置）
- FormSiderLayout（主内容区或侧边栏）

## 注意事项
- 不要与 FileUploadExt 混淆，图片上传仅用于图片文件
- `accept` 是简化的属性名，展开时映射为 `imgType: string[]`（如 `accept: "png,jpg"` → `imgType: ["png","jpg"]`）
- 简化时 `imgType: ["jpg","png"]` → `accept: "jpg,png"`（去除 `image/` 前缀，逗号分隔）
- `model` 和 `modelend` 为内部属性，展开时自动设为空对象 `{}`
