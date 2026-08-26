// 接口管理端点（集成-接口管理，2026-08-25 实测，样本 test/fixtures/real/interface-*.json）。
// 拉取只需两个请求：分组树（目录结构）+ 全量列表（每条自带详情，113 条/178KB 无分页）。
// GET /api/interfaces/table 与 tablecolumn 仅编辑器下拉用，不拉（实测结论 14）。
import { platformPost } from './http-client.js';
import { fetchList } from './menus-api.js';
/** 分组树。实测：POST（不是 GET），请求体不敏感（{}/空均 200）；顺序即平台展示序，无 sort 字段 */
export async function getInterfaceGroups(ctx, apiPrefix) {
    const resp = await platformPost(ctx, apiPrefix, `/api/interface_groups/tree?timestamp=${Date.now()}`, {});
    return (resp?.data ?? []).filter((n) => n && typeof n === 'object');
}
/** 接口全量列表（权威源：含无分组/孤儿条目；树只有 111 条而列表 113 条） */
export async function getInterfaces(ctx, apiPrefix) {
    return fetchList(ctx, apiPrefix, '/api/interfaces');
}
