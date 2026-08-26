import { getPublicFlows, getModels, getProcesses, getProcessGroups, getDictionaries, getDatasets, getEvents, getBizflowDesign, getModelDetail, getProcessData, } from '../platform/api.js';
import { getMenus, getNavigations } from '../platform/menus-api.js';
import { getInterfaces, getInterfaceGroups } from '../platform/interfaces-api.js';
import { getLanguages, getLanguageKinds } from '../platform/language-api.js';
import { extractCode } from '../snapshot/code-extract.js';
/** late 六路的错峰延迟（ms）：与首批 core 七路拉开，降低瞬时并发压力 */
const STAGGER_MS = 200;
/** core 七路：enrich（模型详情/公共编排/流程设计）的前置数据 */
export async function fetchSharedCore(ctx, prefix, appId, gate) {
    const via = (fn) => (gate ? gate.run(fn) : fn());
    const [publicBizflows, models, processes, processGroups, dictionaries, datasets, events] = await Promise.all([
        via(() => getPublicFlows(ctx, prefix, appId)),
        via(() => getModels(ctx, prefix)),
        via(() => getProcesses(ctx, prefix)),
        via(() => getProcessGroups(ctx, prefix)),
        via(() => getDictionaries(ctx, prefix)),
        via(() => getDatasets(ctx, prefix)),
        via(() => getEvents(ctx, prefix)),
    ]);
    return { publicBizflows, models, processes, processGroups, dictionaries, datasets, events };
}
/** late 六路：翻译源与写盘输入（菜单/导航/接口族/语言族），错峰 200ms */
export async function fetchSharedLate(ctx, prefix, appId, gate) {
    const via = (fn) => (gate ? gate.run(fn) : fn());
    const later = (fn) => new Promise(resolve => setTimeout(resolve, STAGGER_MS)).then(fn);
    const [menus, navigations, interfaces, interfaceGroups, languages, languageKinds] = await Promise.all([
        later(() => via(() => getMenus(ctx, prefix, appId))),
        later(() => via(() => getNavigations(ctx, prefix))),
        later(() => via(() => getInterfaces(ctx, prefix))),
        later(() => via(() => getInterfaceGroups(ctx, prefix))),
        later(() => via(() => getLanguages(ctx, prefix))),
        later(() => via(() => getLanguageKinds(ctx))),
    ]);
    return { menus, navigations, interfaces, interfaceGroups, languages, languageKinds };
}
/**
 * 模型详情并发补全（Phase 2：字段清单），请求经 gate 全局限流。
 * 失败记 failures 并按列表形态降级；平台无此模型（design=null）静默跳过不算失败。
 */
async function enrichModels(ctx, prefix, models, failures, gate) {
    return Promise.all(models.map(async (m) => {
        try {
            const d = await gate.run(() => getModelDetail(ctx, prefix, m.key));
            if (!d)
                return m; // null=平台无此模型，静默跳过不算失败
            return {
                ...m,
                config: d.row,
                comment: d.row.comment,
                code: d.row.code,
                columns: d.columns,
            };
        }
        catch (e) {
            failures.push({ type: 'model-detail', id: m.key, reason: String(e).slice(0, 100) });
            return m; // 失败按列表形态降级
        }
    }));
}
/**
 * 公共编排真代码补全（Phase 2 实测：列表 controlCode 80/81 是空模板，
 * 真代码在 bizflows_design，refId=公共编排 32 位 id；controlType=2 → C#，=1 → JS）。
 * 请求失败记 failures 并按 controlCode 形态降级；design 无 data 静默（writer 回退内联判定）。
 */
async function enrichPublicBizflows(ctx, prefix, flows, failures, gate) {
    return Promise.all(flows.map(async (pf) => {
        if (pf.status === false)
            return pf; // 禁用编排运行时不生效：不拉设计代码，清单仍展示（writer 标注禁用）
        try {
            const design = await gate.run(() => getBizflowDesign(ctx, prefix, pf.id));
            return { ...pf, codes: extractCode(design) };
        }
        catch (e) {
            failures.push({ type: 'public-bizflow-design', id: pf.code, reason: String(e).slice(0, 100) });
            return pf; // 失败按 controlCode 形态降级
        }
    }));
}
/**
 * 流程设计数据并发补全（两步走，同 enrichModels 模式）：
 * 列表行只有元数据，BPMN XML 与节点配置在 getProcessData。
 * 版本增量：procdefId 与上次 manifest 一致则跳过请求（designSkipped，writer keep 旧设计文件）；
 * 失败记 failures 降级为纯清单行且不记版本（下次自动重拉）；平台无设计数据（null）静默跳过。
 */
async function enrichProcesses(ctx, prefix, processes, failures, gate, prevVersions) {
    return Promise.all(processes.map(async (p) => {
        if (prevVersions[p.id] && prevVersions[p.id] === p.procdefId) {
            return { ...p, designSkipped: true }; // 版本未变：不请求，writer keep 上次设计文件
        }
        try {
            const design = await gate.run(() => getProcessData(ctx, prefix, p.id));
            return { ...p, design: design ?? undefined, versionTracked: true }; // null=平台无设计数据，同样可跳过
        }
        catch (e) {
            failures.push({ type: 'process-design', id: p.id, reason: String(e).slice(0, 100) });
            return p; // 失败不记版本，下次自动重拉
        }
    }));
}
/**
 * 共享链总编排：core 到齐即启三段 enrich（不等 late），late 并行拉取；
 * 全部请求经同一 gate。runPull 只调用本入口。
 */
export async function fetchSharedChain(ctx, prefix, appId, failures, gate, prevVersions) {
    const coreP = fetchSharedCore(ctx, prefix, appId, gate);
    const enrichedP = coreP.then(async (core) => {
        const [publicBizflows, models, processes] = await Promise.all([
            enrichPublicBizflows(ctx, prefix, core.publicBizflows, failures, gate),
            enrichModels(ctx, prefix, core.models, failures, gate),
            enrichProcesses(ctx, prefix, core.processes, failures, gate, prevVersions),
        ]);
        return { ...core, publicBizflows, models, processes };
    });
    const late = await fetchSharedLate(ctx, prefix, appId, gate);
    return { ...(await enrichedP), ...late };
}
