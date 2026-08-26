// BizFlow（业务编排）C# 运行时平台方法 —— 参考源码
//
// C# 编排（快照中 action.cs / public-bizflows/*/action.cs）发布后由平台 Roslyn 编译为
// 继承 BizflowsCsharpServiceBase 的动态类并执行（样例 gxp2.web GxP2.Services/Business/BizflowsDesign/test.cs）：
//
//   public class Gyi9OVgeM : BizflowsCsharpServiceBase
//   {
//       public async Task<Dictionary<string, object>> main()
//       {
//           await _service.InsertModelData("表名", data);              // 平台方法经 _service 调用
//           var rows = _service.GetModelData("表名", where);            // where 由 _service.WhereFormat 构造
//           var v = this.globalVariables["key"];                       // 上下文属性经 this 访问
//           return outputParams;
//       }
//   }
//
// 可调用面三层：① this 上下文属性（BizflowsCsharpServiceBase 注入）② _service 平台方法
// （BizflowsCsharpService）③ 基类 ServicesBase 继承成员。本文件签名与 XML 注释摘自源码
// （gxp2.web GxP2.Services\），方法体省略；抽取日期 2026-08-26。

/// <summary>编排上下文属性（BizflowsCsharpServiceBase.cs:25-72 注入，生成代码内 this.xxx 直接访问）</summary>
public class BizflowsCsharpServiceBase
{
    /// <summary>全局变量</summary>
    public Dictionary<string, object> globalVariables;
    /// <summary>表单数据</summary>
    public Dictionary<string, object> formData;
    /// <summary>机构ID</summary>
    public string orgId;
    /// <summary>机构名称</summary>
    public string orgName;
    /// <summary>机构编号</summary>
    public string orgCode;
    /// <summary>记录ID（当前单据）</summary>
    public string recordId;
    /// <summary>是否新增记录</summary>
    public bool isNewRecord;
    /// <summary>流程信息（activityId/operationType/instanceId 等）</summary>
    public Dictionary<string, object> workFlow;
    /// <summary>子表提交数据</summary>
    public List<SubFormSubmitData> subForms;
    /// <summary>当前用户（ClaimUser）</summary>
    public ClaimUser _user;
    /// <summary>当前 Token</summary>
    public string _token;
    /// <summary>模型名称</summary>
    public string modelName;
    /// <summary>编排调用上下文 DTO（formData/orgId/recordId/workFlow/pageId 等原始载荷）</summary>
    public BizflowsCsharpDto csharpDto;
    /// <summary>平台公共方法入口（本文件第二部分）</summary>
    public BizflowsCsharpService _service;
}

/// <summary>平台公共方法（BizflowsCsharpService.cs，生成代码经 _service.xxx 调用；XML 注释摘自源码）</summary>
public class BizflowsCsharpService
{
    // ---- 模型/数据 CRUD ----

    /// <summary>插入模型数据（datetime 列自动时区转换）</summary>
    /// <param name="tableName">模型表名</param> <param name="data">字段→值</param> <returns>受影响行数</returns>
    public async Task<int> InsertModelData(string tableName, Dictionary<string, object> data);

    /// <summary>更新模型数据（旧签名兼容）</summary>
    public int UpdateModelData(string tableName, DynamicFilterInfo where, Dictionary<string, object> data);

    /// <summary>更新模型数据；reason 记入审计摘要</summary>
    public int UpdateModelData(string tableName, DynamicFilterInfo where, Dictionary<string, object> data, string reason = null);

    /// <summary>删除模型数据（旧签名兼容）</summary>
    public async Task<int> DeleteModelData(string tableName, DynamicFilterInfo where);

    /// <summary>删除模型数据；reason 记入审计摘要</summary>
    public async Task<int> DeleteModelData(string tableName, DynamicFilterInfo where, string reason = null);

    /// <summary>获取模型数据（datetime 列自动时区转换）</summary>
    /// <param name="orderFields">字段→'asc'/'desc'</param>
    public List<Dictionary<string, object>> GetModelData(string tableName, DynamicFilterInfo where,
        Dictionary<string, string> orderFields = null);

    // ---- 数据集 / 查询构造 ----

    /// <summary>获取数据集数据（key 为数据集 id；datetime 列自动时区转换）</summary>
    public List<Dictionary<string, object>> GetDataSetData(string dataSetKey, DynamicFilterInfo where,
        Dictionary<string, string> orderFields = null, PageInfo pageInfo = null);

    /// <summary>格式化 where 条件：where 含 {0}/{1}… 占位符（如 "Name like '%{0}%'"），paranames 按序替换</summary>
    public DynamicFilterInfo WhereFormat(string where, params object[] paranames);

    /// <summary>格式化排序字段：sort（如 "CreateTime desc, Code" 或对象）→ 字段→'asc'/'desc' 字典</summary>
    public Dictionary<string, string> SortFormat(object sort);

    /// <summary>查询系统(组织)信息。type：组织类型；isContainChild：是否含下级</summary>
    public List<Dictionary<string, object>> QueryOrgInfo(List<string> ids, string type, bool isContainChild);

    // ---- 通用工具 ----

    /// <summary>判断对象是否为空（null/空串/空集合）</summary>
    public bool IsEmpty(object data);

    /// <summary>相等比较（跨类型容错）</summary>
    public bool CustomEquals(object obj1, object obj2);

