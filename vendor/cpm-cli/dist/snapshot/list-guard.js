// 列表资源写盘守卫（性能计划 Task 6 真机实验发现，2026-08-26）：
// 网关并发降级返回 200+空 data 时，若按空列表写盘，旧快照文件会被 finalize 当
// 「平台侧已删除」清理掉（静默数据丢失：真机实测 languages 1477 条被清空且 failures=0）。
// 守卫规则：列表本次为空 且 磁盘目录已有内容 → keep 旧目录全部文件、counts 沿用旧值、
// failures 显式标记（AI 可据此重拉）；新应用合法全空（磁盘无目录/空目录）不受影响。
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
/**
 * 降级页面聚合成一条 failure（2026-08-26 审计：483/488 页面为平台 OOM 响应，
 * 逐页记录会刷屏且 manifest 膨胀；聚合 + 样例 route 供 AI 判断重拉）。
 */
export function buildDegradedFailure(degraded, total) {
    const kept = degraded.filter(d => d.kept).length;
    const absent = degraded.length - kept;
    const sample = degraded.slice(0, 10).map(d => d.route).join('、');
    const reason = `${degraded.length}/${total} 页面为平台错误响应（已各重试 3 次），样例 ${sample}` +
        `${degraded.length > 10 ? ' …' : ''}；${kept} 个已沿用旧快照` +
        `${absent > 0 ? `，${absent} 个无旧快照（目录缺席）` : ''}，建议低峰期重拉`;
    return { type: 'pages-degraded', id: 'pages', reason };
}
/** 守卫覆盖的列表资源：SnapshotData 键名 → 快照目录名 */
const LIST_DIRS = {
    models: 'models', dictionaries: 'dictionaries', datasets: 'datasets', events: 'events',
    menus: 'menus', navigations: 'navigations', interfaces: 'interfaces', languages: 'languages',
};
/** 目录存在且非空（有旧快照内容可供保留） */
function hasContent(dir) {
    try {
        return existsSync(dir) && readdirSync(dir).length > 0;
    }
    catch {
        return false;
    }
}
/** 旧 manifest 的 counts（守卫时 counts 沿用旧值 = 磁盘实际内容数；缺失返回 undefined） */
function prevCounts(outDir) {
    try {
        const m = JSON.parse(readFileSync(join(outDir, 'manifest.json'), 'utf8'));
        const c = m.counts;
        return c && typeof c === 'object' ? c : undefined;
    }
    catch {
        return undefined;
    }
}
/**
 * 对「本次空 + 磁盘已有」的列表资源 keep 旧目录并记 failure。
 * 返回 counts 修正表（键 = 资源名，值 = 旧 counts 值），由 writeSnapshot 合并进报告。
 */
export function guardEmptyLists(w, outDir, data) {
    const guardFailures = [];
    const countOverrides = {};
    const prev = prevCounts(outDir);
    for (const [key, dirName] of Object.entries(LIST_DIRS)) {
        const items = data[key];
        if (!Array.isArray(items) || items.length > 0)
            continue; // 只守卫「本次为空」的路
        const dir = join(outDir, dirName);
        if (!hasContent(dir))
            continue; // 磁盘也无内容：新应用合法空，不守卫
        // keep 旧目录全部文件（防 finalize 清理；递归到文件级——嵌套目录如 menus/QMS 只 keep 一层会漏）；
        // README 由正常路径不写（空列表时 writeList 提前返回）
        w.keepDirDeep(dir);
        const kept = prev?.[key];
        if (typeof kept === 'number')
            countOverrides[key] = kept;
        guardFailures.push({
            type: 'list-empty-guard', id: key,
            reason: `本次拉取为空（疑似网关并发降级），已保留上次快照${typeof kept === 'number' ? ` ${kept} 条` : ''}，建议稍后重拉核对`,
        });
    }
    return { guardFailures, countOverrides };
}
//# sourceMappingURL=list-guard.js.map