# 智学郑大 EduAgent

基于知识追踪与智能体驱动的个性化学习辅助系统，面向郑州大学首届 AI 智能体创新应用大赛 A2 任务。

项目围绕高校《机器学习》课程，用 BKT 根据答题记录估计知识掌握度，由单一 Agent 结合学习目标、错题和先修关系规划后续内容。目标流程为：

```text
学习目标 → 初始诊断 → 知识讲解 → 组卷测评 → 掌握度更新 → 后续学习规划
```

## 当前状态

2026-10-22用户随后授权开启**DeepSeek PDF手动选页识别**。入口已启用，仍需每轮选择页码并勾选外发同意才会发送并计费；本次启用没有模型请求，真实视觉兼容性和质量尚未实测。下方“视觉关闭”为阶段交付时的历史状态。

**当前新增阶段：Phase4B-2课程知识体系已交付。** 「资料学习工作台 → 课程知识体系」支持章节树/概念/关系编辑、课件规则候选预览、确认发布与历史、正式知识点学情只读关联。**501项后端、131项前端、64组隔离HTTP及构建通过**；schema8/27表，原21表与资料文件保持。本轮真实模型0次，视觉仍关闭。现存3页PDF保留为未分类，没有强行构建；真实内容和浏览器人工待验收。[4B-2指南](docs/PHASE4B2_GUIDE.md)含使用、API、迁移/回滚及限制。课件解析保持，4B-3映射/RAG扩展未实施；以下为阶段历史。

Phase4A于 **2026-10-21** 交付时，**版本清单仍为0.4.1，后端355项、前端101项测试与构建通过**；自评、主客观对照、确定性建议、受控学习指南与历史已部署，现用库已备份迁至schema6。浏览器人工验收、真实模型预算与教学效果仍待完成；总结/卡片、教材/图片及下一阶段未实施。

其后经单独授权完成[工作台问答修复](docs/WORKBENCH_ANSWER_FIX.md)，当前**后端382项、前端103项**与构建通过。仍先检索再交给模型；无匹配片段时发送问题并标注模型自身知识，改进格式兼容与具体错误提示。7组修复HTTP和18组4A回归通过，本次真实模型请求0次；schema6与学习数据保持。

随后按用户澄清完成[资料与模型结合的问答](docs/WORKBENCH_HYBRID_GUIDE.md)，当前**391项后端、104项前端**与构建通过。先检索，再由大模型结合资料与自身知识综合生成，未命中或部分命中仍可解释。误把示例扩展的时钟功能已移除。28组隔离HTTP通过，最终HTTP报告18次模拟模型/0次真实模型；仍需真实模型与浏览器人工验收。

最新[模型响应异常修复](docs/MODEL_RESPONSE_GUIDE.md)：当前**403项后端、106项前端**与构建通过，30组模拟HTTP通过。工作台独立输出上限、JSON模式和明确错误已接入；经用户单独授权，1次真实DeepSeek完整生成课程引用与知识补充，未发送个人笔记；预算最多2次、未继续使用剩余额度。主库数据保持，浏览器人工与教学效果仍待验证。

最新[聊天字段兼容修复](docs/ANSWER_SCHEMA_GUIDE.md)：当前**428项后端、107项前端**及构建通过，32组模拟HTTP通过。避免因无关附加字段或常见字段别名丢弃可用回答，保留引用/权限检查；1次真实DeepSeek混合来源验证完整返回，使用5课程与2合成笔记，未发送真实个人笔记。指南、BKT、题库及原评估保持。

