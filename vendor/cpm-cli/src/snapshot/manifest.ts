/** pulledAt 由调用方决定（增量零变化时沿用旧值），此处原样透传 */
export function buildManifest(d) {
    return { ...d };
}
