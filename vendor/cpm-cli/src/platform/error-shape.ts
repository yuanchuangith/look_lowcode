// 平台错误响应形态检测（2026-08-26 快照审计：483/488 page.json 是 OOM/502/空串，
// 平台在并发压力下返回 200 + 错误体而非数据，必须在写盘前识别）。
/**
 * 检测数据是否为平台错误响应而非真实数据。
 * @returns 错误描述（如 "OutOfMemoryException"）；正常数据返回 null。
 * 实测形态（cpm-snapshot 审计）：
 *   ① {Error:{Message}} / {error:{message}}——后端异常（大小写两种形态都出现过）
 *   ② 空串 ""——网关吞掉响应体
 *   ③ HTML 错误页字符串（"<html>…502 Bad Gateway…"）——openresty 网关错误
 */
export function detectPlatformError(data) {
    if (data === null || data === undefined)
        return '响应为空';
    if (data === '')
        return '响应为空串（网关吞掉响应体）';
    if (typeof data === 'string' && /^\s*<html/i.test(data)) {
        const m = data.match(/<title>([^<]*)<\/title>/i);
        return m ? `网关错误页（${m[1]}）` : '网关错误页（HTML）';
    }
    if (typeof data === 'object' && !Array.isArray(data)) {
        const err = data.Error ?? data.error;
        if (err && typeof err === 'object') {
            const msg = err.Message ?? err.message;
            return typeof msg === 'string' && msg ? `平台错误响应（${msg.slice(0, 120)}）` : '平台错误响应（Error 对象）';
        }
    }
    return null;
}
/**
 * 平台错误是否为永久性（重试永不恢复）。
 * 实测唯一已知形态：coreErr:000002「不存在或已删除」——loadTreeList 残留的僵尸条目，
 * 页面在平台侧已删除（真机 55/488），与 OOM/网关降级（瞬时可重试恢复）相反。
 */
export function isPermanentPlatformError(errDesc) {
    return errDesc.includes('不存在或已删除');
}
