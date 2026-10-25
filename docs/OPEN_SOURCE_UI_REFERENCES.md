# 开源 UI 参考与代码归属

日期：2026-10-25（Asia/Shanghai）。本轮实际阅读五个项目的前端源码、组件结构及许可证；未运行第三方应用，也未把其运行时接入 EduAgent。前三个沿用此前已下载的固定源码，另外两个按本轮获取的固定提交阅读。[上轮归属记录](THIRD_PARTY_REFERENCES.md)继续保留。

## 固定版本与实际参考文件

| 项目 | 固定 commit / 许可证 | 实际阅读的前端文件 | 采用的原则与本地落点 |
| --- | --- | --- | --- |
| [Open Notebook](https://github.com/lfnovo/open-notebook) | `a0f6f3081ae06328f0a451b3a3ef2959ca25721d` · [MIT](https://github.com/lfnovo/open-notebook/blob/a0f6f3081ae06328f0a451b3a3ef2959ca25721d/LICENSE) | `frontend/src/app/(dashboard)/notebooks/[id]/page.tsx`、`components/SourcesColumn.tsx`、`components/ChatColumn.tsx` | 来源、聊天、笔记围绕稳定 Notebook 组织；桌面列与手机任务切换。增强 `NotebookPage` 的任务恢复、范围摘要和练习衔接 |
| [DeepTutor](https://github.com/HKUDS/DeepTutor) | `a31d82624c27d75f4e771d4fcb78dce16470b383` · [Apache-2.0](https://github.com/HKUDS/DeepTutor/blob/a31d82624c27d75f4e771d4fcb78dce16470b383/LICENSE) | `web/components/layout/AppShell.tsx`，并核对既有 sidebar 文件结构 | 框架统一、窄屏抽屉与分任务工作区。EduAgent 用 Vue `AppSidebar` 和已有 `ProductDialog` 独立实现，保留本机作用域与原状态生命周期 |
| [nano-NotebookLM](https://github.com/ArthurYangX/nano-NotebookLM) | `ed968a74bff81fd8dc24def0de4346bb90e1f92b` · [Apache-2.0](https://github.com/ArthurYangX/nano-NotebookLM/blob/ed968a74bff81fd8dc24def0de4346bb90e1f92b/LICENSE) | `frontend/reader.jsx` 中 `ChunkBlock`、`DocumentTextBody`、PDF frame / `activePage` 路径 | 引用保持文档和页面上下文，回答与原页对照。`SourceDrawer` 保留真实引用快照，PDF 原版本链接追加 `#page=N`；没有移植其 React reader 或伪造文本高亮 |
| [Exameow](https://github.com/heshengtao/exameow) | `ab792a9ae961a128de664b17268cd062587bb95e` · [Apache-2.0](https://github.com/heshengtao/exameow/blob/ab792a9ae961a128de664b17268cd062587bb95e/LICENSE) | `frontend/src/components/practice/QuestionCard.vue`、`AnswerSheet.vue`，既有 `PracticeView.vue`、practice store 对照 | 单题、题号导航与反馈分开。`ExerciseDesk` 加入按题去重的真实范围计数、上一题/下一题与草稿保存；保留 EduAgent 普通练习服务，不采用生成题或模型主观评分 |
| [Adaptive Knowledge Graph](https://github.com/MysterionRise/adaptive-knowledge-graph) | `0f4841407778421cfc793e1f1f091eb60c1a870c` · [MIT](https://github.com/MysterionRise/adaptive-knowledge-graph/blob/0f4841407778421cfc793e1f1f091eb60c1a870c/LICENSE) / [NOTICE](https://github.com/MysterionRise/adaptive-knowledge-graph/blob/0f4841407778421cfc793e1f1f091eb60c1a870c/NOTICE) | `frontend/components/KnowledgeGraph.tsx`、`LearningPath.tsx` | 当前概念、先修和学习动作需在同一上下文可见。独立实现 `KnowledgeStatus` 可访问列表，以原五点配置展示先修；未引入 Cytoscape、Neo4j、其掌握度阈值或图检索 |

## 三类使用方式

1. **直接复制或改造的第三方代码：本轮无。** 因此没有新增需随产品分发的第三方代码段、Logo、品牌图形或 NOTICE 内容。
2. **参考结构后独立实现：** `AppSidebar`、首页学习状态、共用 progress、题号导航、课程准备导航、PDF 页码链接与覆盖层焦点管理均在既有 Vue3 和 API 契约内编写。
3. **只借鉴视觉或交互思路：** 学术阅读层级、低干扰面板、来源/回答对照、普通练习专注模式与知识状态的明确标注。EduAgent 使用自己的蓝色语义 Token、本机字体与原有线性 SVG 图标。

本机下载源码、固定版本描述和原 LICENSE/NOTICE 保留在 `data/reference-code/`，本轮将此阅读缓存明确加入 `.gitignore`，避免嵌套仓库和第三方运行文件混入提交。前三个目录的固定版本以其 `reference.json` 为准；它们不是独立 Git checkout，不能用父仓库的 `git rev-parse` 当作第三方提交。

后续如果直接复制代码，必须逐项补充“源仓库、完整 commit、源路径、本地路径、许可证、修改说明”，并随实际分发内容保留所需版权、许可证和 NOTICE。本轮没有将研究代码转换为默认可执行的依赖。

## 适配边界

没有照搬整体页面、品牌或专有素材。没有迁移到 React/Next.js，没有引入多智能体、图数据库、外部解析服务或新模型供应商。参考项目的功能展示不证明 EduAgent 已具备同样的解析能力或教学效果。

EduAgent 沿用来源选择与版本检查、逐轮私人外发同意、原 BKT 与正式评分。尤其未采用参考项目的“未诊断即显示掌握百分比”、模型判分或自动生成测评行为。
