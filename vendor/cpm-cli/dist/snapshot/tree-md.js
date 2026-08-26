// 组件树生成与 tree.md 渲染。
// buildComponentTree 移植自 D:\code\test\src\tools\schema-tools\schema-helpers.ts（buildComponentTree）：
// 无 name 的根/包装层用占位名保住子树，无 name 无子树的叶子丢弃。
import { isMissing, MISSING_PREFIX } from './i18n.js';
/** title 提取：Formily 的 title.value 优先，其次 title 字符串，最后组件 props 里的可读标签 */
export function extractTitle(node) {
    const t = node.title;
    if (typeof t === 'object' && t !== null && typeof t.value === 'string')
        return t.value;
    if (typeof t === 'string' && t)
        return t;
    const props = node['x-component-props'] ?? {};
    return props.cardTitle ?? props.tab ?? props.title ?? props.label ?? '';
}
function toTreeNode(node, depth) {
    const componentType = node['x-component'] || '';
    const rawName = node.name || '';
    const isContainer = node.properties && typeof node.properties === 'object'
        && Object.keys(node.properties).length > 0;
    const children = isContainer
        ? Object.values(node.properties)
            .map(child => toTreeNode(child, depth + 1))
            .filter((c) => c !== null && !!c.name)
        : [];
    // 无 name：根节点用 root 承载子树；中间层保住有内容的子树；空叶子丢弃（移植源行为）
    if (!rawName) {
        if (depth === 0 && children.length > 0)
            return mkNode('root', componentType, node, children);
        if (children.length > 0)
            return mkNode(`_anonymous_${depth}`, componentType, node, children);
        return null;
    }
    return mkNode(rawName, componentType, node, children);
}
function mkNode(name, componentType, node, children) {
    return { name, componentType, title: extractTitle(node), children };
}
/** 入参为 pageSchema.content.schema；返回多根节点（根无 name 时用 root 占位） */
export function buildComponentTree(schema) {
    if (!schema || typeof schema !== 'object')
        return [];
    const root = toTreeNode(schema, 0);
    return root ? [root] : [];
}
/** markdown 缩进列表：`- name (EformInput) 厂区ID`；title 优先用翻译结果，missing 哨兵剥掉后展示原串 */
export function renderTreeMd(nodes, translated) {
    const lines = [];
    const render = (n, depth) => {
        let title = n.title;
        const t = translated.get(n.title);
        if (t !== undefined)
            title = isMissing(t) ? t.slice(MISSING_PREFIX.length) : t;
        const label = title ? ` ${title}` : '';
        lines.push(`${'  '.repeat(depth)}- ${n.name}${n.componentType ? ` (${n.componentType})` : ''}${label}`);
        n.children.forEach(c => render(c, depth + 1));
    };
    nodes.forEach(n => render(n, 0));
    return lines.join('\n');
}
/** 全树组件类型去重清单（component-usage 索引用；修复：只看顶层 nodes 导致索引全空——首层是无类型的 root） */
export function flattenComponentTypes(nodes) {
    const acc = new Set();
    const walk = (n) => {
        if (n.componentType)
            acc.add(n.componentType);
        n.children.forEach(walk);
    };
    nodes.forEach(walk);
    return [...acc];
}
//# sourceMappingURL=tree-md.js.map