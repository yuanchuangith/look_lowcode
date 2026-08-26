// 多语言快照渲染（拍板：按语种映射）。kinds.json 保真字典；
// <kindCode>.json 是 key→langText 映射（索引性质，丢弃 appId/creationTime 等雷同元数据）。
import { join } from 'node:path';
/** 每语种一张映射；空 langText 的条目跳过（缺译不入映射，快照只存有效翻译） */
export function buildKindMaps(rows) {
    const maps = new Map();
    for (const row of rows) {
        for (const k of row.kinds ?? []) {
            if (!k?.kindCode || typeof k.langText !== 'string' || !k.langText)
                continue;
            const m = maps.get(k.kindCode) ?? {};
            m[row.key] = k.langText;
            maps.set(k.kindCode, m);
        }
    }
    return maps;
}
/** 语言落盘：languages/<kindCode>.json + kinds.json + README。返回条目数。 */
export function writeLanguages(w, outDir, rows, kinds) {
    if (rows.length === 0)
        return 0;
    const dir = join(outDir, 'languages');
    const maps = buildKindMaps(rows);
    // 字典缺席时用映射 key 兜底合成（保真优先：有 kinds 用 kinds）
    const kindList = kinds.length > 0 ? kinds : [...maps.keys()].map(code => ({ Id: '', Name: code, Code: code }));
    for (const [code, map] of maps) {
        w.writeJson(join(dir, `${code}.json`), map);
    }
    w.writeJson(join(dir, 'kinds.json'), kindList);
    w.write(join(dir, 'README.md'), [
        '# 多语言索引（系统-语言管理）', '',
        `全量 ${rows.length} 条语言条目，按语种拆分为 key→文本映射`,
        '（key = 占位符 \`{multilingual}global.<key>\` 的裸 key 部分）。',
        '查询方法：从菜单/页面/导航名拿 \`{multilingual}global.i18n-xxx\` → 剥掉前缀 → 在 \`zh-cn.json\` 查。', '',
        `- 条目 ${rows.length} 条 × 语种 ${maps.size}（${[...maps.keys()].join(' / ')}）`,
        '- 语种字典：kinds.json（含 IsDefault：默认语种）',
        '- 来源端点：GET /api/language（CPM 语言条目全量）；kinds 来自 languagengine', '',
    ].join('\n') + '\n');
    return rows.length;
}
