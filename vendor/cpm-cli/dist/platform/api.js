// 平台资源端点封装：页面/规则/设计/公共编排/模型/流程/元数据。
// 每函数是 platformGet 的薄封装 + 实测响应解包；字段名依据 test/fixtures/real/（2026-08-25 实测）。
import { platformGet, ServiceUnavailableError } from './http-client.js';
import { detectPlatformError, isPermanentPlatformError } from './error-shape.js';
/**
 * 页面清单（实测定案 loadTreeList）：树形数组，全部有 Route 的节点都是页面
 * （顶层节点可能既是容器又是页面，如"培训管理"自身可路由），递归平铺。
 */
export async function getPageList(ctx, apiPrefix, appId, siteOutId) {
    const tree = await platformGet(ctx, apiPrefix, '/inbiz/api/services/engines/v3/page/loadTreeList', { appId, siteOutId });
    // 实测（2026-08-25 冒烟）：token 失效时 inbiz 引擎可能返回 200 + 登录重定向对象（而非 403），
    // 此时按认证失败处理，让 pull 走重新 login 指引而非崩溃
    if (!Array.isArray(tree)) {
        throw new ServiceUnavailableError(`页面清单响应异常（期望数组，实际：${JSON.stringify(tree).slice(0, 120)}），疑似 token 失效`, 401);
    }
    const flat = [];
    const walk = (nodes, parentName) => {
        for (const n of nodes ?? []) {
            if (n.Route) {
                flat.push({
                    route: n.Route,
                    id: n.Id ?? n.id ?? n.OutId ?? '',
                    outId: n.OutId ?? n.outId ?? n.Id ?? n.id ?? '',
                    name: n.DisplayName ?? n.Name ?? n.Route,
                    group: parentName,
                });
            }
            if (n.Children?.length)
                walk(n.Children, n.DisplayName ?? parentName);
        }
    };
    walk(tree ?? [], undefined);
    return flat;
}
/**
 * 单页 Schema：响应 Component 为 JSON 字符串，parse 后返回；非法 JSON 原样返回（保真不崩溃）。
 * 平台压力下会返回 200+错误体（OOM 对象/空串/502 HTML——2026-08-26 审计 483/488 页面中招）：
 * 错误形态指数退避重试 3 次（500/1500/3000ms，OOM 是并发压力，延迟后常可恢复），
 * 仍错抛自解释错误（上层降级沿用旧快照，不写坏数据）。
 */
export async function getPageSchema(ctx, apiPrefix, q) {
    const fetchOnce = async () => {
        const resp = await platformGet(ctx, apiPrefix, '/inbiz/api/services/front/engines/v3/page', { siteOutId: q.siteOutId, route: q.route, appId: q.appId, dataVersionId: q.dataVersionId });
        if (typeof resp?.Component !== 'string')
            return resp;
        try {
            return JSON.parse(resp.Component);
        }
        catch {
            return resp.Component;
        }
    };
    let schema = await fetchOnce();
    let err = detectPlatformError(schema);
    for (const delayMs of [500, 1500, 3000]) {
        if (!err)
            break;
        // 永久错误（coreErr:000002 页面已删）重试永不恢复：立即失败，不烧退避时间
        if (isPermanentPlatformError(err)) {
            throw new Error(`页面 ${q.route} Schema 拉取失败：${err}（永久错误，未重试）`);
        }
        await new Promise(r => setTimeout(r, delayMs));
        schema = await fetchOnce();
        err = detectPlatformError(schema);
    }
    if (err)
        throw new Error(`页面 ${q.route} Schema 拉取失败：${err}（已重试 3 次）。该页将沿用旧快照`);
    return schema;
}
/** 页面规则列表：路径参数用 route（实测 route 与 pageId 均可，route 是权威标识） */
export async function getBizflows(ctx, apiPrefix, appId, route) {
    const resp = await platformGet(ctx, apiPrefix, `/api/bizflows/${appId}/${route}`);
    return resp?.data ?? [];
}
/** 编排设计数据（jsCode/csharpCode 真正所在，Task 2 实测收敛） */
export async function getBizflowDesign(ctx, apiPrefix, refId) {
    const resp = await platformGet(ctx, apiPrefix, '/api/bizflows_design', { refId, isPublish: false });
    return resp?.data ?? null;
}
/** 公共编排列表（data.rows 解包） */
export async function getPublicFlows(ctx, apiPrefix, appId) {
    const resp = await platformGet(ctx, apiPrefix, '/api/public_flows', { appId });
    return resp?.data?.rows ?? [];
}
/**
 * 元数据列表通用形态。解包规则（实测）：
 *   /api/models 等：{data:{rows:[...]}}；/api/dictionary：{data:[...]}（data 直接是数组）；
 *   /edoc2Flow-web 流程：{code, details:{rows:[...]}}
 * 实测（2026-08-25 冒烟）：网关在并发压力下会瞬时降级返回 200+空 data——空结果短延迟重试一次，
 * 两次都空才接受（兼容新应用全部资源合法为 0 的场景）。
 */
