// 配置存储：.cpm/ 目录下的绑定/凭据/token 缓存读写。
// 纯 fs 同步 IO（配置文件极小，无需异步）；凭据永不进日志与错误输出（铁律）。
import { existsSync, mkdirSync, readFileSync, writeFileSync, appendFileSync, } from 'node:fs';
import { join, resolve } from 'node:path';
/** 凭据缺失错误：message 直接给 AI 下一步指引（AI-native 输出规范） */
export class CredentialsMissingError extends Error {
    constructor() {
        super('ERROR: 未提供平台凭据。请向用户索要账号密码后执行 cpm login --account <账号> --password <密码>，'
            + '或设置环境变量 CPM_ACCOUNT/CPM_PASSWORD。');
        this.name = 'CredentialsMissingError';
    }
}
/** .cpm 目录路径（隐藏目录，绑定与缓存的归属地） */
export function configDir(cwd) {
    return join(cwd, '.cpm');
}
/** 项目目录解析：--out 优先、缺省 cwd，相对 out 基于 cwd 解析，统一 resolve 为绝对路径（平铺式项目根，设计 §3.1） */
export function resolveProjectDir(opts) {
    return resolve(opts.cwd, opts.out ?? '.');
}
function readJson(path) {
    if (!existsSync(path))
        return null;
    try {
        return JSON.parse(readFileSync(path, 'utf8'));
    }
    catch {
        // 损坏的配置文件按"无配置"处理，让上层走重新 login 路径而非崩溃
        return null;
    }
}
export function loadConfig(cwd) {
    return readJson(join(configDir(cwd), 'config.json'));
}
export function saveConfig(cwd, c) {
    mkdirSync(configDir(cwd), { recursive: true });
    writeFileSync(join(configDir(cwd), 'config.json'), JSON.stringify(c, null, 2));
}
/**
 * 凭据解析。优先级：CLI 参数 > 环境变量 CPM_ACCOUNT/CPM_PASSWORD > .cpm/credentials.json。
 * 账号密码必须成对出现，半截凭据视为缺失（避免发出必失败的登录请求）。
 */
export function resolveCredentials(cwd, cli) {
    // 各层剔除显式 undefined 键，避免展开时用 undefined 覆盖低优先级层的有效值
    const clean = (o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined));
    const fromEnv = () => clean({
        account: process.env.CPM_ACCOUNT,
        password: process.env.CPM_PASSWORD,
    });
    const file = clean(readJson(join(configDir(cwd), 'credentials.json')) ?? {});
    const merged = { ...file, ...fromEnv(), ...clean(cli ?? {}) };
    if (!merged.account || !merged.password)
        throw new CredentialsMissingError();
    return { account: merged.account, password: merged.password };
}
export function loadTokenCache(cwd) {
    return readJson(join(configDir(cwd), 'token.json'));
}
export function saveTokenCache(cwd, t) {
    mkdirSync(configDir(cwd), { recursive: true });
    writeFileSync(join(configDir(cwd), 'token.json'), JSON.stringify(t, null, 2));
}
const GITIGNORE_LINES = ['.cpm/credentials.json', '.cpm/token.json'];
/** 向项目 .gitignore 追加缺失的敏感文件忽略行（幂等；顺带确保 .cpm/ 目录存在） */
export function ensureGitignore(cwd) {
    mkdirSync(configDir(cwd), { recursive: true });
    const path = join(cwd, '.gitignore');
    const existing = existsSync(path) ? readFileSync(path, 'utf8').split('\n') : [];
    const missing = GITIGNORE_LINES.filter(l => !existing.includes(l));
    if (missing.length === 0)
        return;
    const prefix = existing.length > 0 && existing[existing.length - 1].trim() !== '' ? '\n' : '';
    appendFileSync(path, prefix + missing.join('\n') + '\n');
}
//# sourceMappingURL=store.js.map