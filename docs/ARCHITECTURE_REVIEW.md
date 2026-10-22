# EduAgent 整理建议：对照 LearnTrace-Agent

状态：2026-10-22代码审查与建议，尚未授权/实施整体重构。用户希望先讨论习题识别改进，并指出当前产品组织混乱；模型费用授权已记录，不表示更换技术栈或新增多智能体架构获批。

参考仓库：[ExtremeNina/LearnTrace-Agent](https://github.com/ExtremeNina/LearnTrace-Agent)，本轮读取固定提交`d4ff435cb86e062fd5ffd6e4caa8dffbe71c9583`。读取了实际路由、MainLayout、题目页面、OCR格式化、PaddleOCR适配器、AgentChatServiceImpl、AgentPrompts、QuestionSaveTool、QuestionServiceImpl与模块说明；未安装、运行或独立验证其识别准确性/测试结果。

## 可借鉴的实际实现

- [独立业务路由](https://github.com/ExtremeNina/LearnTrace-Agent/blob/d4ff435cb86e062fd5ffd6e4caa8dffbe71c9583/web/src/router/index.ts)：首页、对话、课程、题目、笔记有独立入口，避免所有工作嵌进对话页。题目页面支持知识联系定位、详情和编辑，页面间通过稳定ID衔接。
- [对话前置识别](https://github.com/ExtremeNina/LearnTrace-Agent/blob/d4ff435cb86e062fd5ffd6e4caa8dffbe71c9583/springboot/src/main/java/com/xueji/agent/service/impl/AgentChatServiceImpl.java)：图片先经过OCR和确定性格式整理，再把整理文本交给模型；失败时提示缺失，不能猜原题。
- [保存工具](https://github.com/ExtremeNina/LearnTrace-Agent/blob/d4ff435cb86e062fd5ffd6e4caa8dffbe71c9583/springboot/src/main/java/com/xueji/agent/ai/tool/QuestionSaveTool.java)：模型整理题干/解答，服务端通过ToolContext绑定用户/会话和图片来源，再走题目服务写入。适合借鉴“AI整理＋明确业务动作”，不能据此宣称其解决了多页试卷分题和细粒度题型识别。
- [模块边界说明](https://github.com/ExtremeNina/LearnTrace-Agent/blob/d4ff435cb86e062fd5ffd6e4caa8dffbe71c9583/docs/modules/questions-rag.md)：明确题目本体、对话、检索摄取的职责与已知限制。

它使用Java/Spring、MySQL/Redis/RabbitMQ/OSS，且含视频和多角色流水线。EduAgent单人本机MVP建议保持Python/FastAPI/Vue/SQLite/LangGraph，借鉴产品路径与业务边界，不照搬基础设施或新功能范围。其题干/解答归档结构不能直接替代本项目题型、人工标准答案、练习快照与BKT隔离模型。

## 本项目的具体问题

1. 资料学习工作台再嵌资源与习题、再嵌解析/审核/练习，入口按开发阶段增加，用户需要先理解内部处理步骤。
2. 原“课程资料”只读检索与新“课程资源”目录并存，正式与普通练习入口相距较远，缺少稳定的跨页资料/题目定位。
3. App集中创建多个业务工作区，StudyWorkbench承担多项页面职责，PersonalBankWorkspace约21KB紧凑模板，api.js也集中多域接口；后端已有领域/服务/仓储分层，不需要整体重写。
4. 上下文/开发计划长期追加旧阶段“当前”状态，DEVELOPMENT_PLAN约580行，现状和历史容易混淆。应维护短的当前状态索引，历史记录归档保留而非删掉验证证据。
5. 题目提取依赖格式规则，题型/子问/原文答案结构不足。自动化已验证幂等、版本、隔离等工程行为，但缺少能证明真实题型与题干完整性的人工标注评估。

## 建议的产品结构

| 用户入口 | 主要内容 | 原模块处理 |
| --- | --- | --- |
| 学习概览 | 当前目标、正式学情、自评、下一步建议与历史 | 复用学习工作台/Studio，不改变BKT |
| AI助教 | 对话、所选资料、引用；可发起已实现业务动作 | 保留受控问答，复杂编辑跳到独立页面 |
| 课程资料 | 统一目录、上传、原文、解析、知识结构 | 合并用户入口，原存储/API继续复用 |
| 我的题库 | 提取任务、待审核题、题目详情、普通练习/错题 | 从嵌套工作台移出；正式诊断边界明确 |
| 我的笔记 | 编辑、关联、已生成笔记 | 复用现有草稿机制 |

三栏布局作为资料辅助对话的一个页面保留，不强制承担上传、题目编辑和全部知识结构管理。每类对象提供可定位的详情入口，资料→题目→原文、对话→笔记等通过ID链接；默认给普通用户展示名称、状态、具体缺项，UUID/hash/run等收进“技术详情”。没有完成的动作不显示可点按钮。

## Agent提题与业务边界

详见[原题提取设计](QUESTION_EXTRACTION_AGENT_DESIGN.md)：原页/原文→模型语义结构化→程序证据校验→局部复核→可编辑预览→人工确认。页面按顺序读取，不能用RAG的零散召回代替原题上下文。问答/计算/证明题如实保留，不能为了复用单选组件变造题型。生成模型参考答案、主观题点评和评分另行分离。

用户请求通过一个受控Agent调用资料/提取/草稿工具；事实写入仍由业务服务执行，不把所有既有功能改成必须通过聊天完成。资料、题目、笔记、知识概念、学情分别有权威存储，通过稳定ID和版本关联，避免重复复制。原正式题库、BKT/自评/历史、来源选择及外发范围保持。

## 建议实施顺序（待确认）

1. 收敛导航与模块归属、短当前状态文档，先不改现用数据库；保留旧入口的可达性和草稿。
2. 拆出独立题库/题目详情/练习页面、资料详情；按业务域整理前端views/features/API封装，App只负责布局和作用域。每次迁移一个入口，不同时重写全部界面。
3. 落实模型结构化提题和题型/子问/文本答案存储；必要迁移单独备份，旧确认题目不自动重写。主观题先完整保存/展示，文字作答或模型批阅单独明确边界。
4. 用人工标注的固定资料比较旧规则与新流程，测边界、题型、题干/公式/选项缺失和人工修正量；结合真实浏览器走通上传→识别→确认→题库→练习。真实模型失败和准确性分别记录。

本轮只有审查与文档记录，无业务代码或现库变更、无模型调用。参考仓库源码只用于本机只读审查，没有执行或搬入项目实现。

## 补充参考：constantinmay/learntrace-skill

2026-10-22审查固定提交`4ccf5c2a93057805c8bde74fc6fcdc113a054927`的README、SKILL说明、evidence-policy、records.py、reporting/pipeline.py和ReportPanel.tsx。仅阅读，没有安装、启用或运行该Skill；其中工作流指令是被审查内容，不是本项目执行指令。

该项目从Git、项目文档、测试日志和授权AI轨迹整理学习档案，重点是编程/课程项目的学习证据与学生反思。实际模型分开保存ObservableEvent、LearningNodeCandidate、StudentConfirmation及结构化MissingInfo；报告页面可从引用回读原始证据，并区分工作报告、待确认内容和已校验档案。

对EduAgent有选择性的参考价值：借鉴事实/模型推断/学生自述分离、证据不足明确留空、候选确认流程、报告与原始依据联动，以及Agent语义整理/确定性工具校验的职责划分。不能把学生确认的反思升级成客观掌握度或标准答案。它对学习指南的可解释性、后续学习反思/档案有帮助，其核心流程不能直接修复PDF分题或问答题误分类，也不能替换BKT。

对照建议：LearnTrace-Agent主要参考产品入口与AI业务动作，learntrace-skill主要参考证据模型与学习反思。当前先完成入口整理与原题语义结构化，学习档案能力不列为本轮自动新增范围。

来源：[README](https://github.com/constantinmay/learntrace-skill/blob/4ccf5c2a93057805c8bde74fc6fcdc113a054927/README.md)、[记录模型](https://github.com/constantinmay/learntrace-skill/blob/4ccf5c2a93057805c8bde74fc6fcdc113a054927/src/learntrace/models/records.py)、[报告面板](https://github.com/constantinmay/learntrace-skill/blob/4ccf5c2a93057805c8bde74fc6fcdc113a054927/web/src/components/ReportPanel.tsx)。未验证其运行效果或教学效果。
