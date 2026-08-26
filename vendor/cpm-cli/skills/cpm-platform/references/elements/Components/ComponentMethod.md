> 来源：action-design-tools/nodes/Components/ComponentMethod/knowledge.md（同步于 2026-08-25）

# 调用组件方法

> 元件 Key: `ComponentMethod`

## 适用场景
调用页面组件暴露的方法（如刷新表格、清空输入框、获取选中行等）。每个组件有哪些方法，由 `getComponentInfo` 返回。

## 参数逐条说明

本元件有 4 类参数，下表逐一钉死「传什么 / 值从哪来 / 性质(固定/半固定/灵活)」。

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `name`（输入，必填） | 目标组件的**引用对象**（不是字符串） | **固定**：从 `getPageComponents` 返回里取组件的 `ref`，直接粘贴；结构 `{paramTypes:"componentsVariable", value:"componentsVariable-{组件id}", code:"inbiz('{组件id}')", label:"页面组件-{组件名}", dataType:"{组件类型}"}` | 固定结构，取自工具 |
| `methodName`（输入，必填） | 要调用的方法名（字符串字面量，如 `"load"`、`"getSelectedRows"`） | **固定**：从 `getComponentInfo(componentTypes)` 返回的 `methods` 数组里取 `name`。**别凭常见命名猜**（如把 refresh 写成 reload） | 固定值，取自工具 |
| `param_<参数名>`（输入，可选） | 方法的实参。键名固定前缀 `param_` + 方法形参名（如 `param_columnId`） | **半固定**：形参名从 `getComponentInfo` 该方法的 `params` 里取；每个实参值是表达式对象，按实参内容填 | 键名固定，值灵活 |
| `returnValue`（输出，可选） | 方法返回值的**变量名绑定**。键名固定 `returnValue` | **灵活**：变量名自己起（有语义、全编排不重复）；值为表达式对象 `paramTypes:"custom"`，`value`/`code`/`label` 都填这个变量名。仅当方法有返回值时填 | 自定义 |

> 命名、作用域、跨动作共享等通用规则见 prompt.md「变量与作用域」。**重名不报错而是赋值给同名变量**，别用 `data`/`result` 这种泛化名。

## 真实数据样本

### 样本 A：无参无返回（刷新表格）
```json
{
  "elementKey": "ComponentMethod",
  "params": {
    "inputs": {
      "name": {
        "paramTypes": "componentsVariable",
        "value": "componentsVariable-AssessmentList",
        "dataType": "FormTables",
        "label": "页面组件-文件信息列表",
        "code": "inbiz('AssessmentList')"
      },
      "methodName": "load"
    }
  }
}
```

### 样本 B：有返回值（取表格数据存到变量 fileInfoList）
```json
{
  "elementKey": "ComponentMethod",
  "params": {
    "inputs": {
      "name": {
        "paramTypes": "componentsVariable",
        "value": "componentsVariable-DcoumentInfoList",
        "dataType": "FormTables",
        "label": "页面组件-文件信息列表",
        "code": "inbiz('DcoumentInfoList')"
      },
      "methodName": "getData"
    },
    "outputs": {
      "returnValue": {
        "paramTypes": "custom",
        "value": "fileInfoList",
        "dataType": "",
        "label": "fileInfoList",
        "code": "fileInfoList"
      }
    }
  }
}
```

## 下游怎么引用返回的局部变量

`returnValue` 产出的 `fileInfoList` 是个**局部变量**，下游引用**用 `paramTypes:"localVariable"`，不是 custom**：

```json
{ "paramTypes": "localVariable", "value": "localVariable-fileInfoList", "label": "局部变量-fileInfoList", "code": "fileInfoList", "dataType": "array" }
```

取属性（如长度）：`code` 写 `"fileInfoList.length"`，`value`/`label` 同步带上属性。

## 使用示例
```
用户："刷新表格"
→ getPageComponents 找到表格组件 ref
→ getComponentInfo 查表格的 methods，取 methodName="load"
→ addNode(ComponentMethod, name=组件ref, methodName="load")

用户："拿到表格选中行存到变量"
→ 同上查到 methodName="getSelectedRows"
→ addNode(ComponentMethod, name=组件ref, methodName="getSelectedRows", returnValue="selectedRows")
```

## 注意事项
- `name` 是组件**引用对象**（非字符串）；`methodName` 是**字符串字面量**。
- `param_<参数名>` 的实参值、`returnValue` 都是表达式对象。
- 输出键名固定 `returnValue`（非 result）；`value`/`code`/`label` 三者都填变量名。
