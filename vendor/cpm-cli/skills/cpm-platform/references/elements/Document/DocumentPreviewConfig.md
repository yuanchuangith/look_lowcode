> 来源：action-design-tools/nodes/Document/DocumentPreviewConfig/knowledge.md（同步于 2026-08-25）

# 文档预览

> 元件 Key: `DocumentPreviewConfig`

## 适用场景
配置文档预览（指定组件、预览权限动作、附件动作、查看器）并打开预览。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `name`（输入，必填） | 目标组件引用 `{value, label, componentType, modelkey}` | **固定**：从 `getPageComponents` 取表格/列表组件 ref | 固定结构，取自工具 |
| 其余配置项（如预览权限动作/附件动作/查看器） | 预览配置字面量/表达式对象 | **半固定**：按预览配置填，多为固定选项 | 结构固定 |

> 无输出参数。打开预览是终端动作。

## 参数说明

### 输入参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| component | object | 是 | false | 目标组件引用 {value, label, componentType, modelkey}，通常为表格/列表组件 |
| columnKey | string | 否 | false | 文件标识所在的列 key（如 file_name） |
| permissionAction | object | 否 | false | 预览权限判断动作引用（从 getActionList 取） |
| attachmentAction | object | 否 | false | 获取附件/签批页的动作引用（从 getActionList 取） |
| viewer | array | 否 | false | 查看器配置数组，每项 {key, name, extension[], previewPanels[]}，如 "PDF 标准预览" |

### 输出参数
无。

## 参数示例
```json
{
  "elementKey": "DocumentPreviewConfig",
  "params": {
    "inputs": {
      "component": { "value": "GxpSmartTables", "label": "GxpSmartTables", "componentType": "GxpSmartTables", "modelkey": "<GUID>" },
      "columnKey": "file_name",
      "permissionAction": { "value": "<动作id>", "label": "DMS预览权限判断" },
      "attachmentAction": { "value": "<动作id>", "label": "预览获取签批页和变更记载" },
      "viewer": [{ "key": "pdf", "name": "PDF 标准预览", "extension": ["pdf"], "previewPanels": [] }]
    }
  }
}
```

## 使用示例
```
文档预览(组件="GxpSmartTables", 权限="DMS预览权限判断", 附件动作="预览获取签批页和变更记载", 查看器="PDF 标准预览")
```

## 注意事项
- **平台自动生成、模型不要手写**：component.modelkey(GUID)、permissionAction/attachmentAction 的元数据字段、viewer 各项的 id/code。
