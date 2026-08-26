/** 提取编译代码；空串/缺失视为该类代码缺席（写入器据此让文件缺席） */
export function extractCode(design) {
    if (!design)
        return {};
    const r: { js?: string; cs?: string } = {};
    if (design.jsCode && design.jsCode.trim())
        r.js = design.jsCode;
    if (design.csharpCode && design.csharpCode.trim())
        r.cs = design.csharpCode;
    return r;
}
/**
 * 目录命名安全化：保留中文/字母/数字/连字符，其余替换为 '-'；
 * 空结果返回 'unnamed'（目录名不能为空）。
 */
export function slugify(name) {
    const slug = name.replace(/[^\p{Script=Han}\p{L}\p{N}-]+/gu, '-').replace(/^-+|-+$/g, '');
    return slug || 'unnamed';
}
/** 中文名部分截断上限（超长 DisplayName 防目录名失控） */
const NAME_MAX = 64;
/**
 * Phase 2 命名规范：`中文名-短码`（如 `新增培训档案-xinzengpeixundangan`）。
 * 中文名经 slugify 安全化并截断；缺失/全非法时回退纯短码（不带悬挂连字符）。
 */
export function displaySlug(displayName, code) {
    const raw = (displayName ?? '').trim();
    if (!raw)
        return code; // 中文名缺失：纯短码，不带悬挂连字符
    const safeName = slugify(raw).slice(0, NAME_MAX).replace(/-+$/g, '');
    return safeName && safeName !== 'unnamed' ? `${safeName}-${code}` : code;
}
