// 快照写入器：目录编排与文件落盘（设计文档 §6 契约的实现）。
// Phase 2：经 SnapshotWriter 增量写入（内容不变不重写）；manifest.pulledAt 语义为
// 「快照内容最后变化时间」——内容零变化时沿用旧值，保证零变化时全树 mtime/git diff 稳定。
import { join } from 'node:path';
import { existsSync, readFileSync } from 'node:fs';
import { displaySlug } from './code-extract.js';
import { buildComponentTree, renderTreeMd, flattenComponentTypes } from './tree-md.js';
import { buildPageComponents } from './components.js';
import { collectBindings, renderBindingsMd, extractEventSubs } from './bindings.js';
import { isMissing } from './i18n.js';
import { renderPagesIndex, renderModelUsage, renderComponentUsage, renderEventUsage, } from './indexes.js';
import { buildManifest } from './manifest.js';
import { SnapshotWriter } from './incremental.js';
import { syncSkills, stripCliAssetChanges } from './skills-sync.js';
import { syncPublicMethods } from './public-methods.js';
import { guardEmptyLists, buildDegradedFailure } from './list-guard.js';
import { stripOldValue } from './strip-old-value.js';
import { stripQueryFields } from './strip-query-fields.js';
import { assignProcessDirs, writeProcesses } from './writer-flows.js';
import { writePublicBizflows, writeResources, writeTopReadme } from './writer-resources.js';
import { writeMenus, writeNavigations } from './menus.js';
import { writeInterfaces } from './interfaces.js';
import { writeLanguages } from './language.js';
import { loadPageMetadata, metadataToIndexes, samePage, PAGE_META_FILE, PAGE_META_VERSION } from './page-meta.js';
export async function writeSnapshot(outDir, data) {
    // 项目目录化（Critical）：真实用户的项目目录常是 git 仓库且带宿主配置——
    // .cpm 项目缓存 / .git 仓库目录 / .claude 宿主配置均非快照内容，exclude 整棵保护
    const w = new SnapshotWriter(outDir, { exclude: ['.cpm', '.git', '.claude'] });
    // 流程目录分配先算一次：writePages（页面 bindings 反查用 dirOf）与 writeProcesses 共用
    const procDirs = assignProcessDirs(data.processes, data.processGroups);
    const diskMetadata = data.baselineMetadata ?? loadPageMetadata(outDir).metadata;
    const pagesMeta = writePages(w, outDir, data, procDirs.dirOf, diskMetadata);
    const pfCount = writePublicBizflows(w, outDir, data);
    const menusCount = writeMenus(w, outDir, data.menus ?? [], data.menuTranslations);
    const navCount = writeNavigations(w, outDir, data.navigations ?? [], data.menuTranslations);
    const ifaceCount = writeInterfaces(w, outDir, data.interfaceGroups ?? [], data.interfaces ?? []);
    const langCount = writeLanguages(w, outDir, data.languages ?? [], data.languageKinds ?? []);
    const counts = {
        menus: menusCount, navigations: navCount, interfaces: ifaceCount, languages: langCount,
        flows: writeProcesses(w, outDir, data, procDirs, pagesMeta.pageById),
        ...writeResources(w, outDir, data),
    };
    const fullCounts = {
        ...counts, pages: pagesMeta.metadata.length,
        bizflows: pagesMeta.metadata.reduce((n, p) => n + Number(p.bizflowCount ?? 0), 0),
        publicBizflows: pfCount,
    };
    writeNavigation(w, outDir, data, pagesMeta);
    // 页面降级聚合 failure（pages-degraded）：进 manifest 与报告——AI 读 manifest 即知快照新鲜度
    const degradedFailures = pagesMeta.degraded.length > 0
        ? [buildDegradedFailure(pagesMeta.degraded, data.pages.length)]
        : [];
    // 平台已删除页面聚合 failure：旧目录被清理（changes.removed 体现），AI 可知消失原因
    const deletedFailures = pagesMeta.deletedRoutes.length > 0 ? [{
            type: 'pages-deleted', id: 'pages',
            reason: `${pagesMeta.deletedRoutes.length} 个页面平台侧已删除（页面清单残留条目，schema 返回 coreErr:000002），` +
                `旧快照目录已清理；样例 ${pagesMeta.deletedRoutes.slice(0, 10).join('、')}` +
                `${pagesMeta.deletedRoutes.length > 10 ? ' …' : ''}`,
        }] : [];
    const pageFailures = [...degradedFailures, ...deletedFailures];
    // 已删页面名单：route → id 进 manifest（pull 下次双匹配命中即零请求跳过）
    const deletedPages = {};
    for (const p of data.pages) {
        if (p.deleted)
            deletedPages[p.summary.route] = p.summary.id;
    }
    // 健康度：counts 只是清单数量（488=平台有 488 页），health 区分本次成功/降级沿用/平台已删
    const health = {
        pages: {
            total: data.pages.length,
            ok: data.pages.length - pagesMeta.degraded.length - pagesMeta.deletedRoutes.length,
            degraded: pagesMeta.degraded.length,
            deleted: pagesMeta.deletedRoutes.length,
        },
    };
    // 列表空结果守卫：本次空但磁盘已有的资源 keep 旧文件（真机实验：网关降级空 data 不得静默清空快照）
    const { guardFailures, countOverrides } = guardEmptyLists(w, outDir, data);
    Object.assign(fullCounts, countOverrides);
    // manifest 最后写：finalize 先清理消失项得出变化统计；零变化时沿用旧 pulledAt
    const manifestPath = join(outDir, 'manifest.json');
    w.keep(manifestPath);
    // 项目目录自有内容保护（Critical）：.gitignore / AGENTS.md 是用户自有文件，非快照内容——
    // keep 注册防删（存在则免删，不存在无副作用）；.git / .claude 已由 exclude 整棵保护
    w.keep(join(outDir, '.gitignore'));
    w.keep(join(outDir, 'AGENTS.md'));
    // CLI 静态资产同步（skills、public-methods）：manifest 之后、finalize 之前——
    // 写入进 written 集不误删，包内已删文件被 finalize 清理
    const skillsStat = syncSkills(w, outDir);
    if (!skillsStat) {
        data.failures?.push({ type: 'skills-sync', id: 'skills', reason: 'CLI 包内 skill 资源缺失，已跳过同步（不影响快照数据）' });
    }
    const pmStat = syncPublicMethods(w, outDir);
    if (!pmStat) {
        data.failures?.push({ type: 'public-methods-sync', id: 'public-methods', reason: 'CLI 包内 public-methods 资产缺失，已跳过同步（不影响快照数据）' });
    }
    // finalize 先清理消失项得出变化统计；静态资产项剥离（其更新是 CLI 版本变化，非平台变化）；零变化时沿用旧 pulledAt
    const changes = stripCliAssetChanges(w.finalize(), [
        { prefix: 'skills/', stat: skillsStat },
        { prefix: 'public-methods/', stat: pmStat },
    ]);
    const pulledAt = resolvePulledAt(outDir, changes);
    // 流程版本表：可安全跳过的（请求成功/平台确认无数据/版本未变跳过）才记录，失败流程下次自动重拉
    const processVersions = {};
    for (const p of data.processes) {
        if ((p.designSkipped || p.versionTracked) && p.procdefId)
            processVersions[p.id] = p.procdefId;
    }
    w.writeJson(manifestPath, buildManifest({
        platform: data.platform, counts: fullCounts,
        failures: [...(data.failures ?? []), ...pageFailures], changes, pulledAt, processVersions, health,
        deletedPages: Object.keys(deletedPages).length > 0 ? deletedPages : undefined,
    }));
    return {
        counts: fullCounts,
        failures: [...(data.failures ?? []), ...pageFailures, ...guardFailures],
        outDir, changes, health,
    };
}
/** pulledAt 语义 = 快照内容最后变化时间：零变化沿用旧值（manifest 内容因此稳定） */
function resolvePulledAt(outDir, changes) {
    const old = join(outDir, 'manifest.json');
    const noChange = changes.added === 0 && changes.updated === 0 && changes.removed === 0;
    if (noChange && existsSync(old)) {
        try {
            return JSON.parse(readFileSync(old, 'utf8')).pulledAt;
        }
        catch { /* 损坏则重取 */ }
    }
    return new Date().toISOString();
}
/** 真实 Schema 形态为 content.schema（Component parse 后）；兼容直接传根节点 */
function schemaRootOf(pageSchema) {
    const s = pageSchema;
    return s?.content?.schema ?? s;
}
/** 页面目录：page.json / tree.md / components.json / bindings.md / bizflows/（无规则时整目录缺席） */
function writePages(w, outDir, data, processDirOf, diskMetadata) {
    const degraded = [];
    const deletedRoutes = [];
    const partial = data.mode === 'page';
    const target = partial ? data.pages[0]?.summary : null;
    const retained = partial ? diskMetadata.filter(meta => !samePage(meta, target)) : [];
    const metadata = [...retained];
    const occupiedDirs = new Set(retained.map(meta => meta.dir));
    // 单页刷新只允许替换目标页面。其余页面逐文件注册，避免 finalize() 把它们当作平台删除项。
    if (partial) {
        for (const meta of retained)
            w.keepDirDeep(join(outDir, meta.dir));
    }
    const usedSlugs = new Set(retained.map(meta => String(meta.dir).split('/').pop()));
    // 字典 id → 名称映射（bindings.md 字典段名称优先渲染；一次构建全页共用）
    const dictNames = new Map(data.dictionaries.filter(d => d?.id && d?.name).map(d => [String(d.id), String(d.name)]));
    for (const page of data.pages) {
        if (page.deleted) {
            // 平台已删除的残留条目：不写不 keep → finalize 清理旧目录（快照反映平台真实状态）
            deletedRoutes.push(page.summary.route);
            continue;
        }
        const oldMeta = diskMetadata.find(meta => samePage(meta, page.summary));
        let slug = displaySlug(page.summary.name, page.summary.route);
        // 名称未变时沿用稳定目录；名称改变时生成新目录，成功写完后由 finalize 清理旧目录。
        if (partial && oldMeta?.name === page.summary.name)
            slug = String(oldMeta.dir).split('/').pop();
        if (usedSlugs.has(slug) || occupiedDirs.has(`pages/${slug}`))
            slug = `${slug}-${page.summary.id || page.summary.outId}`; // 冲突追加页面标识（设计 §6）
        usedSlugs.add(slug);
        const dir = join(outDir, 'pages', slug);
        // id → 目录映射（degraded 页也填：flows README 关联页面列解析不缺页）
        if (page.degradedReason) {
            // 平台错误响应（已重试）：宁旧勿坏——keep 磁盘旧目录全部文件；无旧目录=首次拉取失败（缺席）
            degraded.push({
                route: page.summary.route, dir: oldMeta?.dir ?? `pages/${slug}`,
                reason: page.degradedReason,
                kept: oldMeta ? w.keepDirDeep(join(outDir, oldMeta.dir)) > 0 : false,
            });
            if (oldMeta)
                metadata.push(oldMeta);
            continue;
        }
        // 编辑器历史快照链（oldValue.oldValue…）剥离：落盘与后续组件树/绑定消费共用剥离后的数据
        stripOldValue(page.pageSchema);
        const schema = schemaRootOf(page.pageSchema);
        const nodes = buildComponentTree(schema);
        w.write(join(dir, 'tree.md'), renderTreeMd(nodes, page.translations) + '\n');
        // 机器可读页面结构：组件清单（白名单/binding/表格列）+ 主模型 + 统计（移植 D:\code\test parseComponentList）
        w.writeJson(join(dir, 'components.json'), buildPageComponents(page.pageSchema));
        const brokenI18nKeys = [...page.translations.entries()]
            .filter(([, v]) => isMissing(v)).map(([k]) => k);
        // 流程↔页面反向关联：流程 meta.pcPageKey = 页面 OutId（实测 2026-08-25，非 route）
        const processFlows = data.processes
            .filter(p => p.row.pcPageKey === page.summary.id)
            .map(p => ({
            id: p.id, name: p.name, dir: processDirOf.get(p.id) ?? '',
            version: p.row.actReProcdefIdRev,
            state: p.row.state,
        }));
        const bindings = collectBindings({
            pageSchema: page.pageSchema, // 原始响应：collectBindings 自取 content.form.model 与 content.schema
            flows: page.flows,
            codes: page.flows.map(f => f.codes ?? {}),
            brokenI18nKeys,
            publicBizflowCodes: data.publicBizflows.map(pf => ({ code: pf.code, name: pf.name })),
            processFlows,
            dictNames,
        });
        w.write(join(dir, 'bindings.md'), renderBindingsMd(page.summary.route, bindings) + '\n');
        // 查询字段定义剥离（dataCenter.queryField / columnConfig.queryFields 系）：与列定义
        // 高度重复的干扰数据；其中字典引用已固化进上方衍生文件——必须在 collectBindings 之后
        stripQueryFields(page.pageSchema);
        w.writeJson(join(dir, 'page.json'), page.pageSchema);
        const componentTypes = flattenComponentTypes(nodes); // 全树递归收集（修复：原只看顶层导致索引空）
        if (page.flows.length > 0)
            writePageBizflows(w, join(dir, 'bizflows'), page);
        // 事件订阅聚合（eventson 静态提取，规则粒度）
        const eventSubscriptions = extractEventSubs(page.flows).map(({ pageDir: _pageDir, ...sub }) => sub);
        const meta = {
            version: PAGE_META_VERSION,
            route: String(page.summary.route ?? ''),
            id: String(page.summary.id ?? ''),
            outId: String(page.summary.outId ?? page.summary.id ?? ''),
            name: String(page.summary.name ?? page.summary.route ?? ''),
            group: page.summary.group ?? null,
            dir: `pages/${slug}`,
            summary: `${page.summary.group ? `[${page.summary.group}] ` : ''}${page.summary.name}`,
            mainModel: bindings.mainModel ?? null,
            componentTypes,
            eventSubscriptions,
            bizflowCount: page.flows.length,
        };
        w.writeJson(join(dir, PAGE_META_FILE), meta);
        metadata.push(meta);
    }
    const indexes = metadataToIndexes(metadata);
    return { ...indexes, metadata, degraded, deletedRoutes };
}
/** 一条规则一个子目录：action.js/action.cs 按存在性缺席 */
function writePageBizflows(w, dir, page) {
    const lines = [
        `# ${page.summary.route} 业务规则清单`, '',
        '| code | 描述 | 启用 | 事件 | 代码 | id |',
        '|------|------|------|------|------|----|',
        ...page.flows.map(f => {
            let kinds = [f.codes?.js && 'js', f.codes?.cs && 'cs'].filter(Boolean).join('+');
            if (!kinds)
                kinds = f.state === false ? '（禁用，未拉取）' : '（平台无代码）';
            // 事件列：平台 event 字段非空直显；空则展示代码静态提取的订阅 key（eventson）
            const subs = extractEventSubs([f]).map(s => s.eventCode);
            const eventCell = f.event || (subs.length > 0 ? `订阅:${subs.join(',')}` : '-');
            // id 列：规则间 InvokeDynamicMethod("<id>",...) 以 id 互调，需可反查
            return `| ${f.code} | ${f.describe || '-'} | ${f.state ? '是' : '否'} | ${eventCell} | ${kinds} | ${f.id} |`;
        }),
    ];
    w.write(join(dir, 'README.md'), lines.join('\n') + '\n');
    for (const f of page.flows) {
        const flowDir = join(dir, displaySlug(f.describe || f.code, f.code));
        if (f.codes?.js)
            w.write(join(flowDir, 'action.js'), f.codes.js);
        if (f.codes?.cs)
            w.write(join(flowDir, 'action.cs'), f.codes.cs);
    }
}
/** 导航层：indexes 四件 + 顶层 README（manifest 由 writeSnapshot 主流程在 finalize 后写） */
function writeNavigation(w, outDir, data, pagesMeta) {
    const idx = join(outDir, 'indexes');
    if (pagesMeta.degraded.length > 0 && pagesMeta.metadata.length < data.pages.length) {
        // 索引守卫：降级页缺席会使索引退化为仅含成功页（如 488 页只剩 5 页），与 keep 的旧页面
        // 数据不一致——keep 旧索引，下次全部成功拉取时自然重建；README 不依赖页面数据照常写
        w.keepDirDeep(idx);
        writeTopReadme(w, outDir, data);
        return;
    }
    w.write(join(idx, 'pages.md'), renderPagesIndex(pagesMeta.indexEntries) + '\n');
    // 模型清单传索引：名称列（comment 中文注释优先）+ 未引用模型段（302 全模型覆盖）
    w.write(join(idx, 'model-usage.md'), renderModelUsage(pagesMeta.bindingPairs, data.models.map(m => ({
        key: String(m.key), name: String(m.name),
        comment: m.comment ?? m.config?.comment,
    }))) + '\n');
    w.write(join(idx, 'component-usage.md'), renderComponentUsage(pagesMeta.componentPairs) + '\n');
    // 事件订阅反向索引：eventson 订阅 key → 平台事件 eventCode 匹配名称（匹配不上为 '-'）
    const evtNameByCode = new Map(data.events
        .filter(e => e?.eventCode && e?.name).map(e => [String(e.eventCode), String(e.name)]));
    w.write(join(idx, 'event-usage.md'), renderEventUsage(pagesMeta.eventSubs.map(s => ({ ...s, eventName: evtNameByCode.get(s.eventCode) ?? '-' }))) + '\n');
    writeTopReadme(w, outDir, data);
}
//# sourceMappingURL=writer.js.map