// cpm pull：拉取管线编排（设计文档 §8.1 十步的实测修正版）。
// 性能计划（2026-08-25）：页面链与共享链双链并行；全部平台请求经 Semaphore 全局闸门（恒 ≤ concurrency）；
// 报告输出 durationMs 与 stageTimings（pages/translateTitles/shared/write 四阶段）。
import { loadConfig, loadTokenCache, saveTokenCache, resolveCredentials, resolveProjectDir, CredentialsMissingError, } from '../config/store.js';
import { login as platformLogin, buildCookie } from '../platform/auth.js';
import { ServiceUnavailableError } from '../platform/http-client.js';
import { getPageList, getPageSchema, getBizflows, getBizflowDesign } from '../platform/api.js';
import { extractCode } from '../snapshot/code-extract.js';
import { writeSnapshot } from '../snapshot/writer.js';
import { fetchSharedChain } from './fetch-shared.js';
import { translateAll, translateTitles, translateDicts, recoverLanguageRows } from './translate-stage.js';
import { loadPrevProcessVersions, loadPrevDeletedPages } from './process-incremental.js';
import { summarizeChanges } from '../snapshot/incremental.js';
import { Semaphore } from './async-pool.js';
/** 全局并发默认上限（性能计划：全进程平台请求经同一 Semaphore 闸门压到此值） */
export const DEFAULT_CONCURRENCY = 10;
/** 阶段计时包装：fn 完成后把耗时（ms）记入 timings[name] */
function timed(timings, name, fn) {
    const start = Date.now();
    return fn().finally(() => { timings[name] = Date.now() - start; });
}
/** token 解析：缓存优先，缺失则重登并回写缓存 */
async function resolveToken(cwd, url) {
    const cached = loadTokenCache(cwd);
    if (cached?.token)
        return cached.token;
    let creds;
    try {
        creds = resolveCredentials(cwd, undefined);
    }
    catch (e) {
        if (e instanceof CredentialsMissingError) {
            console.log(e.message);
            process.exit(1);
        }
        throw e;
    }
    const { token } = await platformLogin(`${url}/gxp2`, creds);
    saveTokenCache(cwd, { token, obtainedAt: new Date().toISOString() });
    return token;
}
/**
 * 单页拉取任务：Schema → 规则列表 → 逐规则设计代码（串行链，实测两步：bizflows + bizflows_design）。
 * 页面任务本身不占闸门槽——链内串行无并发语义，只有单个 HTTP 请求占槽（经 gate）。
 * Schema 为平台错误响应（OOM/空串/502，api 层已重试 3 次）时整页降级：
 * 不再拉规则（给压力中的平台减压），writer 沿用磁盘旧快照（宁旧勿坏）。
 */ async function fetchPage(ctx, prefix, appId, siteOutId, p, failures, gate, prevDeleted) {
    // 上次已判死的僵尸条目（route+id 双命中）：零请求直接标记 deleted；
    // 同 route 换 id（平台重建页面）不命中，照常拉取
    if (prevDeleted[p.route] === p.id) {
        return {
            summary: p, pageSchema: null, deleted: true,
            flows: [], translations: new Map(),
        };
    }
    let pageSchema;
    try {
        pageSchema = await gate.run(() => getPageSchema(ctx, prefix, { siteOutId, route: p.route, appId }));
    }
    catch (e) {
        // 平台 coreErr:000002「不存在或已删除」= loadTreeList 残留的僵尸条目：重拉永不恢复，
        // 标记 deleted 由 writer 清理旧目录（区别于 OOM/网关临时降级的沿用旧快照）
        const msg = String(e.message);
        const deleted = msg.includes('不存在或已删除');
        return {
            summary: p, pageSchema: null,
            deleted: deleted || undefined,
            degradedReason: deleted ? undefined : msg.slice(0, 120),
            flows: [], translations: new Map(),
        };
    }
    const flows = await gate.run(() => getBizflows(ctx, prefix, appId, p.route));
    // 禁用规则（state=false）运行时不生效：不拉设计代码，README 清单仍展示（writer 标注禁用）
    const active = flows.filter(f => f.state !== false);
    // 设计拉取失败不丢规则（代码缺席），但记录失败供审查
    const settled = await Promise.allSettled(active.map(f => gate.run(() => getBizflowDesign(ctx, prefix, f.id)).then(d => ({ ...f, codes: extractCode(d) }))));
    const byId = new Map();
    settled.forEach((r, i) => {
        if (r.status === 'fulfilled')
            byId.set(active[i].id, r.value);
        else
            failures.push({ type: 'bizflow-design', id: active[i].code, reason: String(r.reason).slice(0, 100) });
    });
    // 禁用/设计拉取失败的规则：保持清单原行（无 codes → 无代码目录）
    const flowList = flows.map(f => byId.get(f.id) ?? f);
    return {
        summary: p, pageSchema,
        flows: flowList,
        translations: new Map(),
    };
}
/** 全部页面并行拉取：在飞 HTTP 数由 gate 全局限流；单页失败进 failures 继续 */
async function fetchPages(ctx, prefix, appId, siteOutId, routes, failures, gate, prevDeleted) {
    const settled = await Promise.allSettled(routes.map(p => fetchPage(ctx, prefix, appId, siteOutId, p, failures, gate, prevDeleted)));
    const pages = [];
    settled.forEach((r, i) => {
        if (r.status === 'fulfilled')
            pages.push(r.value);
        else
            failures.push({ type: 'page', id: routes[i].route, reason: String(r.reason).slice(0, 100) });
    });
    return pages;
}
export async function runPull(opts) {
    const projectDir = resolveProjectDir(opts);
    // --out 模式的指引后缀：错误提示里的 cpm login 命令拼上 --out <目录>，AI 可直接照抄执行
    const outHint = opts.out ? ` --out ${opts.out}` : '';
    const config = loadConfig(projectDir);
    if (!config) {
        console.log(`ERROR: 尚未绑定平台。请先执行 cpm login${outHint} --url <平台地址> --account <账号> --password <密码>`);
        process.exit(1);
    }
    // 并发上限校验：非法值在任何网络请求前拒绝（进程闸门构造前提）
    const concurrency = opts.concurrency ?? DEFAULT_CONCURRENCY;
    if (!Number.isInteger(concurrency) || concurrency < 1) {
        console.log('ERROR: --concurrency 需为正整数。请检查参数，例如 --concurrency 10。');
        process.exit(1);
    }
    let token;
    try {
        token = await resolveToken(projectDir, config.url);
    }
    catch (e) {
        console.log(`ERROR: 登录失败：${e.message}。请执行 cpm login${outHint} --account <账号> --password <密码>`);
        process.exit(1);
    }
    const ctx = {
        baseUrl: config.url, cookie: buildCookie(token, config.companyId, config.orgIdentityId),
        appId: config.appId, siteOutId: config.siteOutId,
    };
    const failures = [];
    try {
        // 流程版本增量前提：先算输出目录并读上次版本表（无 manifest / 损坏视为首次全量）
        const outDir = projectDir; // 平铺式项目根即快照根（旧 cpm-snapshot/ 嵌套布局废弃，finalize 自然清理）
        const prevVersions = loadPrevProcessVersions(outDir);
        const prevDeleted = loadPrevDeletedPages(outDir);
        let pages = await getPageList(ctx, config.apiPrefix, config.appId, config.siteOutId);
        if (opts.page) {
            pages = pages.filter(p => p.route === opts.page || p.id === opts.page);
            if (pages.length === 0) {
                console.log(`ERROR: 未找到页面 ${opts.page}。请核对 --page 参数（route 或页面 ID），或去掉 --page 全量拉取。`);
                process.exit(1);
            }
        }
        // 双链并行编排（性能计划）：页面链与共享链无数据依赖；
        // 全部平台请求（含共享列表与翻译批量）经同一 gate，全程并发恒 ≤ concurrency。
        // 调度顺序（2026-08-26 实测优化）：共享链先创建——core 七路（轻、几十 ms）先入队，
        // 到齐即启 enrich（不等错峰的 late 六路）；pages 后入队与其公平竞争闸门。
        // 若 pages 先入队：433 个 schema 把列表挤到 ~10s 后执行、enrich 尾段拖成独立关键路径
        // （实测 shared 46.1s > pages 43.1s）。
        const t0 = Date.now();
        const timings = {};
        const gate = new Semaphore(concurrency);
        const sharedP = timed(timings, 'shared', () => fetchSharedChain(ctx, config.apiPrefix, config.appId, failures, gate, prevVersions));
        const pagesP = timed(timings, 'pages', () => fetchPages(ctx, config.apiPrefix, config.appId, config.siteOutId, pages, failures, gate, prevDeleted));
        const [pageDataRaw, shared] = await Promise.all([pagesP, sharedP]);
        // languages 降级恢复：本次空且磁盘旧快照有 zh-cn.json → 重建翻译源（防下游译文漂移到兜底）；
        // 落盘仍传空数组，由 writer 守卫保留全语种旧文件
        const languagesEmpty = Array.isArray(shared.languages) && shared.languages.length === 0;
        const recoveredRows = languagesEmpty ? recoverLanguageRows(outDir) : null;
        if (recoveredRows) {
            failures.push({
                type: 'languages-recovered', id: 'languages',
                reason: `本次拉取为空（疑似网关并发降级），翻译源已从旧快照恢复 ${recoveredRows.length} 条，语言文件由写盘守卫保留`,
            });
        }
        const translateSource = { ...shared, languages: recoveredRows ?? shared.languages };
        // 翻译段需要 pages（页面名 raw key / 组件树 title）与 shared.languages 两方数据：双链汇合后统一处理
        const { pages: pageData, menuTranslations, dictionaries } = await timed(timings, 'translateTitles', async () => {
            const r = await translateAll(ctx, config.apiPrefix, gate, pageDataRaw, pages, translateSource);
            await translateTitles(ctx, config.apiPrefix, r.pages, gate); // 组件树 title 批量翻译
            // 字典 value 占位符翻译（本地优先 + 兜底；翻译源用恢复后的 languages）
            const dicts = await translateDicts(ctx, config.apiPrefix, gate, shared.dictionaries, translateSource.languages ?? []);
            return { ...r, dictionaries: dicts };
        });
        const report = await timed(timings, 'write', () => writeSnapshot(outDir, {
            ...shared, pages: pageData, menuTranslations, dictionaries,
            platform: { url: config.url, appId: config.appId },
            failures,
        }));
        Object.assign(report, { durationMs: Date.now() - t0, stageTimings: timings });
        if (opts.json) {
            console.log(JSON.stringify(report));
        }
        else {
            const counts = Object.entries(report.counts).map(([k, v]) => `${k}=${v}`).join(' ');
            const stages = Object.entries(timings).map(([k, v]) => `${k} ${(Number(v) / 1000).toFixed(1)}s`).join(' / ');
            console.log(`拉取完成：${counts}${failures.length ? `，失败 ${failures.length} 项` : ''}（耗时 ${(report.durationMs / 1000).toFixed(1)}s：${stages}）`);
            // 健康度行（有降级/已删时显示）：AI 一眼看出快照有多少数据非本次新鲜拉取及原因
            const ph = report.health?.pages;
            if (ph && (ph.degraded > 0 || (ph.deleted ?? 0) > 0)) {
                const parts = [`数据健康：pages 本次成功 ${ph.ok}/${ph.total}`];
                if (ph.degraded > 0) {
                    parts.push(`${ph.degraded} 个为平台错误响应（OOM/网关）已沿用旧快照——建议低峰期重新 cpm pull`);
                }
                if ((ph.deleted ?? 0) > 0) {
                    parts.push(`${ph.deleted} 个平台侧已删除（清单残留条目），旧快照目录已清理`);
                }
                console.log(parts.join('；'));
            }
            // 增量变化摘要：AI 据此判断平台侧改了什么（git diff 同样只显示变化文件）
            console.log(summarizeChanges(report.changes));
            for (const f of failures)
                console.log(`  失败 [${f.type}] ${f.id}: ${f.reason}`);
            if (report.changes.removedPaths.length > 0) {
                const sample = report.changes.removedPaths.slice(0, 10).join('、');
                console.log(`  删除清单（前 10）：${sample}${report.changes.removedPaths.length > 10 ? ' …' : ''}`);
            }
            console.log(`AI 下一步：读 ${outDir.replace(/\\/g, '/')}/indexes/pages.md 定位页面`);
        }
        return report;
    }
    catch (e) {
        if (e instanceof ServiceUnavailableError && (e.status === 401 || e.status === 403)) {
            console.log(`ERROR: token 无效或已过期。请向用户索要平台账号密码后执行 cpm login${outHint} --url ${config.url} --account <账号> --password <密码>`);
            process.exit(1);
        }
        throw e;
    }
}
//# sourceMappingURL=pull.js.map