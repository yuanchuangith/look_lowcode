// 平台登录：表单编码 POST 换 token。
// 移植自 D:\code\test\test\__helpers__\auth.ts；编码规则经 2026-08-25 实测确认：
// account = "o" + base64(明文账号)、password = "b" + base64(明文密码)，与 auth.ts 样本逐字节一致。
import axios from 'axios';
export function encodeAccount(plain) {
    return `o${Buffer.from(plain, 'utf8').toString('base64')}`;
}
export function encodePassword(plain) {
    return `b${Buffer.from(plain, 'utf8').toString('base64')}`;
}
/**
 * 登录换取 token。url 为带上下文前缀的平台地址（如 http://cpm.gxp2.com/gxp2）。
 * 错误消息不含账号密码（凭据永不进日志与错误输出）。
 */
export async function login(url, creds) {
    const body = `account=${encodeURIComponent(encodeAccount(creds.account))}`
        + `&password=${encodeURIComponent(encodePassword(creds.password))}`;
    const resp = await axios.post(`${url}/api/auth/login`, body, {
        headers: {
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'x-requested-with': 'XMLHttpRequest',
        },
        timeout: 15000, validateStatus: () => true, maxRedirects: 0,
    });
    const setCookie = resp.headers['set-cookie'];
    const m = setCookie?.join(';').match(/token=([^;]+)/);
    if (!m) {
        throw new Error(`登录未返回 token（status=${resp.status}）。请向用户确认账号密码是否正确后执行 cpm login --account <账号> --password <密码>`);
    }
    return { token: m[1] };
}
/**
 * 拼装完整 Cookie。companyId/orgIdentityId 是租户上下文，部分接口缺失会被误判 401
 * （auth.ts 实证）；缺失时省略段。
 */
export function buildCookie(token, companyId, orgIdentityId) {
    const parts = [`token=${token}`];
    if (companyId)
        parts.push(`companyId=${companyId}`);
    if (orgIdentityId)
        parts.push(`orgIdentityId=${orgIdentityId}`);
    return parts.join('; ');
}
