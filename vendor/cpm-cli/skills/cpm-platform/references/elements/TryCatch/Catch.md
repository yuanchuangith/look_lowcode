> 来源：action-design-tools/nodes/TryCatch/Catch/knowledge.md（同步于 2026-08-25）

# CATCH 异常捕获

> 元件 Key: `Catch`

## 适用场景
捕获 Try 块内抛出的异常（运行时错误或显式 ThrowError），执行错误处理逻辑。用于表达 try-catch-finally 结构的 catch 分支。

## 参数逐条说明

| 参数 | 传什么 | 值从哪来 | 性质 |
|------|--------|----------|------|
| `exception`（输入，可选） | 捕获到的异常对象变量名，表达式对象 | **灵活**：变量名自己起（如 `exception`/`err`）；值为表达式对象 `paramTypes:"custom"`，code 即变量名。CATCH 块内通过它访问 `exception.message` | 自定义 |

> 无输出参数。纯结构节点（同时是 endMarker 关闭 try body + levelMarker 开启 catch body）。

## 使用说明
- 必须放在 `Try` 之后、`Finally`（如有）之前、`EndTry` 之前
- 一个 TRY 块最多有一个 Catch
- Catch 内可访问捕获到的异常对象，用于记录日志、弹窗提示、回滚等
- 添加 Catch 后结构为：`TRY {...} CATCH (exception) {...} 结束异常处理`

## 参数说明

### 输出参数
| 参数名 | 类型 | 必填 | acceptsExpression | 说明 |
|--------|------|------|-------------------|------|
| exception | object | 否 | true | 捕获到的异常对象变量名（表达式对象，paramTypes:custom，code 即变量名，如 exception） |

## 使用示例
```
用户："调用接口失败就弹个错误提示"
→ addNode(Try)
→ addNode(CallInterface, ...)
→ addNode(Catch)
→ addNode(OpenMessageDialog, 内容=exception.message)
```
伪代码：
```
TRY {
  result = 调用接口(...)
} CATCH (exception) {
  消息提示(内容="exception.message")
}
```

## 注意事项
- Catch 与所属 Try 共享同一个 EndTry 结束标记
- 在 Catch 内引用异常对象用表达式对象 {paramTypes:'custom', code:'exception', label:'exception', dataType:'object'}（code 可自定义为任意变量名）
- 若需无论是否异常都执行的清理逻辑，配合 Finally 使用
