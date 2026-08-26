// 接口管理快照渲染：分组目录（还原嵌套）+ requestBody/responseBody parse 展开（拍板）+ README 索引。
// 权威源是全量列表（树只提供目录结构）；孤儿（无分组/分组已删）进「未挂载」。
import { join } from 'node:path';
import { slugify } from './code-extract.js';
const ORPHAN_GROUP = '未挂载';
const NAME_MAX = 64;
/** parse 展开核心：空串/非法 JSON 原样返回（原串本身即异常信号，不加标注字段） */
export function parseMaybeJson(raw) {
    if (!raw)
        return raw;
    try {
        return JSON.parse(raw);
    }
    catch {
        return raw;
    }
}
/** 接口行展开（拍板例外：仅 requestBody/responseBody 两字段 parse；其余字段原样保真） */
export function expandInterfaceRow(row) {
    return {
        ...row,
        requestBody: parseMaybeJson(row.requestBody ?? ''),
        responseBody: parseMaybeJson(row.responseBody ?? ''),
    };
}
/**
 * 分组目录树（实测规则）：
 *   树里 type:1 是分组、type:2 是条目元信息（忽略——详情以全量列表为准）；
 *   接口按 categoryId 挂组；无 categoryId 或指向不存在分组 → 「未挂载」（实测各 1 条）。
 * 树响应无 sort 字段，顺序按响应数组序。
 */
export function buildInterfaceTree(groups, rows) {
    const groupNodes = new Map();
    const collect = (n) => {
        if (n.type === 1)
            groupNodes.set(n.id, n);
        for (const c of n.children ?? [])
            collect(c);
    };
    groups.forEach(collect);
    const dirs = new Map();
    const dirOf = (n) => {
        if (!dirs.has(n.id)) {
            dirs.set(n.id, { name: n.title, children: [], rows: [] });
        }
        return dirs.get(n.id);
    };
    const roots = [];
    for (const n of groupNodes.values()) {
        const dir = dirOf(n);
        if (n.parentId && groupNodes.has(n.parentId))
            dirOf(groupNodes.get(n.parentId)).children.push(dir);
        else
            roots.push(dir);
    }
    const orphans = [];
    for (const r of rows) {
        const dir = r.categoryId ? dirs.get(r.categoryId) : undefined;
        if (dir)
            dir.rows.push(r);
        else
            orphans.push(r);
    }
    if (orphans.length > 0)
        roots.push({ name: ORPHAN_GROUP, children: [], rows: orphans });
    return roots;
}
/** 模式中文名（README 渲染用；row 内 modeType 不改） */
function modeLabel(modeType) {
    if (modeType === 'physical')
        return '物理';
    if (modeType === 'dynamic')
        return '动态';
    return '-';
}
/**
 * 接口落盘：interfaces/<分组>[/<子分组>]/<接口名>.json（expandInterfaceRow 展开后写）
 * + interfaces/README.md。文件名 slugify 截断 64；组内撞名追加完整 id（对齐 flows/menus 惯例）。
 * 无接口的分组不落目录（以列表为准，空分组无意义）。返回写入条数。
 */
export function writeInterfaces(w, outDir, groups, rows) {
    if (rows.length === 0)
        return 0;
    const root = join(outDir, 'interfaces');
    let count = 0;
    const readme = [
        '# 接口索引（集成-接口管理，按分组）', '',
        '每接口一 JSON（全量保真；requestBody/responseBody 已 parse 展开为对象，',
        '失败时保留原始字符串）。模式：物理=手写 URL 转发；动态=绑定物理表自动生成 CRUD。',
        '`未挂载` 分组 = 无分组或分组已删除的孤儿接口（平台侧脏数据）。', '',
    ];
    const writeDir = (dir, parentSlug, heading) => {
        const slug = slugify(dir.name);
        const dirSlug = parentSlug ? `${parentSlug}/${slug}` : slug;
        if (dir.rows.length > 0) {
            readme.push(`## ${heading}`, '', '| 文件 | 接口 | 模式 | 方法 | 路径/表 | 鉴权 |', '|------|------|------|------|------|------|');
            const used = new Set();
            for (const r of dir.rows) {
                let file = slugify(r.name).slice(0, NAME_MAX).replace(/-+$/g, '') || 'unnamed';
                if (used.has(file))
                    file = `${file}-${r.id}`;
                used.add(file);
                w.writeJson(join(root, dirSlug, `${file}.json`), expandInterfaceRow(r));
                count++;
                const target = r.modeType === 'dynamic' ? (r.modeTable || '-') : (r.requestUrl || '-');
                readme.push(`| ${file}.json | ${r.name} | ${modeLabel(r.modeType)} `
                    + `| ${r.requestType ?? '-'} | ${target} | ${r.isAuth ? '是' : '否'} |`);
            }
            readme.push('');
        }
        for (const c of dir.children)
            writeDir(c, dirSlug, heading ? `${heading} / ${c.name}` : c.name);
    };
    for (const dir of buildInterfaceTree(groups, rows))
        writeDir(dir, '', dir.name);
    w.write(join(root, 'README.md'), readme.join('\n') + '\n');
    return count;
}