- 已完成：BKT、5 个知识点、10 道题草稿、确定性评分、SQLite、命令行与 HTTP 闭环；LangGraph/DeepSeek 助教和课程检索；Vue 的学习目标、答题反馈、掌握度、讲解、资料与历史页面；申报草稿已整理。
- 我的笔记：增删改查、UTF-8导入、公式预览、多知识点、草稿恢复和版本保护；保存后建立本地片段，更新/删除立即使旧片段失效。操作不触发BKT；模型外发需要本轮明确同意；演示标识不是账号认证。
- 资料学习工作台：来源/问答/学习工作室响应式布局，显式选择课程/个人/组合，默认本地检索；历史不重复调用模型，引用可打开原文快照，回答可另存和编辑。
- 学习工作室：五知识点四级自评/可空信心、追加历史与独立版本；只读学情对照/重点及规则指南，可选模型辅助解释。自评不改BKT，资料与答题/自评版本绑定，指南个人外发同意与Chat独立。
- 内容准备：40 道候选题（每知识点 8 题，包含原 10 题）、逐题审阅单和两套共 55 条检索开发案例已建立；当前服务仍使用原 10 题演示库。
- 待人工验收：题目答案、解析、教学先修关系与课程资料；所有候选题仍为 `pending`。
- 后续计划：人工审阅并启用正式题库、处理检索误检、建立独立测试集、浏览器可视/操作验收与试用。
- 验证情况：355项后端、101项前端及构建通过；4A完成18组隔离真实HTTP、9次模拟模型、0次真实模型；schema6备份与回滚副本通过，原12表摘要一致。3A/3B及55例检索报告独立保留；没有浏览器人工验收或真实学习效果结论。
- 检索边界：原开发集的宿舍电费误检已拦截；新增挑战集仍有 5/15 个课程外问题误检，不能宣称可靠语义拒答。工作台模型问答无匹配片段时可解释并标注无本地依据；学习指南仍按依据与规则回退。
- 新版本进度：[Phase4A指南](docs/PHASE4A_GUIDE.md)记录自评/建议/指南API、schema6迁移回滚、验证及人工清单；[工作台](docs/WORKBENCH_GUIDE.md)和[个人检索](docs/PERSONAL_RAG_GUIDE.md)保留阶段记录。完整v0.5.0未发布；Phase4A交付后停止，下一阶段需确认。

离线核心只使用标准库；HTTP 与 Agent 分别作为可选依赖安装到项目 `.venv`，没有修改全局 Python。包声明支持 Python 3.11 及以上，目前只验证了 3.12.8。

## 打开学习页面

当前电脑从根目录运行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn eduagent.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

