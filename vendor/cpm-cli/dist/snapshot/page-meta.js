import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
export const PAGE_META_FILE = 'page-meta.json';
export const PAGE_META_VERSION = 1;
export class PartialBaselineError extends Error {
    code = 'PARTIAL_BASELINE_REQUIRED';
    details;
    constructor(message, details = []) {
        super(message);
        this.name = 'PartialBaselineError';
        this.details = details;
    }
}
function posixRelative(root, path) {
    return relative(root, path).split(sep).join('/');
}
function validateMeta(meta, expectedDir) {
    if (!meta || meta.version !== PAGE_META_VERSION)
        return 'version';
    for (const key of ['route', 'id', 'outId', 'name', 'dir']) {
        if (typeof meta[key] !== 'string')
            return key;
    }
    if (!Array.isArray(meta.componentTypes) || !Array.isArray(meta.eventSubscriptions))
        return 'derived-index-fields';
    if (expectedDir && meta.dir !== expectedDir)
        return 'dir';
    return null;
}
/** Read every page metadata record. Invalid or missing records are returned as baseline errors. */
export function loadPageMetadata(outDir) {
    const pagesDir = join(outDir, 'pages');
    const metadata = [];
    const errors = [];
    if (!existsSync(pagesDir))
        return { metadata, errors: ['pages/ 不存在'] };
    for (const entry of readdirSync(pagesDir, { withFileTypes: true })) {
        if (!entry.isDirectory())
            continue;
        const dir = join(pagesDir, entry.name);
        const relDir = posixRelative(outDir, dir);
        const path = join(dir, PAGE_META_FILE);
        if (!existsSync(path)) {
            errors.push(`${relDir}/${PAGE_META_FILE} 缺失`);
            continue;
        }
        try {
            const meta = JSON.parse(readFileSync(path, 'utf8'));
            const invalid = validateMeta(meta, relDir);
            if (invalid)
                errors.push(`${relDir}/${PAGE_META_FILE} 无效字段: ${invalid}`);
            else
                metadata.push(meta);
        }
        catch {
            errors.push(`${relDir}/${PAGE_META_FILE} 不是有效 JSON`);
        }
    }
    if (metadata.length === 0 && errors.length === 0)
        errors.push('pages/ 中没有页面元数据');
    return { metadata, errors };
}
function identityValues(value) {
    return [value?.route, value?.id, value?.outId].filter((v) => typeof v === 'string' && v.length > 0);
}
export function samePage(a, b) {
    const av = new Set(identityValues(a));
    return identityValues(b).some(v => av.has(v));
}
export function assertPartialBaseline(outDir, pageCatalog) {
    const loaded = loadPageMetadata(outDir);
    const errors = [...loaded.errors];
    for (const page of pageCatalog) {
        if (!loaded.metadata.some(meta => samePage(meta, page)))
            errors.push(`页面缺少元数据: ${page.route || page.id || page.outId}`);
    }
    if (errors.length > 0) {
        throw new PartialBaselineError('当前快照不是可安全单页更新的完整基线，请先执行一次全量 cpm pull。', errors.slice(0, 20));
    }
    return loaded.metadata;
}
export function metadataToIndexes(metadata) {
    const sorted = [...metadata].sort((a, b) => String(a.route).localeCompare(String(b.route)));
    const indexEntries = sorted.map(meta => ({
        route: meta.route,
        name: meta.name,
        dir: meta.dir,
        summary: meta.summary || meta.name,
    }));
    const bindingPairs = sorted.map(meta => ({
        dir: meta.dir,
        bindings: { mainModel: meta.mainModel ?? null },
    }));
    const componentPairs = sorted.map(meta => ({
        dir: meta.dir,
        componentTypes: meta.componentTypes,
    }));
    const eventSubs = sorted.flatMap(meta => meta.eventSubscriptions.map((sub) => ({
        ...sub,
        pageDir: meta.dir,
    })));
    const pageById = new Map();
    for (const meta of sorted) {
        const value = { name: meta.name, dir: meta.dir };
        if (meta.id)
            pageById.set(meta.id, value);
        if (meta.outId)
            pageById.set(meta.outId, value);
    }
    return { indexEntries, bindingPairs, componentPairs, eventSubs, pageById };
}
//# sourceMappingURL=page-meta.js.map