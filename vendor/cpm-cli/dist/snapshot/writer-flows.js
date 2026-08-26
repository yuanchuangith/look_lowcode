// 流程写入：目录分配（分组目录）+ 每流程 meta/process.xml/ext.json + flows/README.md 索引。
// 从 writer.ts 拆出（300 行硬指标）；行为与拆分前完全一致（Task 1 纯重构）。
import { join } from 'node:path';
import { existsSync, readdirSync } from 'node:fs';
import { slugify } from './code-extract.js';
/**
 * 流程目录分配（writeProcesses 与页面 bindings 共用）：
 * 按分组组织 `flows/<分组名>/<流程名>`，目录名纯中文名（同名撞车追加完整 id 兜底，不截断保 AI 可检索）。
 */
export function assignProcessDirs(processes, groups) {
    const byGroupMap = new Map();
    for (const p of processes) {
        const gid = p.groupId ?? '';
        const arr = byGroupMap.get(gid) ?? [];
        arr.push(p);
        byGroupMap.set(gid, arr);
    }
    const meta = new Map((groups ?? []).map(g => [g.id, g]));
    const gids = [...byGroupMap.keys()]
        .sort((a, b) => (meta.get(a)?.sort ?? 9999) - (meta.get(b)?.sort ?? 9999));
    const dirOf = new Map();
    const usedGroups = new Set();
    const byGroup = [];
    for (const gid of gids) {
        const list = byGroupMap.get(gid);
        const gname = meta.get(gid)?.groupName ?? list.find(p => p.groupName)?.groupName ?? '未分组';
        let gslug = slugify(gname);
        if (usedGroups.has(gslug))
            gslug = `${gslug}-${gid}`;
        usedGroups.add(gslug);
        const used = new Set();
        for (const p of list) {
            let slug = slugify(p.name);
            if (used.has(slug))
                slug = `${slug}-${p.id}`;
            used.add(slug);
            dirOf.set(p.id, `flows/${gslug}/${slug}`);
        }
        byGroup.push({ gname, list });
    }
    return { byGroup, dirOf };
}
/**
 * 流程落盘 + flows/README.md 索引。
 * 关联页面列解析为 `pages/目录（名称）`（pageById 以页面 OutId = 流程 pcPageKey 为键，实测 2026-08-25）；
 * 反查不到的（跨应用表单）显示原始 OutId +（本应用外）标注。
 */
export function writeProcesses(w, outDir, data, dirs, pageById) {
    const total = dirs.byGroup.reduce((n, g) => n + g.list.length, 0);
    if (total === 0)
        return 0;
    const root = join(outDir, 'flows');
    const readme = [
        '# 流程索引（按分组）', '',
        '每流程一目录：meta.json（元数据，含版本 actReProcdefIdRev/关联页面 pcPageKey=页面 OutId）',
        '→ process.xml（BPMN 节点链路：审批节点/条件/会签）→ ext.json（节点审批人/按钮/推送配置）。', '',
    ];
    for (const { gname, list } of dirs.byGroup) {
        const rows = list.map(p => {
            const rel = dirs.dirOf.get(p.id);
            const dir = join(outDir, rel);
            w.writeJson(join(dir, 'meta.json'), p.row);
            if (p.designSkipped && existsSync(dir)) {
                // 版本未变被跳过的流程：keep 上次写的设计文件，防 finalize 当消失项删除
                for (const f of readdirSync(dir))
                    w.keep(join(dir, f));
            }
            else {
                if (p.design?.xml)
                    w.write(join(dir, 'process.xml'), p.design.xml);
                if (p.design?.ext !== undefined)
                    w.writeJson(join(dir, 'ext.json'), p.design.ext);
            }
            const files = ['meta.json', ...designFilesOf(p, dir)].join(' ');
            const pk = p.row.pcPageKey;
            const pg = pk ? pageById.get(pk) : undefined;
            const pageCell = pg ? `${pg.dir}（${pg.name}）` : (pk ? `${pk}（本应用外）` : '-');
            return `| ${rel.split('/').pop()} | ${p.row.actReProcdefIdRev ?? '-'} | ${p.row.state ?? '-'} | ${pageCell} | ${files} |`;
        });
        readme.push(`## ${gname}`, '', '| 目录 | 版本 | 状态 | 关联页面 | 文件 |', '|------|------|------|------|------|', ...rows, '');
    }
    w.write(join(root, 'README.md'), readme.join('\n') + '\n');
    return total;
}
/** 流程目录文件清单（README files 列）：正常按 design 存在性；skipped 从磁盘读既有文件（顺序与正常形态一致） */
function designFilesOf(p, dir) {
    if (!p.designSkipped) {
        return [p.design?.xml && 'process.xml', p.design?.ext !== undefined && 'ext.json']
            .filter(Boolean);
    }
    if (!existsSync(dir))
        return []; // 目录缺失（如手动清理）：仅 meta.json
    const names = readdirSync(dir).filter(f => f !== 'meta.json');
    const order = ['process.xml', 'ext.json']; // 与正常写入顺序一致，保证 README 内容稳定
    return [...order.filter(f => names.includes(f)), ...names.filter(f => !order.includes(f))];
}
//# sourceMappingURL=writer-flows.js.map