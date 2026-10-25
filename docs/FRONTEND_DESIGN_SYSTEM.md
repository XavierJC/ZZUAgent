# EduAgent 前端设计系统

日期：2026-10-25（Asia/Shanghai）。设计方向：Modern Academic / Minimal Technology。范围为现有 Vue3 学习端与课程构建端；不替换技术栈或评分业务。[实施报告](UI_UX_REFACTOR_REPORT.md) · [开源参考](OPEN_SOURCE_UI_REFERENCES.md)。

## 基础变量

权威定义为 `frontend/src/shared/design-tokens.css`。基础、工作台、笔记、练习、资料、知识体系、指南和发布样式已接入语义颜色变量；Markdown 保留本地 KaTeX 与代码高亮实现。组件内不重新定义主题色值。

| 用途 | Token | 浅色值 |
| --- | --- | --- |
| 页面 / 内容 / 次级内容 | `--color-background` / `--color-surface` / `--color-surface-muted` | #F7F9FC / #FFFFFF / #F1F5F9 |
| 主操作 / 悬停 | `--color-primary` / `--color-primary-hover` | #2563EB / #1D4ED8 |
| 选中背景 / 强调边框 | `--color-primary-soft` / `--color-primary-border` | #EFF6FF / #BFDBFE |
| 正文 / 次级正文 / 辅助文字 | `--color-text` / `--color-text-secondary` / `--color-text-subtle` | #1E293B / #475569 / #64748B |
| 边框 / 加强边框 | `--color-border` / `--color-border-strong` | #E2E8F0 / #CBD5E1 |
| 成功 / 警告 / 错误 | `--color-success` / `--color-warning` / `--color-danger` | #166534 / #92400E / #B91C1C |
| 深色代码背景 / 代码正文 | `--color-code-background` / `--color-code-text` | #172033 / #E2E8F0 |

状态各自有 `*-soft` 背景。遮罩、玻璃背景、阴影也集中定义。`--blue`、`--ink`、`--muted`、`--border`、`--radius` 作为旧样式兼容别名，继续指向新 Token。

正文 #1E293B 对白底约 14.6:1；辅助文字 #64748B 对白底约 4.76:1，主色与白色约 5.17:1。数值为颜色相对亮度计算，不能替代全部实际组合的无障碍审计。

## 字体、间距和形状

- 字体使用本机 Segoe UI / PingFang SC / Microsoft YaHei，代码使用 Cascadia Code / Consolas；不请求远程字体。
- 文字层级为 12 / 13 / 14 / 16 / 20 / 26 / 32px。旧产品界面中 8～11px 的辅助文字提升到 12px。正文和数学式保留自然行高，长公式、代码与表格各自横向滚动。
- 间距为 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40px；常用面板内边距 20～24px，手机 16～20px。旧业务布局的特定尺寸仍可保留，不为统一而修改数据或渲染逻辑。
- 圆角分为 6 / 10 / 14 / 20px，普通面板无重阴影。悬停只轻微抬升；尊重 `prefers-reduced-motion`。
- 常规控件至少 40px 高，手机主要按钮至少 44px。焦点使用蓝色描边，不只依靠背景变化。

## 共用组件与职责

| 组件 | 职责 / 复用 |
| --- | --- |
| `app/CourseShell.vue`、`app/AppSidebar.vue` | 共用学习/管理框架；桌面折叠、手机导航弹窗；旧路径仍可到达 |
| `shared/PageHeader.vue` | 页面标题、说明和主要操作；嵌套任务可用二级标题 |
| `shared/EmptyState.vue` | 笔记本空列表与搜索反馈，插槽保留明确下一步操作 |
| `shared/LearningProgress.vue` | 首页诊断覆盖、知识状态与普通练习范围计数；原生 progress 语义 |
| `shared/KnowledgeStatus.vue` | 正式证据、自评、原配置先修及当前建议的并列展示 |
| `shared/ProductDialog.vue`、`shared/useOverlayFocus.js` | 焦点进入、Tab 循环、Escape、关闭恢复、背景 inert 与滚动锁；支持嵌套计数 |
| 现有 `SourceDrawer.vue` | 版本快照、原页对照、PDF 页码链接；大屏内嵌区域和小屏模态保持不同键盘行为 |
| 现有 `ExerciseCard.vue` / `PracticeFeedback.vue` | 题目、输入与答案反馈；复用 Markdown/LaTeX；保留客观评分资格与主观作答边界 |
| `app/AuthoringSteps.vue` | 查看资料 → 整理知识 → 校对习题 → 检查发布的导航，不显示虚构完成状态 |

没有为每个标签、标题或边框新建组件。原领域状态、API、资料原件与 Markdown 渲染仍是相应业务模块的职责。

## 页面规则

首页先回答当前目标、已有证据、下一步，再展示笔记本和最近更新。诊断覆盖来自 `has_evidence`，不使用先验概率、笔记数量或普通练习次数制造掌握度。

笔记本固定主题、版本化资料、问答/练习/笔记任务。当前问答选择可展开查看；来源类别区分课程、上传、确认片段与私人笔记。`task` 是可选 hash 参数，刷新恢复原任务；旧链接仍默认问答。

练习显示当前范围真实可练题数、当前题号和已有结果的不同题目数，重复作答去重。草稿不计完成，过滤后的范围可能变化，明确标为“当前筛选范围”。跳到已有作答读取原会话；“再练一次”才创建新普通会话。

管理端共用主题和准备流程，提取记录默认折叠，运行/待确认任务可展开。原文与结构化编辑继续对照；发布条件、审核勾选及保存版本均由现有后端控制。

## 响应式与主题范围

- 1600px：完整侧栏，问答、资料和引用可三栏对照。
- 1280px：保留桌面侧栏，引用按需抽屉，主要内容维持可读宽度。
- 768px：侧栏改为菜单弹窗，原有辅助入口仍可到达。
- 375px：单列内容、资料任务切换、可滚动公式/代码、主要作答操作易点击。

本轮完整交付浅色主题。没有发布深色模式或系统跟随开关，避免旧编辑器、公式与原件对照未经验证便切换。后续如实现，应扩展同一语义 Token，并重新验收全部渲染区域。
