# 编排公共方法参考（public-methods/）

业务编排（BizFlow）代码里调用的平台公共方法参考源码。读快照中的编排代码遇到平台方法时在此查语义：

| 文件 | 覆盖范围 | 什么时候查 |
|------|----------|-----------|
| related-attributes.js | JS 编排运行时注入的 `relatedAttributes.*`（31 个方法 + moment/message/gxpUrl 工具值） | 读 `pages/*/bizflows/*/action.js`、`public-bizflows/*/action.js` 遇到 `relatedAttributes.xxx(...)` |
| csharp-service.cs | C# 编排的三层调用面：`this.*` 上下文属性（14 个）、`_service.*` 平台方法（30 个）、ServicesBase 继承成员 | 读 `action.cs` 遇到 `_service.xxx(...)`、`this.globalVariables` 等 |

## 背景知识

- JS 编排发布为 `function (inbiz, relatedAttributes) { var self = {}; self.main = async function (...) {...}; return self; }`，平台方法统一经 `relatedAttributes.xxx(...)` 调用（异步须 `await`）。
- C# 编排编译为继承 `BizflowsCsharpServiceBase` 的动态类，平台方法经 `_service.xxx(...)` 调用，表单/流程上下文经 `this.xxx` 属性访问。
- JS 侧方法按「基础包 → 元件注册表 → 运行时插件」顺序合并（重名先到先得）；本目录只含静态注册部分，运行时插件（`/api/plugins/ActionDesign`）注入的方法不在内。

## 时效说明

本目录不是平台拉取数据，而是从平台前后端源码库抽取的参考资产，随 cpm CLI 版本分发：

- 来源：`gxp2.components`（前端，src/core/common/ActionDesign/）与 `gxp2.web`（后端，GxP2.Services/），每个方法/属性注释中标注了源文件与行号。
- 平台版本升级后内容可能过时：以注释中的来源路径为准，需要时到源码库核对。
