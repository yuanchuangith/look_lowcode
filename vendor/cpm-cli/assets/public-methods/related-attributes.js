/**
 * BizFlow（业务编排）JS 运行时公共方法包 —— 参考源码
 *
 * 平台把每个 JS 编排发布为如下形态的函数，生成代码内统一通过 relatedAttributes.xxx(...) 调用平台方法（异步须 await）：
 *   function (inbiz, relatedAttributes) {
 *     var self = {};
 *     self.main = async function (a, b) {
 *       var ok = await relatedAttributes.showConfirmModal('标题', '内容');
 *       var rows = await relatedAttributes.getSelectModelData('modelKey', 1, 100, where);
 *       return self.outputParams; // 输出参数
 *     };
 *     return self;
 *   }
 *
 * 本文件从平台前端源码抽取（gxp2.components src/core/common/ActionDesign/），供 AI 理解快照中
 * action.js / public-bizflows/*/action.js 的编排代码。方法体不可独立执行（依赖平台运行时闭包），
 * 签名/参数/返回/来源行号是权威信息。抽取日期：2026-08-26。
 *
 * 注入合并规则（重名先到先得、不覆盖）：基础包（utils.tsx）→ 元件注册表（ElementListData 静态）
 * → 运行时插件（GET /api/plugins/ActionDesign 远程加载，本文件不含插件注入项）。
 */