    /// <summary>取数组/集合长度</summary>
    public int GetLength(object data);

    /// <summary>按点路径取值："globalVariables.key" / "formData.key" / "workFlow.key"</summary>
    public object TryGetValue(string path);

    /// <summary>获取当前服务器 IP 列表</summary>
    public List<string> GetLocalIPAddresses();

    // ---- 编排互调 / 事件 ----

    /// <summary>调用另一个动态编排方法（RefId=目标编排，MethodName=动作名，Params=参数）</summary>
    public async Task<Dictionary<string, object>> InvokeDynamicMethod(string RefId, string MethodName,
        bool IsPublish, BizflowsCsharpDto csharpDto, params object[] Params);

    /// <summary>触发事件订阅（延迟 1.5s 异步）。events: [{key, value}]；eventParams: 事件参数</summary>
    public void CallEvent(List<Dictionary<string, string>> events, Dictionary<string, object> eventParams);

    // ---- 编号 / 消息 / 待办 ----

    /// <summary>生成策略编号。变量优先级：上下文>传入参数>全局变量>表单数据；isFixedCode=固定编号</summary>
    public string GenerateCode(string idOrJsonConfig, Dictionary<string, string> variableParams,
        List<object> context = null, bool isFixedCode = false, bool isExample = false);

    /// <summary>通过消息模板发送消息（platformCode 模板编码；placeholders 占位符；attachUserIds 附加接收人）</summary>
    public async Task<DataResult> SendTemplateMessage(string platformCode, Dictionary<string, object> placeholders,
        List<string> attachUserIds = null, string messageType = null);

    /// <summary>新增待办事项（dto 含标题/接收人/关联单据/跳转页面等）</summary>
    public int AddTodoList(AssignmentBillDto dto);

    /// <summary>更新待办事项状态（dto: 状态字典）</summary>
    public int UpdateTodoStatus(string key, Dictionary<string, int> dto);

    // ---- 流程 ----

    /// <summary>流程任务是否完成（incident=流程实例，taskIds=任务ID数组）</summary>
    public bool TaskIsComplate(string incident, string[] taskIds);

    /// <summary>工作流是否完成</summary>
    public bool WorkFlowIsComplate(string incident);

    /// <summary>当前节点是否审批完成</summary>
    public bool CurrentTaskIsComplate(string incident, string taskId, string userId);

    /// <summary>获取流程节点审批人ID（nodeName 节点名；range: -1待审批/0全部/1已审批；多人逗号分隔）</summary>
    public string GetProcessIncidentApprover(string incident, string nodeName, int range = 1);

    /// <summary>按节点编号获取审批人ID（activityNo 节点编号；range 同上）</summary>
    public string GetProcessIncidentApproverByActivityNo(string incident, string activityNo, int range = 1);

    // ---- 集成 / 接口 / 打印 / 文件 ----

    /// <summary>按接口管理配置调用外部接口（interfaceId；headers/path/query/body 四组参数）</summary>
    public Dictionary<string, object> CallInterface(string interfaceId, Dictionary<string, string> headers,
        Dictionary<string, string> path, Dictionary<string, string> query, object body);

    /// <summary>打印任务（返回条码集合）</summary>
    public async Task<IEnumerable<string>> PrintTask(object dto);

    /// <summary>根据模板文件生成报告</summary>
    public async Task<GenerateReportResult> GenerateReport(GenerateReportRequestDto dto);

    /// <summary>发布文件</summary>
    public async Task<UploadFileResponseDto> ReleaseFile(string fileId);

    /// <summary>复制文件版本</summary>
    public async Task<UploadFileResponseDto> CopyFileVersion(string versionId);

    // ---- 系统配置 / 日期 ----

    /// <summary>获取系统配置的日期格式</summary>
    public string GetDateFormat();

    /// <summary>时区日期转通用格式 yyyy-MM-dd HH:mm:ss</summary>
    public string ConvertToUniversalDateTime(object dateValue);

    /// <summary>获取系统配置值（key 配置键；orgId 空取全局）</summary>
    public string GetCpmSettingValue(string key, string orgId = "");
}

/// <summary>ServicesBase 继承成员（this.xxx 可用；编排常用的列在此，全量见 gxp2.web GxP2.Services/Base/ServicesBase.cs）</summary>
public abstract class ServicesBase
{
    /// <summary>FreeSql 数据库对象（IFreeSql，事务感知）</summary>
    public IFreeSql Db;
    /// <summary>当前用户（ClaimUser）</summary>
    public ClaimUser User;
    /// <summary>事务：action 内 Db 操作进同一事务；支持分布式锁参数 lockKey/lockExpiry/lockTimeout</summary>
    protected T Transaction<T>(Func<T> action);
    /// <summary>查询实体（自动过滤 IsDeleted；includeDeleted=true 含已删）</summary>
    protected ISelect<T> Select<T>(bool includeDeleted = false);
    /// <summary>取平台服务（DI 容器）</summary>
    protected T GetService<T>();
    /// <summary>实体审计字段辅助（创建人/时间等，Insert/Update/Delete 系）</summary>
    protected void AddBaseEntity(/* 重载见源码 */);
    protected void UpdateBaseEntity(/* 重载见源码 */);
    protected void DeleteBaseEntity<T>(/* 重载见源码 */);
}
