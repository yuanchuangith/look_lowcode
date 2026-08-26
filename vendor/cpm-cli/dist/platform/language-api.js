// 多语言端点（系统-语言管理，2026-08-25 实测，样本 test/fixtures/real/language-*.json）。
// 两个端点：语言条目全量（1477 条，每条自带全部语种翻译）+ 语种字典（languagengine）。
import { platformGet } from './http-client.js';
import { fetchList } from './menus-api.js';
/** 语言条目全量（实测 data.rows 解包变体；无 searchKey 需求，一次 99990 拉齐） */
export async function getLanguages(ctx, apiPrefix) {
    return fetchList(ctx, apiPrefix, '/api/language', { page: 1, pageSize: 99990 });
}
/**
 * 语种字典。实测：路径 /inbiz/* 原样（不走 gxp2 前缀，故无 apiPrefix 参数）；
 * 响应是裸数组（无 statusCode 包装）；服务端要求 appid 头（buildHeaders 自动携带）。
 */
export async function getLanguageKinds(ctx) {
    const resp = await platformGet(ctx, '', '/inbiz/api/services/languagengine/v3/kind', { timestamp: Date.now() });
    return Array.isArray(resp) ? resp : (resp?.data ?? []);
}
//# sourceMappingURL=language-api.js.map