const relatedAttributes = {

  // ========== 基础：机构 / 消息 / 日期时间（ActionDesign/utils.tsx:359-405） ==========

  /** 当前机构 ID。实现：cookie companyId → 当前用户 orgId（getCurrentCompany）。来源 utils.tsx:360 */
  async getOrgId() { /* 依赖平台 getCurrentCompany */ },

  /** 当前机构名称。来源 utils.tsx:364 */
  async getOrgName() { /* 依赖平台 getCurrentCompany */ },

  /** 当前机构编号。来源 utils.tsx:368 */
  async getOrgCode() { /* 依赖平台 getCurrentCompany */ },

  /** 轻提示（antd message.info，3 秒）。参数 content：提示文本。来源 utils.tsx:372 */
  ShowMessage(content) { /* 依赖 antd message */ },

  /**
   * 服务器当前时间（异步版）。参数 part 可选：'year'|'month'|'day'|'hour'|'minute'|'second'
   * 返回对应部件字符串；不传返回按系统 DateFormat 拼装的完整 Date 对象。
   * 内部 GET /api/system/datetime/now。来源 utils.tsx:378
   */
  async currentDate(part) { /* 依赖平台 service */ },

  /** 服务器当前时间（同步 XHR 版，参数与返回同 currentDate）。生成代码里日期快捷取值多用它。来源 utils.tsx:391 */
  syncCurrentDate(part) { /* 依赖平台 service（同步 XHR） */ },

  /** 系统配置的日期格式串（如 'yyyy-MM-dd'，GET /api/settings）。来源 utils.tsx:398 */
  async getDateFormat() { /* 依赖平台 getSettings */ },

  /**
   * 流程上下文信息。参数 name 可选：'activityId'|'operationType'|'activityNo'|'taskName'|'instanceId'
   * 不传返回含全部五键的对象。来源 utils.tsx:624（纯取值，无外部依赖）
   */
  getWorkFlowInfo(inbiz, name) {
    // var workFlow = { activityId: inbiz.workFlow?.activityId, operationType: inbiz.workFlow?.operationType,
    //   activityNo: inbiz.workFlow?.baseInfo?.activityNo, taskName: inbiz.workFlow?.baseInfo?.taskName,
    //   instanceId: inbiz.queryData.instanceId };
  },

  /**
   * 打开页面。参数：pageId 目标页面 ID；openType 'modal'（1200 宽弹窗）|'tab'（平台页签）|'newPage'（新窗口）；
   * pageParameter 附加参数数组 [{key, value}]（自动附带 masterRecordId=当前 recordId）；
   * inbiz 当前页 SDK；pageName 可选页签标题（缺省取目标页面名）。
   * 来源 utils.tsx:636
   */
  async OpenPage(pageId, openType, pageParameter, inbiz, pageName) { /* 依赖平台 gxpLoadPage/GxpTabs 等 */ },

  // ========== 编排互调与表单数据 ==========

  /**
   * 调用 C# 编排方法（JS 编排调后端动作的唯一通道，POST /api/bizflows_design/call_csharp）。
   * 参数：refId 业务编排 refId；methodName C# 动作名（调公共编排固定 'main'）；
   * globalVariables 通常传 self.globalVariables；params 输入参数数组。
   * 平台自动附带 formData/orgId/recordId/workFlow/pageId 等上下文（getCallCsharpDto）。来源 CallAction.tsx:113
   */
  async CallCsharpAction(inbiz, refId, methodName, globalVariables, params) { /* 依赖平台 request */ },

  /**
   * 取表单数据。参数 key 可选：模型字段名（FormField 的 props.name）。
   * 传 key 返回单字段值（对象/数组序列化为 JSON 字符串）；取值优先级：控件实时值 > masterDatas > oldData。
   * 不传返回整个表单数据对象（合并 oldData + masterDatas（跳过 @desc 后缀）+ 控件实时值）。来源 utils.tsx:524
   */
  GetFormData(key) { /* 依赖 window.inbiz 页面 SDK */ },

  /**
   * 调用另一个 JS 编排（含公共编排）。参数：refId 目标编排 ID；...otherParams 透传给目标 main。
   * 目标代码经 GET /api/bizflows_design/js 拉取并按 refId 缓存。来源 utils.tsx:416
   */
  async execActionsFun(inbiz, refId, ...otherParams) { /* 依赖平台 actionFunctionCache */ },

  // ========== 数据查询（数据中心） ==========

  /**
   * where 条件占位符替换。参数：whereStr 含 {{0}}/{{1}}… 占位符的 JSON 字符串；
   * params 按序替换的值数组（含 JSON 的字符串自动转义引号）。返回解析后的 where 对象。
   * 来源 Database/SelectModelData.tsx:181
   */
  whereFormat(whereStr, params) {
    params.forEach((item, index) => {
      let escapedValue;
      if (typeof item === 'string') {
        const hasJsonLikeData = /[\[{].*".*".*[\]}]/.test(item) || /".*".*"/.test(item);
        escapedValue = hasJsonLikeData ? JSON.stringify(item).slice(1, -1) : item;
      } else escapedValue = String(item);
      whereStr = whereStr.replace(`{{${index}}}`, escapedValue);
    });
    return JSON.parse(whereStr);
  },

  /**
   * 查询数据中心模型/数据集。参数：modelkey 模型标识；pageIndex 页码；pageSize 页大小（默认 int32 最大值=不分页）；
   * filter whereFormat 返回的过滤对象。返回 { Rows, Total }。来源 Database/SelectModelData.tsx:202
   */
  async getSelectModelData(modelkey, pageIndex, pageSize, filter) { /* 依赖平台 QueryDataCenter */ },

  /** 查询条件加密（条件含敏感数据时后端要求先加密，statusCode==200 返回密文，失败原样返回）。来源 SelectModelData.tsx:221 */
  async conditionEncrypt(condition) { /* 依赖平台 dataEncrypt */ },

  // ========== 通用工具值与判空 ==========

  /** 判空：null/undefined/空串/空数组/空对象/NaN/时间戳 0（1970-01-01）为 true；数字 0 与布尔 false 非空。来源 base/utils.tsx:986 */
  isEmpty(value) {
    if (value === undefined || value === null) return true;
    if (value instanceof Date) return value.getTime() === 0;
    if (Array.isArray(value)) return value.length === 0;
    const type = typeof value;
    if (type === 'string' || value instanceof String) return String(value) === '';
    if (type === 'number' || value instanceof Number) return isNaN(Number(value));
    if (type === 'boolean' || value instanceof Boolean) return false;
    if (type === 'object')
      return Object.prototype.toString.call(value) === '[object Object]' && Object.keys(value).length === 0;
    return false;
  },

  /** moment 日期库实例（npm moment，完整 API：moment(date).format('YYYY-MM-DD')、add/subtract 等） */
  moment: null,

  /** antd message API：message.success/error/info/warning({content, duration})、message.loading。来源 OpenMessageDialog.tsx:94 */
  message: null,

  /** 平台 API 前缀（string，如 origin + '/gxp2'）：拼接口地址用 relatedAttributes.gxpUrl + '/api/...'。来源 base/config.ts:6 */
  gxpUrl: null,

  // ========== 文档与打印 ==========

  /**
   * 复制文件版本（POST /api/Storage/copy_file_version）。参数 versionId 文件版本 ID；
   * 返回 { id, verId, ... } 新版本信息；业务码非 200 抛错。来源 Document/FileCopyVersion.tsx:147
   */
  async copyFileVersion(versionId) { /* 依赖平台 request */ },

  /**
   * 批量下载（源文件/PDF 共用，POST）。参数单对象：url 接口地址（/api/Storage/batch_download 或 batch_download_pdf）；
   * body POST 体（含 ids、pc、downloadMode）；downloadMode 'direct'（浏览器直接下载）|'task'（异步任务，仅提示）；
   * fileName 用户配置文件名或 null；messageApi 通常传 relatedAttributes.message；defaultFileName 兜底文件名。
   * 来源 Document/FileDownload.tsx:260
   */
  async handleBatchDownload(options) { /* 依赖 fetch，扩展名从响应取 */ },

  /**
   * 单文件下载（遗留模式，GET）。参数单对象：url GET 地址；fileName 用户配置文件名或 null；
   * messageApi 通常传 relatedAttributes.message。来源 Document/FileDownload.tsx:301
   */
  async handleDirectDownload(options) { /* 依赖 fetch */ },

  /**
   * 打开打印预览弹窗（全屏）。参数单对象：inbiz 页面 SDK；fileVerId 文件版本 ID；copies 份数；
   * printCopies 打印份数；FileStorageType 固定 1；fileName 文件名或 null；Watermark 水印配置或 null
   * （convertWatermarkFormat 的返回值）；scope/printPages/Config/AttachFileVerIds/MergeFiles 其余打印配置或 null。
   * Promise 在用户点打印时 resolve。来源 FilePrint/index.tsx:213
   */
  async ShowPrintPreview(props) { /* 依赖平台 FilePrint 组件 */ },

  /**
   * 设置文档预览配置。参数：inbiz 页面 SDK；params 单对象：component 组件 ID；columnKey 列 key（表格列预览时）；
   * viewer 预览器编排 refId；permissionAction 权限编排 refId；relatedDocumentsAction/attachmentAction 关联编排 refId；
   * variables 预览变量；watermark 水印；globalVariables 通常传 self.globalVariables。来源 base/utils.tsx:1223
   */
  setDocumentPreviewConfig(inbiz, params) { /* 写入页面级预览配置 */ },

  /**
   * 水印设计配置转后端格式（文档生成水印用）。参数：jsonStr 水印设计 JSON 字符串（设计器产出）；
   * sourceData 源数据（供变量替换）；dateFormat 可选日期格式。返回后端水印对象数组。
   * 长实现（约 96 行，含纸张分组/坐标换算/变量替换），来源 DataProcessing/WatermarkConvert.tsx:133
   */
  async convertWatermarkFormat(jsonStr, sourceData, dateFormat) { /* 详见来源文件 */ },

  /**
   * 版本号格式化。参数 versionValue：'X.Y' 字符串或数字主版本。按系统配置 VersionFormat
   * （X.Y / 0(X-1) / 0(X) 三种格式）转换。来源 DataProcessing/VersionFormat.tsx:131
   */
  async formatVersion(versionValue) { /* 依赖平台 formatVersionBySettings */ },

  // ========== 对话框交互 ==========

  /** 确认对话框。参数：title 标题；content 内容。返回 Promise<boolean>：确认 true / 取消 false。来源 base/utils.tsx:67 */
  async showConfirmModal(title, content) { /* 依赖 antd Modal.confirm */ },

  /**
   * 输入对话框。参数：title 标题；inputType 'text'|'password'|'textarea'|'number'。
   * 返回 Promise<string>：用户输入值（取消时 reject）。来源 base/utils.tsx:88
   */
  showInputDialog(title, inputType) { /* 依赖 antd Modal.confirm + Input */ },

  // ========== 系统配置与页面广播 ==========

  /**
   * 读系统配置（GET /api/settings，模块级缓存）。参数：key 可选配置键（不传返回全部）；
   * orgId 可选机构。返回 DataResult，取值 resp.data[key]。来源 base/service.ts:455
   */
  async getSettings(key, orgId) { /* 依赖平台 request + 缓存 */ },

  /** 页面广播发送（跨窗口生效）。参数：eventName 事件名；params 可选载荷。来源 Notice/SendPageBroadcast.tsx:69 */
  eventsemit(eventName, params) { /* 依赖平台 events 单例 */ },

  /**
   * 页面广播订阅。参数：eventName 事件名；callback 回调（生成代码中传 self.<动作名>，
   * 即把编排内子动作注册为广播处理器）。来源 Notice/SubscriptionPageBroadcast.tsx:66
   */
  eventson(eventName, callback) { /* 依赖平台 events 单例 */ },

  // ========== 页面生命周期钩子 ==========

  /**
   * 注册保存后回调（覆盖式）。参数：handler 回调（生成代码中为 async function，内部常再调 CallCsharpAction）。
   * 来源 Page/AfterSave.tsx:87
   */
  AfterSave(inbiz, _refId, handler) { /* inbiz.configEvent('AfterSave', handler) */ },

  /**
   * 注册「提交后端前」回调（写入页面全局变量键 BeforeSubmitBackend）。参数：refId 编排 refId；
   * methodName 动作名；globalVariables 通常传 self.globalVariables。注意：定义于 BeforeSubmitBackend.tsx。
   * 来源 Page/BeforeSubmitBackend.tsx:70
   */
  AfterSubmit(inbiz, refId, methodName, globalVariables) { /* setPageGlobalVariable */ },

  /**
   * 注册「提交后端后」回调（写入页面全局变量键 AfterSubmitBackend）。参数同 AfterSubmit。
   * 来源 Page/AfterSubmitBackend.tsx:72
   */
  AfterSubmitBackend(inbiz, refId, methodName, globalVariables) { /* setPageGlobalVariable */ },
};

/** 工具值实际由平台注入（此处 null 占位）：moment=npm moment 实例；message=antd message；gxpUrl=API 前缀串 */
