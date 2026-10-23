# Phase 5：双工作区、课程发布与教学闭环

后续更新（2026-10-23）：[真实课程试点](REAL_COURSE_PILOT_GUIDE.md)已补齐已确认教师片段RAG/页码引用及发布关联，当前schema12/45表，内容待负责人确认。下文schema11、“教师课件尚无RAG”和Phase5测试数为当时历史；旧发布不会被自动改写。

2026-10-23。按[本轮任务书](requirements/PHASE5_TASK_BRIEF.md)实施5A～5D并部署到本机。当前schema11、43张表；原36张表、原件和旧评估摘要保持。实际验收、修改文件、失败记录见[综合验收报告](PHASE5_VALIDATION.md)。没有新增依赖、外部服务或真实模型请求。项目清单版本仍0.4.1，不等于完整v0.5.0产品发布。

## 两个工作区

打开[本机学习页](http://127.0.0.1:8000/)。默认学生端，使用原演示学习标识恢复记录；新用户可直接选择预置的“机器学习 · 工程演示课程”，无需先操作后台。

| 工作区 | 主入口 | 复用内容 |
| --- | --- | --- |
| 学生端 | 我的学习、学情与目标、AI伴学、学习记录 | 正式题目/评分/BKT、独立自评与指南、来源约束问答、历史 |
| 学生辅助入口 | 我的笔记、学习资料、普通练习与错题 | 原笔记编辑器/草稿、已保存资料、个人题库普通练习 |
| 课程构建 | 课程概览、课程资料、知识体系、习题管理、课程审核与发布 | 原上传解析、知识树、原题提取/审核，新增课程发布清单 |

工作区切换只调整入口，不创建教师身份，也不改变学生、正式学情或数据权限。`student_id`仍是本机演示作用域，不是认证。构建草稿与发布只在当前标识可见；预置演示课程是公共本机示例。只有一个机器学习课程的既有正式配置，不能作为公共多用户平台部署。

沿用Hash地址：`#/learn`、`#/insights`、`#/study`、`#/history`；辅助入口`#/notes`、`#/resources`、`#/practice`。构建入口`#/builder`、`#/materials`、`#/architecture`、`#/bank`、`#/publish`。旧资料/题目ID链接仍保留；旧`#/bank?view=practice`转到普通练习。前进后退和刷新读取数据，不提交题目或调用模型。

复用现有蓝白布局。构建页850px以下按单栏排列，按钮换行；AI伴学保留原三栏/分栏/小屏标签机制，MarkdownRenderer、引用抽屉及公式防溢出样式保持。DOM测试已覆盖导航、草稿与恢复，真实桌面/窄屏/键盘体验仍需按验收清单操作。

## 学生学习流程

1. 选择课程发布版本和正式目标，再明确点击“开始学情诊断”。服务器建立教学会话，显式分配诊断；不是通过刷新分题。
2. 正式答题沿用原LearningService、确定性评分和BKT公式。新答题事件同时记录会话、发布版本、原题快照；写入与幂等回执在同一事务完成。
3. 查看答题次数、最近结果、BKT估计、自评及确定性下一步理由。没有答题证据显示“待诊断”，不把先验当成薄弱结论。
4. 从建议进入AI伴学，预填问题并选择本发布版本允许的课程来源。进入页面不会自动调用模型；可本地检索，或明确选择模型并提交。
5. 讲解后返回“我的学习”，明确进入正式练习/复测。正式服务依新证据更新BKT并重新规划；普通练习入口明确标为“不更新BKT”。

既有学习标识的目标保持固定，更换目标使用新演示标识。BKT仍按原标识连续累计，不因换会话、发布版本或重新打开页面重置。原题库有限、先修不足、目标已完成或题目耗尽时沿用原策略反馈，不自动生成新题或固定展示“进步”。

恢复旧标识时不会擅自分配新题。旧未完成分配可在明确建立新教学会话后继续，但分配来源仍记为`legacy_unbound`，不能宣称它原本来自新发布版本。旧作答历史不补写`release_id`。

## 发布契约

### 草稿、审核、发布

在“课程构建 → 课程审核与发布”新建草稿，选择课程资料及可选的本标识教师课件版本、已确认知识体系版本；核对原运行题干/选项/答案/解析并逐题确认。保存后检查发布条件，勾选明确确认，再发布。

`reviewed`要求已确认知识体系、原10题全部确认、审核人说明、各正式知识点有题、所选资料有效且配置匹配。未满足条件可明确发布`demo`，必须显示工程演示及未审核警示。预置版本只初始化一次，不因重启或资料变化自动发布新版本。

**现库原10题内容仍pending**。系统没有代替负责人审核。40题候选池包含原10题，额外候选30题，不能算作50题。人工确认本版本答案不等于BKT参数已统计标定；原文件的pending标记不会被后台草稿修改。候选题、个人普通练习、AI原题提取结果均不能在本轮发布机制中自动进入正式诊断。

### 发布清单

发布记录包含稳定`release_id`、作用域内`release_version`、`demo/reviewed`、时间、草稿revision、完整快照及SHA-256指纹。快照包括：

- 课程ID/标题、5个正式知识点和先修配置、原10题的ID/版本/题干/答案/解析。
- 当前题库/知识版本、catalog指纹、BKT参数、策略及`exact-option-key-v1`评分标识。
- 已确认知识体系ID/发布版本/图快照指纹；演示版本可不绑定。
- 课程资料及教师课件的ID、当前版本、内容指纹、教师解析记录定位；原文件不复制。
- 可检索范围`retrieval_scope`。只有已实际接入课程RAG的来源进入范围；教师课件标为`rag_available=false`，仅来源引用，不声称可自动课件检索。
- 审核说明、逐题确认集合、BKT尚未统计标定及运行题库准入说明。

发布后没有覆盖/修改接口。编辑草稿、创建新版本不能改变旧快照。发布前重新计算来源与配置；revision或审核指纹变化返回409。相同request_id+相同内容重放原回执，不同内容409；同草稿revision不能被另一个新请求重复发布。

来源删除/修改或运行配置变化会使旧版本对**新分题/新讲解**不可用，历史快照继续保留并显示来源状态。已分配题在评分配置仍一致时可以完成，避免因资料变动丢失作答；评分配置变化则拒绝混用。当前只支持原运行题库，不是任意题库版本热切换系统。

## 教学请求与Agent

后端以TeachingService组合原LearningService、GuidanceService、CourseReleases与WorkbenchService/LangGraph。确定性服务继续负责分题、评分、BKT、先修与发布有效性；模型只能讲解。

讲解服务端上下文保存会话/发布ID、发布版本、答题revision、自评revision、目标、规则行动/理由及真实客观摘要。模型实际收到的辅助上下文移除会话/发布身份ID，不把笔记当系统指令。所有课程来源必须是发布清单允许的ID+版本，个人笔记继续经过原作用域、版本、索引就绪检查及逐轮外发同意。空来源被拒绝，不查全库；无RAG命中时仍可按已有混合问答规则解释模型知识，不伪造引用。

模型调用前再次核验学习状态、课程/资料、自评版本，网络调用在数据库事务外进行。生成期间状态变化或查看旧讲解时，保留原回答/引用快照，标注`lesson_stale`及原版本；不会把它改称当前状态的建议。个人笔记历史快照、软删除及另存笔记沿用[工作台契约](WORKBENCH_GUIDE.md)，删除不是物理清除所有历史引用。

讲解请求先持久登记意图，再调用原Workbench。刷新只读已保存回答/回执和教学上下文，不重发付费请求。若只有意图而无法确认执行结果，返回`uncertain`，不能自动重试。明确结束等待也不代表原请求未执行。本阶段真实付费调用须另批，自动验收全部使用模拟客户端。

## API

公共只读：`GET /api/v1/courses/published`返回预置公共演示版本，不暴露答案快照。其余前缀为`/api/v1/students/{student_id}`。

| 方法及路径 | 用途 |
| --- | --- |
| GET `/course-releases`、`/course-releases/{release_id}` | 当前标识可见发布版本及当前有效性 |
| GET `/course-builder` | 本地构建清单、资料、已确认体系、原题审核、候选包含关系 |
| POST `/course-builder/drafts` | 新建草稿：`request_id,payload` |
| GET `/course-builder/drafts/{draft_id}` | 草稿、重新计算审核结果与`snapshot_hash` |
| PUT 同上 | 更新：另需`expected_revision` |
| POST `/course-builder/drafts/{draft_id}/publish` | `request_id,expected_revision,snapshot_hash,kind,confirmed:true` |
| GET `/course-workflow/requests/{request_id}` | 原幂等写入回执，不重发 |
| GET `/current-decision` | 已有正式分配或null；不分题 |
| GET `/teaching-sessions` | 最近教学会话及一致学情，或session=null |
| POST `/teaching-sessions` | 明确开始：`request_id,release_id,goals` |
| GET `/teaching-sessions/{session_id}` | 只读会话、建议、当前分配和历史 |
| POST `/teaching-sessions/{session_id}/next` | 明确分题：`request_id,expected_learning_revision` |
| POST `/teaching-sessions/{session_id}/answers` | 正式提交：`request_id,decision_id,answer` |
| POST `/teaching-sessions/{session_id}/explain` | 复用原WorkbenchQuestion输入，额外绑定服务端课程上下文 |
| GET `/teaching-history` | 原正式历史+新旁表来源；旧事件保持unbound |
| GET `/teaching-explanations` | 最近100条教学讲解版本与当前过期状态；不调用模型 |

原Workbench的GET回答、引用、另存笔记接口继续可用，旧学习接口契约保持；新前端恢复不调用原POST next。具体JSON可在[本机接口页](http://127.0.0.1:8000/docs)查看，真实HTTP示例见`scripts/verify_phase5.py`（临时库及模拟模型）。

草稿payload字段仅允许`title,architecture_id,architecture_version,sources,reviewer,reviewed_question_ids`。每个source是`source_type,source_id,source_version`，类型为`course_material`或`teaching_material`，明确1～30项；个人笔记不能被自动提升为课程资料。formal goals只接受现有正式知识点。

主要错误：422非法字段/输入；404当前标识下无资源；409版本冲突、来源变化、审核不足、请求编号内容冲突、其他会话未完成分配；413请求体/本地数量上限。原错误体格式保持，错误不透露其他标识的私有内容。

## 数据及迁移回滚

schema10的36表基础上新增7表，无既有表数据重写：

| 新表 | 职责 |
| --- | --- |
| course_release_drafts | 当前标识课程草稿及独立revision |
| course_releases | 不可变发布快照、指纹及作用域内版本 |
| teaching_sessions | 目标、课程发布版本及流程阶段 |
| teaching_decisions | 正式分配旁表；旧分配版本可为空 |
| teaching_events | 新正式作答旁表及当时完整题目快照 |
| teaching_explanations | 网络前请求意图、上下文及不确定状态 |
| course_workflow_operations | 写操作幂等回执 |

仓储嵌套事务使用SQLite SAVEPOINT，最外层BEGIN IMMEDIATE提交，保证评分事实和来源旁表同时成功/回滚。评分/BKT/策略算法没有改变；历史仍以原表为准。迁移事务失败已用隔离库注入验证，不产生部分发布结构。

实际迁移前确认8000无服务监听、没有运行中的解析/模型/提取任务。先副本演练，再正式迁移，验证原36表所有列摘要、完整性、外键、原件和旧评估。部署后仅新增1个工程演示发布，教学会话/事件等6新表仍0，未制造用户答题或模型记录。

- 本轮开始备份：`data/local/phase5-prechange-5626ce15/`（代码、数据库、摘要，不含.env）。
- 正式升级前备份：`data/local/eduagent.before-v10-ecd743e05173.sqlite3`。
- SHA-256：`a773e6db0e5787dc9861dcde70e7c36a6d9f6f5cdf69d90fc872a785060a548b`。
- 正式回滚副本目录：`data/local/phase5-rollback-90e7de09/`，含`restored-schema10.sqlite3`、`preserved-schema11.sqlite3`及`legacy/backend/src`。
- 演练、正式迁移、部署记录分别为`data/evaluation/phase5-migration-rehearsal-v1.json`、`phase5-migration-v1.json`、`phase5-deployment-v1.json`。

恢复流程：停止当前API；用SQLite备份方式另存**当时最新**schema11数据库和documents原件目录；保留现有数据库，禁止用旧副本覆盖。使用归档schema10代码和独立路径`restored-schema10.sqlite3`运行旧服务，前端也用归档源码构建。新草稿/新会话留在升级库中，不自动倒灌旧库。当前库中新活动若晚于本轮备份，旧副本不会包含，恢复前必须说明这一点。

已验证旧schema10代码能打开恢复10副本且拒绝11副本。普通API拒绝未显式迁移的旧库；禁止旧服务直连新版。迁移脚本仅接受尚未升级的10库，不能对当前11库重复运行：

```powershell
# 仅停服后对schema10执行；当前现用库已经完成，不要重复执行
.\.venv\Scripts\python.exe scripts/verify_phase5_migration.py --db data/local/eduagent.sqlite3
```

## 运行与复验

现用API仅监听127.0.0.1:8000；启动记录`data/local/phase5-server.json`，stdout/stderr在同目录。页面由FastAPI提供已构建前端。需手动重新启动时先确认原服务已停：

```powershell
.\.venv\Scripts\python.exe -m uvicorn eduagent.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -c backend/pyproject.toml -q --tb=short
Set-Location frontend
npm.cmd run test
npm.cmd run build
Set-Location ..
.\.venv\Scripts\python.exe scripts/verify_phase5.py
.\.venv\Scripts\python.exe scripts/verify_phase5_deployment.py
```

`verify_phase5.py`创建隔离库/自建资料及模拟模型，不读现用私人内容。部署验证脚本是交付时的严格基线检查，预期6张教学/草稿表为空；用户实际学习后应重新设验收基线，不能为了使脚本通过删除用户数据。

## 当前限制与下一步

正式仍只有原5点/10演示题；10题内容和40候选需负责人审阅，题目可能耗尽。没有统计BKT标定、真实教学效果证据、真实模型质量复验或本轮浏览器人工验收。主JS约742.83kB，构建通过但有包体提示。现有55条检索评估及5/15课程外误检保留，没有用本轮HTTP测试宣称语义准确率提高。

课件RAG、全量知识映射、自动新题、主观评分、正式题库准入、真实身份/RBAC未实施。建议先完成人工教学流程及内容审核，再另行确认课件RAG/映射或模型质量评测范围。本轮停止在Phase5。