async function listResource(ctx, apiPrefix, path, extra = {}) {
    const query = { group: '', pageIndex: 1, pageSize: 1000, key: '', timestamp: Date.now(), ...extra };
    const unpack = (resp) => {
        if (Array.isArray(resp?.data))
            return resp.data;
        return resp?.data?.rows ?? resp?.rows ?? resp?.details?.rows ?? [];
    };
    const fetchOnce = () => platformGet(ctx, apiPrefix, path, { ...query, timestamp: Date.now() });
    let rows = unpack(await fetchOnce());
    // 网关并发降级返回 200+空 data（实测 2026-08-26：性能计划真机实验 10 档也偶发、
    // 降级窗口可超 900ms）：指数退避（500/1000/2000/4000ms）重试最多 4 次，
    // 五次都空才接受（兼容新应用全部资源合法为 0 的场景；写盘侧守卫兜底防误删）
    for (let retry = 0; rows.length === 0 && retry < 4; retry++) {
        await new Promise(r => setTimeout(r, 500 * 2 ** retry));
        rows = unpack(await fetchOnce());
    }
    return rows;
}
export async function getModels(ctx, apiPrefix) {
    const rows = await listResource(ctx, apiPrefix, '/api/models');
    // 模型行字段 id/name/code（getModelList.tool 实证）；key 用 id（与 Schema 的 ModelKey=32hex 对应）
    return rows.map(r => ({ key: r.id ?? r.code, name: r.name, config: r }));
}
/**
 * 模型详情：字段清单在 config.Columns（D:\code\test model-cache.ts 实证）。
 * config 为 JSON 字符串 → parse 为对象放回 row（消除双重编码）；非法 JSON 保留原串、columns 空数组。
 */
export async function getModelDetail(ctx, apiPrefix, id) {
    const resp = await platformGet(ctx, apiPrefix, `/api/models/${id}`, { timestamp: Date.now() });
    const data = resp?.data;
    if (!data)
        return null;
    let parsed = data.config;
    if (typeof data.config === 'string') {
        try {
            parsed = JSON.parse(data.config);
        }
        catch { /* 保真保留原串 */ }
    }
    const columns = parsed?.Columns;
    return {
        row: { ...data, config: parsed },
        columns: Array.isArray(columns) ? columns : [],
    };
}
export async function getProcesses(ctx, apiPrefix) {
    const rows = await listResource(ctx, apiPrefix, '/edoc2Flow-web/process/manageMent/getProcessList');
    return rows.map((r) => ({
        id: String(r.id ?? ''),
        name: String(r.name ?? ''),
        key: r.key,
        groupId: r.groupId,
        groupName: r.groupName,
        procdefId: r.actReProcdefId,
        row: r,
    }));
}
export async function getProcessGroups(ctx, apiPrefix) {
    const rows = await listResource(ctx, apiPrefix, '/edoc2Flow-web/process/manageMent/getProcessGroup', { pageSize: 9999 });
    return rows.map((g) => ({
        id: String(g.id ?? ''),
        groupName: String(g.groupName ?? ''),
        sort: g.sort,
    }));
}
/** 流程设计：orgToken/loginName 实测留空即可；extPropJson 是 JSON 字符串 → parse（非法保真原串） */
export async function getProcessData(ctx, apiPrefix, id) {
    const resp = await platformGet(ctx, apiPrefix, '/edoc2Flow-web/process/design/getProcessData', { id, orgToken: '', loginName: '', timestamp: Date.now() });
    const d = resp?.details;
    if (!d)
        return null;
    let ext = d.extPropJson;
    if (typeof d.extPropJson === 'string') {
        try {
            ext = JSON.parse(d.extPropJson);
        }
        catch { /* 保真保留原串 */ }
    }
    return { xml: d.processDefinitionXml, ext };
}
export async function getDictionaries(ctx, apiPrefix) {
    return listResource(ctx, apiPrefix, '/api/dictionary');
}
export async function getDatasets(ctx, apiPrefix) {
    return listResource(ctx, apiPrefix, '/api/datasets');
}
export async function getEvents(ctx, apiPrefix) {
    return listResource(ctx, apiPrefix, '/api/events');
}
//# sourceMappingURL=api.js.map