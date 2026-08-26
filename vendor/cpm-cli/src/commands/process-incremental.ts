// 流程版本增量：读取上次快照 manifest 的流程版本表（id → procdefId）。
// procdefId 形如 key:rev:defId（rev 变则串变），列表行自带，对比零成本。
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
export function loadPrevProcessVersions(outDir) {
    try {
        const m = JSON.parse(readFileSync(join(outDir, 'manifest.json'), 'utf8'));
        const v = m.processVersions;
        return v && typeof v === 'object' ? v : {};
    }
    catch {
        return {};
    } // 无 manifest / 损坏：视为首次，全量拉取
}
/** 上次已删页面名单（route → 页面 id）：pull 命中（双匹配）即零请求跳过 */
export function loadPrevDeletedPages(outDir) {
    try {
        const m = JSON.parse(readFileSync(join(outDir, 'manifest.json'), 'utf8'));
        const v = m.deletedPages;
        return v && typeof v === 'object' ? v : {};
    }
    catch {
        return {};
    } // 无 manifest / 损坏：视为首次，全量识别
}
