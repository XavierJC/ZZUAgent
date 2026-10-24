# 智学郑大 EduAgent

基于知识追踪与智能体驱动的个性化学习辅助系统，面向郑州大学首届 AI 智能体创新应用大赛 A2 任务。

项目围绕高校《机器学习》课程，用 BKT 根据答题记录估计知识掌握度，由单一 Agent 结合学习目标、错题和先修关系规划后续内容。目标流程为：

```text
学习目标 → 初始诊断 → 知识讲解 → 组卷测评 → 掌握度更新 → 后续学习规划
```

## 当前状态

最新完成 **学习体验整合**：问答区突出，原文和学习建议按需展开；上传资料支持逐页查看与缺失提示；练习可按来源/知识关联查找并专注作答，进度直接衔接下一步。[使用指南](docs/LEARNING_EXPERIENCE_GUIDE.md) · [验收与文件清单](docs/LEARNING_EXPERIENCE_REPORT.md)。

本轮615后端、195前端、29组隔离HTTP及构建通过；已实际检查桌面/窄屏、引用、键盘、普通作答和刷新恢复。schema13/45表内容保持，真实模型0。解析精度与真实教学效果未验证，原BKT及评分保持。下面为此前阶段记录。

最新完成 **学习主流程收敛**：主入口为“资料学习、练习、学习进度”，管理工具默认收起。上传可读资料后可直接提问并点击编号引用查看原文；导入习题可自动整理进入普通练习，缺项留待处理，不再要求每题都人工勾选。AI整理与参考答案保持未核验标记，正式BKT/评分规则不变。[使用说明](docs/LEARNING_SIMPLIFICATION_GUIDE.md) · [实际验收](docs/LEARNING_SIMPLIFICATION_REPORT.md)。

当前schema13/45表，12→13备份/摘要/回退验证通过；604后端、185前端、34组隔离HTTP及构建通过，真实模型0次。长文件识别仍每轮最多3相邻页，真实课件有未识别内容和漏检，浏览器人工验收待完成。此前各阶段数字为历史记录。

已修复“两题后暂停、无法继续作答”的入口：刷新后点击 **复习已做题（不更新掌握度）**，可循环复习并恢复本机进度。正式题不足仍需审核补充，原掌握度/正式记录保持；本机复习不计入BKT。587后端、172前端、9组隔离HTTP及构建通过；schema12/45表不变，真实模型0次。[使用与验证](docs/PRACTICE_CONTINUATION_GUIDE.md)。

最新完成[真实课程单知识点试点](docs/REAL_COURSE_PILOT_GUIDE.md)：课件片段审核、教师RAG、页码原图引用及课程发布/教学整合。**真实内容仍待负责人确认**，恢复`pilot-model-evaluation`可查看5页候选和3道草稿；原正式题库/BKT保持。当前schema12/45表，583后端、163前端、130组隔离HTTP及构建通过；HTTP最终36次模拟。真实视觉请求1次遇网络错误/执行不明，没有成功识别结果，真实聊天0；浏览器人工与教学效果待验收。[本轮完整报告](docs/REAL_COURSE_PILOT_REPORT.md)。

以下Phase5结果为此前交付记录，当前schema和验证以以上试点为准。

已完成并部署 **Phase5双工作区与教学闭环整合**。学生端以“下一步学习任务”为中心；课程构建端独立准备资料、知识体系、习题及发布版本。

- 学生端：我的学习、学情与目标、AI伴学、学习记录；笔记、学习资料和普通练习作为辅助入口。课程构建：课程概览、课程资料、知识体系、习题管理、课程审核与发布。
- 已发布工程演示课程可直接开始：目标→诊断→客观学情/自评→受控讲解→正式复测→BKT更新及重新规划。刷新只读，不分配新题、不重发模型。旧历史不补认新发布版本。
- 新增不可变课程发布清单、审核与版本检查，正式仍原5知识点/10演示题，内容待人工审核。40候选**包含原10题**，额外30题，不自动启用。普通练习和文字作答不更新BKT。
- 笔记、RAG、四格式课件/图片解析、原题提取/修正、知识树、自评及指南保持；新界面复用原模块。教师课件仅支持发布来源引用，尚未全面接入RAG。
- 当前schema11/43表；升级前备份、原36表/原件/旧评估摘要及回退副本验证通过。现有24道个人题、5篇笔记、2份资料和27条正式作答保持。
- **本轮570项后端、158项前端、117组隔离HTTP及构建通过；35次HTTP模拟模型，真实付费调用0。** 浏览器人工、真实模型质量及教学效果待验证；保留原55条检索评估与5/15课程外误检。

[本轮使用/API/迁移说明](docs/PHASE5_GUIDE.md) · [实际验收、修改文件与人工清单](docs/PHASE5_VALIDATION.md) · [开发计划与历史](docs/DEVELOPMENT_PLAN.md)。新增依赖0，版本清单仍0.4.1，完整v0.5.0未发布。仅本机演示，没有教师/学生身份认证。

此前功能记录：[原题识别](docs/EXTRACTION_V2_GUIDE.md)、[个人题库](docs/PHASE4C_GUIDE.md)、[课件解析](docs/PHASE4B1_GUIDE.md)、[知识体系](docs/PHASE4B2_GUIDE.md)、[自评与指南](docs/PHASE4A_GUIDE.md)、[资料问答](docs/WORKBENCH_GUIDE.md)、[个人检索](docs/PERSONAL_RAG_GUIDE.md)、[笔记](docs/NOTES_GUIDE.md)。旧报告的schema和测试数字为阶段历史。

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

默认数据库为`data/local/eduagent.sqlite3`，已忽略。改变学习目标用新标识；改变题库/BKT/策略配置用新`--db`路径，不静默改写历史。当前schema13，普通API拒绝不兼容版本，[本轮迁移与回退](docs/LEARNING_SIMPLIFICATION_GUIDE.md)已验证备份和恢复副本。现用库已升级，勿重复执行旧schema迁移脚本。题目不足明确停止，不重复答题凑掌握度。

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
