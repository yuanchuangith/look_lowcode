> 来源：schema-tools/components/ProcessButton/knowledge.md（同步于 2026-08-25）

# 流程按钮

> 组件 Key: `ProcessButton`

## 适用场景

在表单中嵌入流程审批操作按钮。支持发起、同意、拒绝、退回、终止、加签、催办、草稿等操作，根据流程状态和用户权限自动过滤可用按钮。
与 EformButton 区别：EformButton 是普通表单按钮，ProcessButton 绑定流程引擎。

## 属性

> 公共属性（label、name、display、pattern）由系统自动注入。

| 名称 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| webbuttonConfig | `ButtonStructure[]` | `[initiate, approve, returnsBack, cancel]` | Web 端按钮配置列表（缺省由系统注入默认 4 按钮） |
| wapbuttonConfig | `ButtonStructure[]` | `[initiate, approve, returnsBack, cancel]` | WAP 端按钮配置列表（缺省由系统注入默认 4 按钮） |
| buttonVisible | `'visible' \| 'hidden'` | `'visible'` | 按钮整体可见状态 |
| tips | `string` | `''` | 审批意见输入框提示文字 |
| showCCmember | `boolean` | `false` | 是否显示抄送人选择 |
| showComment | `boolean` | `true` | 是否显示审批意见输入 |
| radius | `number` | `4` | 按钮圆角 |
| permissionBind | `any` | `null` | 权限绑定 |
| componentStyle | `object` | - | 组件样式配置 |
| decoratorStyle | `object` | - | 容器样式配置 |

## 复杂类型定义

### ButtonStructure

```typescript
interface ButtonStructure {
  action: string       // 按钮动作：initiate | approve | refuse | returnsBack | returnsStarter | cancel | signBefore | signAfter | urge | saveDraft
  name?: string        // 按钮显示名称（多语言 key）
  type?: string        // 按钮类型
  bgColor?: string     // 背景色，如 '#1989fa'
  fontColor?: string   // 字体色，如 '#ffffff'
  id?: string          // 按钮唯一标识，缺省为空字符串
  taskType?: string    // 任务类型，真实数据普遍为 'faqishenqing'
}
```

### 按钮动作类型

| 动作 | 描述 |
|------|------|
| `initiate` | 发起流程 |
| `approve` | 同意 |
| `refuse` | 拒绝 |
| `returnsBack` | 退回上一步 |
| `returnsStarter` | 退回发起人 |
| `cancel` | 终止流程 |
| `signBefore` | 前加签 |
| `signAfter` | 后加签 |
| `urge` | 催办 |
| `saveDraft` | 保存草稿 |

## 放置规则

- GridColumn
- GxpCard（直接放置）
- FormTab.TabPane

## 注意事项

- 按钮实际显示由流程引擎根据当前状态和用户权限自动过滤
- webbuttonConfig / wapbuttonConfig 不配置时，系统自动注入默认 4 个按钮（发起、同意、退回、终止），含 id/taskType/bgColor/fontColor
- ProcessButton 是 void 动作组件，装饰器为 Container（非数据字段的 FormItem），节点不带 title / x-validator
- 按钮点击有防抖处理，防止重复提交
- 需要配合流程引擎使用，单独放置不会触发流程操作
