// cpm login：绑定平台与应用，登录换 token 并缓存。
// 输出直接 console、出错 process.exit(1)（命令层约定，由 cli.ts 调用）。
import { resolveProjectDir, resolveCredentials, saveConfig, saveTokenCache, ensureGitignore, loadConfig, CredentialsMissingError, } from '../config/store.js';
import { login as platformLogin } from '../platform/auth.js';
// 平台默认部署在 /gxp2 上下文（cpm.gxp2.com 实证）；换环境时改此默认
const DEFAULT_API_PREFIX = '/gxp2';
// 内部环境默认租户（参考仓库 .env 同源值）：单环境人人默认；
// CLI 无 --app/--site 参数（拍板 2026-08-26），将来多租户时再加回
const DEFAULT_APP_ID = '3a14fc0cb4cadc10c5626a7a4b1605bd';
const DEFAULT_SITE_OUT_ID = '3a14fc0cb4cd1807842c8157ef2fdd10';
/** 应用/站点解析链：已有绑定（重登不换绑） > 内置默认租户；已有绑定读项目目录（与落盘同源） */
function resolveBinding(projectDir) {
    const prev = loadConfig(projectDir);
    return {
        appId: prev?.appId ?? DEFAULT_APP_ID,
        siteOutId: prev?.siteOutId ?? DEFAULT_SITE_OUT_ID,
    };
}
export async function runLogin(opts) {
    const projectDir = resolveProjectDir(opts);
    // --out 模式的指引后缀：失败提示里的 cpm login 命令拼上 --out <目录>，AI 可直接照抄执行
    const outHint = opts.out ? ` --out ${opts.out}` : '';
    let creds;
    try {
        creds = resolveCredentials(projectDir, { account: opts.account, password: opts.password });
    }
    catch (e) {
        if (e instanceof CredentialsMissingError) {
            console.log(e.message);
            process.exit(1);
        }
        throw e;
    }
    let token;
    try {
        const r = await platformLogin(`${opts.url}${DEFAULT_API_PREFIX}`, creds);
        token = r.token;
    }
    catch (e) {
        console.log(`ERROR: 登录失败：${e.message}。请核对平台地址与账号密码后执行 cpm login${outHint} --url <平台地址> --account <账号> --password <密码>`);
        process.exit(1);
    }
    const { appId, siteOutId } = resolveBinding(projectDir);
    saveConfig(projectDir, {
        url: opts.url,
        apiPrefix: DEFAULT_API_PREFIX,
        appId,
        siteOutId,
    });
    saveTokenCache(projectDir, { token, obtainedAt: new Date().toISOString() });
    ensureGitignore(projectDir);
    // 绑定摘要（AI 靠它确认绑定成功与下一步；显示解析后的实际值，缺省时用户可见落了哪个应用）
    console.log(`已绑定平台 ${opts.url}${DEFAULT_API_PREFIX}（appId=${appId}${siteOutId ? ` site=${siteOutId}` : ''}），token 已缓存。`);
    console.log('下一步：执行 cpm pull 拉取快照。');
}
//# sourceMappingURL=login.js.map