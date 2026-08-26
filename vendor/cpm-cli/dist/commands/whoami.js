// cpm whoami：健康检查——输出当前绑定与 token 有效性。
// token 失效时给完整的重新 login 指引（AI-native 错误规范）。
import { loadConfig, loadTokenCache } from '../config/store.js';
import { buildCookie } from '../platform/auth.js';
import { getModels } from '../platform/api.js';
export function makeCtx(baseUrl, cookie, appId, siteOutId) {
    return { baseUrl, cookie, appId, siteOutId };
}
/**
 * @param outHint --out 模式的指引后缀（如 ' --out D:/proj'，由 cli.ts 入口拼装）：
 *   错误提示里的 cpm login 命令带上它 AI 可直接照抄；缺省空串，无 --out 时输出与旧版完全一致
 */
export async function runWhoami(projectDir, outHint = '') {
    const config = loadConfig(projectDir);
    if (!config) {
        console.log(`ERROR: 尚未绑定平台。请先执行 cpm login${outHint} --url <平台地址> --account <账号> --password <密码>`);
        process.exit(1);
    }
    const cached = loadTokenCache(projectDir);
    if (!cached?.token) {
        console.log(`ERROR: 无 token 缓存。请执行 cpm login${outHint} --url ${config.url} --account <账号> --password <密码>`);
        process.exit(1);
    }
    const ctx = makeCtx(config.url, buildCookie(cached.token, config.companyId, config.orgIdentityId), config.appId, config.siteOutId);
    try {
        // 用轻量端点验证 token（getModels 只拉一页元数据）
        await getModels(ctx, config.apiPrefix);
    }
    catch (e) {
        console.log(`ERROR: token 无效或已过期（${e.message.slice(0, 120)}）。请向用户索要平台账号密码后执行 cpm login${outHint} --url ${config.url} --account <账号> --password <密码>`);
        process.exit(1);
    }
    console.log(`绑定：${config.url}${config.apiPrefix} appId=${config.appId} site=${config.siteOutId || '(未设置)'}`);
    console.log(`token 有效（获取于 ${cached.obtainedAt}）。可执行 cpm pull 拉取快照。`);
}
//# sourceMappingURL=whoami.js.map