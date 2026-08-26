// i18n key 批量翻译：{multilingual}global.i18n-xxx → 中文。
// 移植自 D:\code\test\src\tools\action-design-tools\multilingual-resolver.ts（去缓存，快照一次成型）。
// 接口实测（cpm.gxp2.com）：POST /api/inbizdatas/languages/zh-cn，body=纯 key 数组，
// 响应 { statusCode, data: [{key, value}] }。
// Task 12 翻译源统一后：本地语言全量（/api/language）优先构建，translateKeys 降级为缺失 key 兜底。
import { platformPost } from '../platform/http-client.js';
/** 翻译失败哨兵前缀：value 以此开头 = 该 key 缺失（bindings 列入 brokenI18nKeys） */
export const MISSING_PREFIX = '\u0000MISSING\u0000';
export function isMissing(value) {
    return typeof value === 'string' && value.startsWith(MISSING_PREFIX);
}
// 兼容三种形式：{multilingual}global.i18n-x / {multilingual}i18n-x / 裸 i18n-x
const I18N_RE = /(?:\{multilingual\}(?:global\.)?)?(i18n-[a-z0-9]+)/gi;
/** 命名占位检测（页面/菜单/导航名通用） */
const I18N_NAME_RE = /\{multilingual\}/;
/** 从原始串提取纯 key（导出复用：buildLocalTranslations 依赖同一提取规则） */
export function extractPureKeys(raws) {
    const pureToRaws = new Map();
    for (const raw of raws) {
        if (typeof raw !== 'string' || !raw)
            continue;
        I18N_RE.lastIndex = 0;
        let m;
        while ((m = I18N_RE.exec(raw)) !== null) {
            if (!pureToRaws.has(m[1]))
                pureToRaws.set(m[1], new Set());
            pureToRaws.get(m[1]).add(raw);
        }
    }
    return pureToRaws;
}
/** 收集含 {multilingual} 占位的原始串（页面/菜单/导航名通用），去重 */
export function collectI18nKeys(names) {
    return [...new Set(names.filter(n => typeof n === 'string' && I18N_NAME_RE.test(n)))];
}
/**
 * 从语言全量构建翻译 Map（实测：占位的裸 key 直接命中 /api/language，zh-cn 文本）。
 * 只返回命中的 raw→文本；未命中留给 translateKeys 兜底（Map 无哨兵值，语义干净）。
 */
export function buildLocalTranslations(rows, raws) {
    const result = new Map();
    const byKey = new Map<any, any>(rows.map(r => [r.key, r]));
    for (const raw of raws) {
        for (const pure of extractPureKeys([raw]).keys()) {
            const zh = byKey.get(pure)?.kinds?.find(k => k.kindCode === 'zh-cn')?.langText;
            if (typeof zh === 'string' && zh) {
                result.set(raw, zh);
                break;
            }
        }
    }
    return result;
}
/** 命名翻译（纯函数版，原 pull.ts translateNames 本地化）：命中改写；未命中剥前缀回退 */
export function translateNamesLocal(items, translations) {
    return items.map(p => {
        if (!I18N_NAME_RE.test(p.name))
            return p;
        const t = translations.get(p.name);
        if (t && !isMissing(t))
            return { ...p, name: t };
        return { ...p, name: p.name.replace(/^\{multilingual\}/, '') };
    });
}
/**
 * 批量翻译。返回 Map<原始串, 中文>；未翻译成功的原始串映射为
 * MISSING_PREFIX + 原始串（下游 isMissing 判定后列 brokenI18nKeys）。
 * 网络整体失败时不抛错（全部标记 missing，快照流程继续）。
 */
export async function translateKeys(ctx, apiPrefix, keys) {
    const result = new Map();
    const pureToRaws = extractPureKeys(keys);
    if (pureToRaws.size === 0)
        return result;
    let translated = new Map<string, string>();
    try {
        const resp = await platformPost(ctx, apiPrefix, `/api/inbizdatas/languages/zh-cn?timestamp=${Date.now()}`, [...pureToRaws.keys()]);
        translated = new Map((resp?.data ?? [])
            .filter(it => it && typeof it.key === 'string' && typeof it.value === 'string')
            .map(it => [it.key, it.value]));
    }
    catch {
        // 整体失败：下面统一按 missing 标记
    }
    for (const [pure, raws] of pureToRaws) {
        const value = translated.get(pure);
        for (const raw of raws) {
            result.set(raw, value !== undefined ? value : MISSING_PREFIX + raw);
        }
    }
    return result;
}
