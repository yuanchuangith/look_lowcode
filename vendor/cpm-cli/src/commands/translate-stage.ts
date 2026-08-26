// 拉取管线翻译阶段（从 pull.ts 抽离：双链汇合后的统一翻译，防 pull.ts 超 300 行红线）。
// 两段：translateAll（页面/菜单/导航名：本地语言全量优先 + translateKeys 兜底）
// 与 translateTitles（组件树 title 批量翻译）。批量请求均经 gate 全局闸门。
// 另含 recoverLanguageRows：languages 被网关降级清空时从旧快照恢复翻译源。
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { buildComponentTree } from '../snapshot/tree-md.js';
import { translateKeys, collectI18nKeys, buildLocalTranslations, translateNamesLocal, } from '../snapshot/i18n.js';
import { collectDictI18nKeys, applyDictTranslations } from '../snapshot/dict-i18n.js';
/**
 * languages 降级恢复：languages/zh-cn.json 落盘形态恰是 {key: langText}——
 * 与 buildLocalTranslations 的输入对称可逆。返回重建的翻译源行；无旧快照/损坏返回 null。
 * 注意：仅用作翻译源（防 tree/bindings/目录名随兜底译文漂移），落盘仍走空数组 → writer 守卫保留全语种。
 */
export function recoverLanguageRows(outDir) {
    try {
        const map = JSON.parse(readFileSync(join(outDir, 'languages', 'zh-cn.json'), 'utf8'));
        if (!map || typeof map !== 'object' || Array.isArray(map))
            return null;
        const rows = Object.entries(map)
            .filter(([, v]) => typeof v === 'string' && v)
            .map(([key, langText]) => ({ key, kinds: [{ kindCode: 'zh-cn', langText }] }));
        return rows.length > 0 ? rows : null;
    }
    catch {
        return null;
    } // 无旧快照/损坏：不恢复
}
/** 聚合全部组件树 title 的 i18n key 并批量翻译（经 gate），写回各页 translations */
export async function translateTitles(ctx, prefix, pages, gate) {
    const titles = [];
    const walk = (nodes) => {
        for (const n of nodes) {
            if (n.title)
                titles.push(n.title);
            walk(n.children);
        }
    };
    for (const p of pages) {
        // 与 writer.schemaRootOf 相同的取根规则：content.schema ?? 根节点
        const s = p.pageSchema;
        walk(buildComponentTree(s?.content?.schema ?? s));
    }
    if (titles.length === 0)
        return; // 无标题不发批量翻译请求
    const map = await gate.run(() => translateKeys(ctx, prefix, titles));
    for (const p of pages) {
        // 翻译缺失的 key（哨兵标记）由 writer 写入 bindings.md 的 brokenI18nKeys 节
        p.translations = map;
    }
}
/**
 * 页面/菜单/导航名翻译：本地语言全量优先构建（快照自洽、少网络往返），
 * 缺失 key 一次批量 translateKeys 兜底（经 gate）。
 * 返回页面 summary 改写结果（目录/索引用）与完整翻译表（menuTranslations 传 writer，row 保真）。
 */
export async function translateAll(ctx, prefix, gate, pageData, summaries, shared) {
    const rawKeys = collectI18nKeys([
        ...summaries.map(p => p.name),
        ...(shared.menus ?? []).map(m => m.name),
        ...(shared.navigations ?? []).map(m => m.name),
    ]);
    const translations = buildLocalTranslations(shared.languages ?? [], rawKeys);
    const missing = rawKeys.filter(k => !translations.has(k));
    if (missing.length > 0) {
        for (const [k, v] of await gate.run(() => translateKeys(ctx, prefix, missing)))
            translations.set(k, v);
    }
    // 页面 summary 名按翻译改写；菜单/导航只传 Map 给 writer（row 保真）
    const namedSummaries = translateNamesLocal(summaries, translations);
    const summaryByName = new Map(summaries.map((p, i) => [p, namedSummaries[i]]));
    const pages = pageData.map(pd => ({ ...pd, summary: summaryByName.get(pd.summary) ?? pd.summary }));
    return { pages, menuTranslations: translations };
}
/**
 * 字典 value 占位符翻译（对齐 translateAll 模式）：
 * 本地语言全量优先构建（快照自洽、少网络往返），缺失 key 一次批量 translateKeys 兜底（经 gate）。
 */
export async function translateDicts(ctx, prefix, gate, dictionaries, languages) {
    const raws = collectDictI18nKeys(dictionaries);
    if (raws.length === 0)
        return dictionaries;
    const translations = buildLocalTranslations(languages, raws);
    const missing = raws.filter(k => !translations.has(k));
    if (missing.length > 0) {
        for (const [k, v] of await gate.run(() => translateKeys(ctx, prefix, missing)))
            translations.set(k, v);
    }
    return applyDictTranslations(dictionaries, translations).dicts;
}