当前电脑已构建前端，启动后打开 [学习页面](http://127.0.0.1:8000/)，创建或恢复学习标识即可使用。答题后查看反馈并继续；资料工作台选择模型并显式提问后，先检索再结合模型生成，未命中部分标注模型知识，个人片段外发仍逐轮同意；刷新只读已保存记录。[接口文档](http://127.0.0.1:8000/docs) 提供API调试。运行见[Web说明](docs/WEB_GUIDE.md)，课件入口见[4B-1指南](docs/PHASE4B1_GUIDE.md)。

后端进程必须持续运行，打开链接不会自动启动服务。若浏览器显示 `ERR_CONNECTION_REFUSED`，先执行上方启动命令，并保持该终端运行；按 Ctrl+C 或关闭运行终端后，地址将无法访问。

新环境安装与完整测试：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e './backend[api,dev,agent,documents]'
.\.venv\Scripts\python.exe -m pytest backend/tests -c backend/pyproject.toml -q

# 前端需要 Node 22（至少 22.12）；安装使用已有锁文件
Set-Location frontend
npm.cmd ci
npm.cmd run test
npm.cmd run build
Set-Location ..
```

当前本机 `.env` 已配置 Agent；该文件被 Git 忽略，不应公开。新环境使用 [.env.example](.env.example) 的空占位配置，在本机填写密钥并启用后重启服务。详细请求见 [Agent 说明](docs/AGENT_GUIDE.md)，基础接口见 [API 说明](docs/API_GUIDE.md)。

## 运行第一阶段

从项目根目录 `D:\ZZUAgent` 打开 PowerShell：

```powershell
$env:PYTHONPATH = 'D:\ZZUAgent\backend\src'
$env:PYTHONIOENCODING = 'utf-8'

# 交互答题；输入 q 保存退出，同一标识再次运行即可恢复
python -m eduagent --student learner-01 --goal logistic_regression

# 合成演示：自动提交标准答案，只验证工程流程
python -m eduagent --demo --student synthetic-01 --db data/local/synthetic.sqlite3

# 仅查看已保存状态（恢复时可省略 --goal）
python -m eduagent --student learner-01 --status

# 完整自动测试（使用安装了 API 与开发依赖的项目环境）
.\.venv\Scripts\python.exe -m pytest backend/tests -c backend/pyproject.toml -q
```

默认数据库为`data/local/eduagent.sqlite3`，已忽略。改变学习目标用新标识；改变题库/BKT/策略配置用新`--db`路径，不静默改写历史。当前schema8，旧库须停写、备份并显式运行迁移入口，普通API启动拒绝版本不兼容，见[迁移与回滚](docs/PHASE4B2_GUIDE.md)。题目不足会明确停止，不重复答题凑掌握度。

若仅测试无需 HTTP/Agent 的离线核心，可运行 `python -m pytest backend/tests/test_bkt.py backend/tests/test_catalog.py backend/tests/test_learning.py backend/tests/test_cli.py -c backend/pyproject.toml -q`（65 项）。详细机制见 [第一阶段说明](docs/PHASE1_GUIDE.md)。

## MVP 范围

课程知识点限定为线性回归与损失函数、梯度下降、逻辑回归、过拟合与正则化、模型评估。最终目标是 30～50 道人工校验客观题、可追溯课程问答、学情诊断、个性化规划和简洁 Web 学习页面。

技术栈：**Vue 3 + Vite / Python + FastAPI / LangGraph / SQLite / 自主 BKT / FAISS + 本地 TF-IDF 检索 / DeepSeek API**。当前检索为词项向量基线，未接入语义嵌入服务。

第一阶段已用 10 道单选题草稿和规则决策器跑通：

```text
答题 → 确定性评分 → BKT 更新 → SQLite 保存 → 下一步决策 → 后续题目
```

第一阶段的规则闭环已接入模型工具调用、带来源讲解和 Web 页面。Web 工程已完成基础测试；浏览器人工操作、可视检查与教学内容验收仍待完成，见 [开发计划](docs/DEVELOPMENT_PLAN.md)。

## 文档与官方资料

- [课程知识体系](docs/PHASE4B2_GUIDE.md)：稳定章节/概念、关系、候选/确认/版本、只读学情、schema8迁移及待人工清单。

- [课件解析与管理](docs/PHASE4B1_GUIDE.md)：Phase4B-1实际API、依赖、资源限制、schema7备份/回滚、验证记录和待人工验收项。

- [AGENTS.md](AGENTS.md)：长期开发规则，后续协作先读取。
- [项目上下文](docs/PROJECT_CONTEXT.md)：目标、需求、赛事依据、技术路线与约束。
- [开发计划](docs/DEVELOPMENT_PLAN.md)：阶段任务、验收、技术建议、决策记录与待办。
- [第一阶段说明](docs/PHASE1_GUIDE.md)：数据契约、模块分工、运行方式、题目审阅清单与当前限制。
- [API 说明](docs/API_GUIDE.md)：第二阶段安装、接口契约、错误处理与测试结果。
- [Web 使用与验收](docs/WEB_GUIDE.md)：页面功能、安装构建、刷新恢复与人工验收边界。
- [Agent 说明](docs/AGENT_GUIDE.md)：模型配置、LangGraph 与工具机制、RAG 边界和新增接口。
- [真实模型验证](docs/LIVE_MODEL_REPORT.md)：两组实际请求、来源、用量和验证限制。
- [内容审阅说明](docs/CONTENT_REVIEW_GUIDE.md)：40 道候选题、逐题审阅单、校验方法与题库切换约定。
- [检索开发集评估](docs/RETRIEVAL_EVALUATION.md)：两套共 55 条开发案例的实际结果、指标、误检与适用范围。
- [教学决策对比](docs/POLICY_EVALUATION.md)：8 个合成状态上，当前策略与固定两题基线的配对行为、暂停限制和复现命令。
- [v0.5.0 设计与计划](docs/V0_5_0_DESIGN.md)：完整版本历史提案；实际阶段进度以各指南为准。
- [自评与学习指南](docs/PHASE4A_GUIDE.md)：Phase4A实际API、确定性规则、受控指南、schema6迁移回滚、355/101项与18组HTTP及人工清单。
- [Markdown/公式渲染](docs/MARKDOWN_GUIDE.md)：Phase 1 实际依赖、接入、限制、47 项前端测试与人工验收项。
- [个人笔记管理](docs/NOTES_GUIDE.md)：Phase 2 用法、完整 API/数据设计、迁移与回滚、269/75项测试和浏览器人工验收清单。
- [本地个人RAG](docs/PERSONAL_RAG_GUIDE.md)：Phase3A来源约束、分块/版本恢复、API、schema4迁移、295/75项测试和13组隔离HTTP结果。
- [申报内容草稿](docs/APPLICATION_DRAFT.md)：按官方表单字段整理，待补个人信息和人工核对，未提交。
- [官方任务清单](docs/references/附件1：任务清单-真实需求.xlsx)：A2 位于 Sheet1 第 3 行。
- [官方申报表](docs/references/附件2：郑州大学首届AI智能体创新应用大赛项目申报表.docx)。
- [官方其他事项说明](docs/references/附件3：其他事项说明.docx)。
- [官方赛事通知](https://www5.zzu.edu.cn/student/info/1003/13120.htm)：报名截至 **2026-11-04**，决赛原则上于 11 月底前完成，具体以后续通知为准；另需核实学院内部申报节点。

## 数据与验证原则

使用公开、自建、模拟或经授权的数据。题目保留来源与校验状态，材料引用可追溯，不收集无关个人信息，不提交 API 密钥。

BKT 参数与阈值在未校准前仅为演示假设。模拟答题用于验证程序行为，不作为真实学习效果证据。完成情况、测试结果及未完成项持续记录在开发计划中。
