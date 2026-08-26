// 字典 value 的 i18n 解析：{multilingual}global.i18n-xxx → 中文。
// 纯函数（翻译网络在 translate-stage 管线做，本地语言全量优先 + translateKeys 兜底）；
// 64/199 字典 value 是占位符不可读的修复（2026-08-25 分析）。
import { isMissing } from './i18n.js';
const I18N_VALUE_RE = /^\{multilingual\}(?:global\.)?(i18n-[a-z0-9]+)$/i;
/** 收集全部 children value 中的 multilingual 原始串（去重；翻译管线的输入） */
export function collectDictI18nKeys(dictionaries) {
    const keys = new Set();
    for (const d of dictionaries) {
        for (const c of d?.children ?? []) {
            if (typeof c?.value === 'string' && I18N_VALUE_RE.test(c.value))
                keys.add(c.value);
        }
    }
    return [...keys];
}
/**
 * 应用翻译：value 命中则替换为中文；缺失（isMissing 哨兵）保留原串并把原始串收入 broken。
 * 返回新数组不改入参（快照管线纯函数语义）。
 */
export function applyDictTranslations(dictionaries, map) {
    const broken = [];
    const dicts = dictionaries.map(d => {
        if (!Array.isArray(d?.children))
            return d;
        const children = d.children.map((c) => {
            if (typeof c?.value !== 'string' || !I18N_VALUE_RE.test(c.value))
                return c;
            const t = map.get(c.value);
            if (t === undefined || isMissing(t)) {
                broken.push(c.value); // 缺翻译：保留原占位串，manifest 不记（字典级自查）
                return c;
            }
            return { ...c, value: t };
        });
        return { ...d, children };
    });
    return { dicts, broken };
}
