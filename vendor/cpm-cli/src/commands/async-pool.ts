// 并发限流原语（性能计划 2026-08-25）：
// 原嵌套 asyncPool（外层 5 页 × 内层 5 规则峰值 25 不可控）已由 Semaphore 全局闸门取代并删除；
// Semaphore 把全进程平台请求压在同一上限内（默认 10，--concurrency 可调）。
/** 全局并发闸门：最多 limit 个 fn 同时执行。用于把全进程平台请求压在同一上限内。 */
export class Semaphore {
    limit;
    active = 0;
    waiters = [];
    constructor(limit) {
        this.limit = limit;
    }
    async run(fn) {
        if (this.active >= this.limit)
            await new Promise(r => this.waiters.push(r));
        this.active++;
        try {
            return await fn();
        }
        finally {
            this.active--;
            this.waiters.shift()?.();
        }
    }
}
