// 菜单/导航快照渲染：树构建（实测 parentId→父 outId）+ 分组目录落盘 + README 树形索引。
// 全量保真：JSON 落平台原始 row；translations 仅用于目录名/README 渲染（不改 row 字段）。
import { join } from 'node:path';
import { slugify } from './code-extract.js';
import { isMissing } from './i18n.js';
/** 孤儿菜单（父节点不在列表）的虚拟分组名 */
const ORPHAN_GROUP = '未挂载';
/** 菜单名渲染：i18n 翻译优先；缺失回退剥离 {multilingual} 前缀（目录名不能带花括号，对齐 translateNames） */
export function menuDisplayName(name, translations) {
    const t = translations.get(name);
    if (t && !isMissing(t))
        return t;
    return name.replace(/^\{multilingual\}/, '');
}
/**
 * 树构建（实测规则）：
 *   parentId 指向父菜单 outId（非 id）；空 parentId 是顶层分组（组织/构建/…/系统）；
 *   父节点缺失的孤儿菜单合成「未挂载」虚拟分组（实测 4 条脏数据）。
 * 各层按 sort 升序；数据实测两层，children 递归防御多层。
 */
export function buildMenuTree(menus) {
    const byOutId = new Map(menus.map(m => [m.outId, m]));
    const childrenOf = new Map();
    const roots = [];
    const orphans = [];
    const bySort = (a, b) => (a.sort ?? 0) - (b.sort ?? 0);
    for (const m of menus) {
        if (!m.parentId) {
            roots.push(m);
            continue;
        }
        if (!byOutId.has(m.parentId)) {
            orphans.push(m);
            continue;
        }
        const arr = childrenOf.get(m.parentId) ?? [];
        arr.push(m);
        childrenOf.set(m.parentId, arr);
    }
    const build = (row) => ({
        row,
        children: (childrenOf.get(row.outId) ?? []).sort(bySort).map(build),
    });
    const tree = roots.sort(bySort).map(build);
    if (orphans.length > 0) {
        tree.push({
            row: { id: '', outId: '', parentId: '', name: ORPHAN_GROUP },
            children: orphans.sort(bySort).map(build),
        });
    }
    return tree;
}
/**
 * 菜单落盘：menus/<分组>/<菜单名>.json（叶子菜单全量 row；分组行是目录载体不单独落盘）+ menus/README.md。
 * 目录/文件名：中文名 slugify；组内同名追加完整 outId 防撞（对齐 flows 惯例，不截断保 AI 可检索）。
 * 多层子菜单平铺进分组目录，文件名拼接父名防撞。返回菜单总行数（含分组行，与真机 80 条对齐）。
 */
export function writeMenus(w, outDir, menus, translations = new Map()) {
    if (menus.length === 0)
        return 0;
    const root = join(outDir, 'menus');
    const usedGroups = new Set();
    const readme = [
        '# 菜单索引（管理端功能入口，按分组）', '',
        '每菜单一 JSON（平台原始行全量保真）。路由/内置页面是定位页面的关键；',
        '`未挂载` 分组 = 父节点缺失的孤儿菜单（平台侧脏数据）。', '',
    ];
    /** README 表格行渲染 */
    const readmeRow = (r, name, file) => `| ${file}.json | ${name} | ${r.route ?? '-'} `
        + `| ${r.pageRoute || r.linkUrl || '-'} | ${r.isVisible === false ? '否' : '是'} `
        + `| ${r.isHomePage ? '是' : '-'} | ${r.sort ?? '-'} |`;
    for (const group of buildMenuTree(menus)) {
        const gname = menuDisplayName(group.row.name, translations);
        let gslug = slugify(gname);
        if (usedGroups.has(gslug))
            gslug = `${gslug}-${group.row.outId}`;
        usedGroups.add(gslug);
        readme.push(`## ${gname}`, '', '| 文件 | 菜单 | 路由 | 内置页面/外链 | 可见 | 首页 | 排序 |', '|------|------|------|------|------|------|------|');
        const usedFiles = new Set();
        const walk = (nodes, parentName) => {
            for (const n of nodes) {
                const name = menuDisplayName(n.row.name, translations);
                const base = parentName ? `${parentName}-${name}` : name;
                let file = slugify(base);
                if (usedFiles.has(file))
                    file = `${file}-${n.row.outId}`;
                usedFiles.add(file);
                w.writeJson(join(root, gslug, `${file}.json`), n.row);
                readme.push(readmeRow(n.row, name, file));
                walk(n.children, base);
            }
        };
        walk(group.children, '');
        readme.push('');
    }
    w.write(join(root, 'README.md'), readme.join('\n') + '\n');
    return menus.length;
}
/** 导航落盘：navigations/<名称>.json + README（顶栏应用入口，按 sort 平铺）。返回写入条数。 */
export function writeNavigations(w, outDir, navs, translations = new Map()) {
    if (navs.length === 0)
        return 0;
    const dir = join(outDir, 'navigations');
    const used = new Set();
    const rows = navs.slice().sort((a, b) => (a.sort ?? 0) - (b.sort ?? 0)).map(n => {
        const name = menuDisplayName(n.name, translations);
        let file = slugify(name);
        if (used.has(file))
            file = `${file}-${n.outId}`;
        used.add(file);
        w.writeJson(join(dir, `${file}.json`), n);
        return `| ${file}.json | ${name} | ${n.route ?? '-'} | ${n.isHomePage ? '是' : '-'} `
            + `| ${n.cpmAppId ? n.cpmAppId.slice(0, 8) : '-'} | ${n.sort ?? '-'} |`;
    });
    w.write(join(dir, 'README.md'), [
        '# 导航索引（顶栏应用入口：工作台/文件/记录/培训/QMS…）', '',
        '与 menus/ 是两套数据；cpmAppId 前 8 位对应 /api/apps 应用（跨应用入口）。', '',
        '| 文件 | 名称 | 路由 | 首页 | 应用 | 排序 |', '|------|------|------|------|------|------|',
        ...rows, '',
    ].join('\n') + '\n');
    return navs.length;
}
