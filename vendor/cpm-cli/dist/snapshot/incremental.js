// 增量写入器（Phase 2 任务 6）：全量请求 + 内容哈希对比，只写变化的文件。
// 目的：二次 pull 后 mtime / git diff 只反映平台真实变化，AI 可据此识别「这次改了什么」。
// 用法：new SnapshotWriter(outDir, { exclude: ['.cpm', '.git', '.claude'] }) → 全部文件经 write/writeJson 落盘 → finalize() 清理消失项并返回变化统计。
import { writeFileSync, readFileSync, existsSync, mkdirSync, readdirSync, rmSync, statSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
/** 目录存在性确保（写文件前 mkdir -p） */
function ensureDir(path) {
    mkdirSync(dirname(path), { recursive: true });
}
/** 收集目录下全部文件相对路径（正斜杠，跨平台断言友好）；excluded 为顶层排除目录名，整棵跳过 */
function listFiles(root, excluded) {
    const acc = [];
    const walk = (d) => {
        for (const e of readdirSync(d, { withFileTypes: true })) {
            const p = join(d, e.name);
            if (e.isDirectory()) {
                if (d === root && excluded.includes(e.name))
                    continue; // 顶层排除目录整棵跳过
                walk(p);
            }
            else
                acc.push(relative(root, p).split(sep).join('/'));
        }
    };
    walk(root);
    return acc;
}
/** 删除空目录（自底向上，删净残留的幽灵目录）；excluded 目录不剪不删 */
function pruneEmptyDirs(root, excluded) {
    let hasEmpty = false;
    for (const e of readdirSync(root, { withFileTypes: true })) {
        if (!e.isDirectory())
            continue;
        if (excluded.includes(e.name))
            continue; // 排除目录不剪不删（可能是空的项目缓存目录，保留）
        const p = join(root, e.name);
        pruneEmptyDirs(p, excluded);
        if (readdirSync(p).length === 0) {
            rmSync(p, { recursive: true });
            hasEmpty = true;
        }
    }
    if (hasEmpty) { /* 父目录可能因子目录删除而变空，递归自然处理 */ }
}
export class SnapshotWriter {
    outDir;
    written = new Set(); // 本次写入的目标文件（绝对路径）
    added = 0;
    updated = 0;
    excluded;
    constructor(outDir, opts) {
        this.outDir = outDir;
        mkdirSync(outDir, { recursive: true });
        this.excluded = opts?.exclude ?? [];
    }
    /** 内容相同不写（mtime 不变）；返回 added/updated/unchanged */
    write(path, content) {
        this.written.add(path);
        ensureDir(path);
        if (existsSync(path) && readFileSync(path, 'utf8') === content)
            return 'unchanged';
        const result = existsSync(path) ? 'updated' : 'added';
        writeFileSync(path, content, 'utf8');
        if (result === 'added')
            this.added++;
        else
            this.updated++;
        return result;
    }
    /** JSON 落盘（2 空格缩进），同样走增量判定 */
    writeJson(path, data) {
        return this.write(path, JSON.stringify(data, null, 2));
    }
    /** 注册目标文件但不写入（如 finalize 后才生成的 manifest：防被当消失项删除） */
    keep(path) {
        this.written.add(path);
    }
    /**
     * 递归注册目录下全部文件（keep 的目录版）。
     * finalize 按文件路径匹配，故嵌套目录必须注册到文件级（list-guard 曾只 keep 一层，
     * menus 等嵌套资源的子目录文件在空降级守卫时仍会被当消失项删除）。
     * @returns 注册的文件数（目录不存在为 0）
     */
    keepDirDeep(dir) {
        if (!existsSync(dir))
            return 0;
        let n = 0;
        const walk = (d) => {
            for (const e of readdirSync(d, { withFileTypes: true })) {
                const p = join(d, e.name);
                if (e.isDirectory())
                    walk(p);
                else {
                    this.keep(p);
                    n++;
                }
            }
        };
        walk(dir);
        return n;
    }
    /**
     * 收尾：删除快照中不在本次写入集的文件与空目录，返回变化统计。
     * 目录内未注册的既有文件视为平台侧已消失（页面删除/规则删除等）。
     */
    finalize() {
        const removedPaths = [];
        for (const rel of listFiles(this.outDir, this.excluded)) {
            const abs = join(this.outDir, rel);
            if (!this.written.has(abs)) {
                rmSync(abs);
                removedPaths.push(rel);
            }
        }
        pruneEmptyDirs(this.outDir, this.excluded);
        return { added: this.added, updated: this.updated, removed: removedPaths.length, removedPaths };
    }
}
/** 变化统计的人类/AI 可读摘要行（pull 输出用） */
export function summarizeChanges(c) {
    if (c.added === 0 && c.updated === 0 && c.removed === 0)
        return '本次拉取与磁盘快照完全一致（零变化）';
    const parts = [`新增 ${c.added}`, `更新 ${c.updated}`, `删除 ${c.removed}`];
    return `本次变化：${parts.join('，')}`;
}
/** statSync 重导出（测试断言 mtime 用，避免测试直接依赖 fs 细节） */
export { statSync };
//# sourceMappingURL=incremental.js.map