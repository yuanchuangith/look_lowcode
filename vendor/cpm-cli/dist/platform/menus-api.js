// 系统管理资源端点：菜单树 + 顶栏导航（2026-08-25 实测，样本 test/fixtures/real/menus-*.json）。
// 与 api.ts 分离：api.ts 已近 300 行红线，菜单族独立成文件。
import { platformGet } from './http-client.js';
/**
 * 菜单族列表通用拉取（导出共享：interfaces-api/language-api 复用，泛型 T 适配行类型）。
 * 解包差异（实测）：
 *   /api/menus → {statusCode, data: [...]}；/api/menus/navigations → {statusCode, data: {data: [...]}}；
 *   /api/language → {statusCode, data: {rows: [...]}}（第三个解包变体）
 * 空结果递增延迟重试最多 2 次（网关并发降级 200+空 data，对齐 api.ts listResource）。
 */
export async function fetchList(ctx, apiPrefix, path, extra = {}) {
    const unpack = (resp) => (Array.isArray(resp?.data) ? resp.data
        : Array.isArray(resp?.data?.data) ? resp.data.data
            : resp?.data?.rows) ?? [];
    const fetchOnce = () => platformGet(ctx, apiPrefix, path, { ...extra, timestamp: Date.now() });
    let rows = unpack(await fetchOnce());
    // 网关并发降级返回 200+空 data（对齐 api.ts listResource：指数退避重试最多 4 次）
    for (let retry = 0; rows.length === 0 && retry < 4; retry++) {
        await new Promise(r => setTimeout(r, 500 * 2 ** retry));
        rows = unpack(await fetchOnce());
    }
    return rows;
}
/**
 * 应用菜单树（扁平全量）。实测：appId 传 inbiz 应用 id 与 gxp2 应用 id 等价，
 * 统一传 config.appId；skipPerm=false + parentId=all 拉全量不分页。
 */
export async function getMenus(ctx, apiPrefix, appId) {
    return fetchList(ctx, apiPrefix, '/api/menus', { appId, skipPerm: false, parentId: 'all' });
}
/** 顶栏导航（应用入口：工作台/文件/QMS…；与菜单树是两套数据，实测 data 双层嵌套） */
export async function getNavigations(ctx, apiPrefix) {
    return fetchList(ctx, apiPrefix, '/api/menus/navigations', { pageIndex: 1, pageSize: 99990 });
}
//# sourceMappingURL=menus-api.js.map