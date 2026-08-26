// CLI 静态资产同步：包内随版本分发的参考资源（cpm-platform skill、public-methods 公共方法参考源码）
// 释放到项目目录（设计 §3.4）。走同一 SnapshotWriter：写入进 written 集（finalize 不误删），
// 包内已删文件由 finalize 清理；变化统计经 stripCliAssetChanges 剥离——静态资产更新是 CLI 版本变化，不计入平台变化。
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
/** 包内 skill 资源根：src/snapshot/ 与 dist/snapshot/ 两种运行模式同路径 ../../skills（与版本号读取同构） */
export const SKILL_SRC = fileURLToPath(new URL('../../skills/cpm-platform', import.meta.url));
/** 递归收集目录下全部文件相对路径（正斜杠） */
export function listFiles(root) {
    const acc = [];
    const walk = (d) => {
        for (const e of readdirSync(d, { withFileTypes: true })) {
            const p = join(d, e.name);
            if (e.isDirectory())
                walk(p);
            else
                acc.push(relative(root, p).split(sep).join('/'));
        }
    };
    walk(root);
    return acc;
}
/**
 * 同步包内静态资产目录到 <destRoot>（CLI 是权威源，每次全量同步；内容不变不重写）。
 * 返回文件统计（stripCliAssetChanges 用）；包内资源缺失返回 null（调用方记 failure，不中断 pull）。
 */
export function syncStaticDir(w, srcRoot, destRoot) {
    let files;
    try {
        files = listFiles(srcRoot);
    }
    catch {
        return null;
    }
    const stat = { total: files.length, added: 0, updated: 0 };
    for (const rel of files) {
        const content = readFileSync(join(srcRoot, rel), 'utf8');
        const r = w.write(join(destRoot, rel), content);
        if (r === 'added')
            stat.added++;
        else if (r === 'updated')
            stat.updated++;
    }
    return stat;
}
/** 同步包内 skill 到 <projectDir>/skills/cpm-platform/（拍板 2026-08-26：CLI 是权威源，每次全量同步） */
export function syncSkills(w, projectDir) {
    return syncStaticDir(w, SKILL_SRC, join(projectDir, 'skills', 'cpm-platform'));
}
/**
 * 剥离 CLI 静态资产（skills/、public-methods/ 等）的变化统计：这些目录随 CLI 版本更新，不是平台变化。
 * stat=null 时该目录没有 added/updated 可扣减，但 removedPaths 里的前缀仍要剥离——
 * 否则 finalize 清理的旧资产文件会穿透计入平台变化统计。
 */
export function stripCliAssetChanges(c, assets) {
    let added = c.added, updated = c.updated;
    for (const { stat } of assets) {
        if (stat) {
            added -= stat.added;
            updated -= stat.updated;
        }
    }
    const prefixes = assets.map(a => a.prefix);
    const kept = c.removedPaths.filter(p => !prefixes.some(pre => p.startsWith(pre)));
    return { added, updated, removed: c.removed - (c.removedPaths.length - kept.length), removedPaths: kept };
}
