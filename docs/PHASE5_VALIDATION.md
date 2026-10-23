# Phase 5 综合验收报告

2026-10-23，Windows本机。按[任务书](requirements/PHASE5_TASK_BRIEF.md)完成5A～5D工程实现，部署为schema11/43表。用法、API、迁移和回滚见[PHASE5_GUIDE](PHASE5_GUIDE.md)。以下是本轮实际运行结果，旧报告保持历史原文。

## 结果

| 验证 | 实际结果 | 范围 |
| --- | --- | --- |
| 后端完整pytest | **570通过** | 原552+新增18，正式评分/BKT/资料/笔记/问答/指南/提取/发布/闭环 |
| 前端完整Vitest | **158通过，13文件** | 原149+新增9；双工作区、只读恢复、显式提交、草稿、讲解版本 |
| 前端生产构建 | 通过 | JS742.83kB、gzip249.55kB；CSS79.18kB；>500kB提示仍存在 |
| 最终隔离真实HTTP | **117组通过** | 真实本机HTTP+真实业务服务，模型响应明确模拟 |
| HTTP中模型 | **35次模拟，0次真实** | 最终7份报告中的计数，不含重复调试轮次/pytest内部mock |
| 迁移演练及现用迁移 | 通过 | 原36表、完整性/外键、备份hash、旧代码边界、回退副本 |
| 实际部署只读检查 | 通过 | 健康、83条API路径、静态资源、12个旧标识及旧历史未补认版本 |
| 浏览器桌面/窄屏/键盘 | **未执行，待人工** | 既往localhost浏览器访问遭拒，遵从任务要求未绕过限制 |
| 真实模型/真实教师内容外发 | **本轮0次** | 本轮未申请付费调用，不复用旧提取费用授权 |
| 真实教学效果/普遍识别质量 | **未验证** | 程序通过不等于教学效果或真实试卷准确率 |

## 最终HTTP报告

| 报告（data/evaluation/） | 组数 | 模拟模型 | 真实模型 |
| --- | --- | --- | --- |
| [phase5-http-v1.json](../data/evaluation/phase5-http-v1.json) | 19 | 2 | 0 |
| [phase5-documents-http-v1.json](../data/evaluation/phase5-documents-http-v1.json) | 15 | 3 | 0 |
| [phase5-architectures-http-v1.json](../data/evaluation/phase5-architectures-http-v1.json) | 17 | 0 | 0 |
| [phase5-guidance-http-v1.json](../data/evaluation/phase5-guidance-http-v1.json) | 18 | 9 | 0 |
| [phase5-chat-http-v1.json](../data/evaluation/phase5-chat-http-v1.json) | 14 | 15 | 0 |
| [phase5-bank-http-v1.json](../data/evaluation/phase5-bank-http-v1.json) | 21 | 2 | 0 |
| [phase5-extraction-http-v1.json](../data/evaluation/phase5-extraction-http-v1.json) | 13 | 4 | 0 |
| 合计 | **117** | **35** | **0** |

新19组使用隔离数据库、自建资料及2次模拟模型响应，重启服务2次。实际调用既有学习分配/评分/BKT/规则与RAG服务，不是静态演示。验证：预置演示可直接开始、GET不分题、目标绑定、显式诊断/幂等、真实评分与重新规划、候选40包含10、本地讲解、模拟模型上下文/引用及重放、讲解后正式复测、审核门槛、不可变发布及草稿CAS、来源子集/空集、标识隔离、无同意私人片段零模型传输、有同意的合成笔记mock、普通练习不写BKT、旧历史不补认及不同学情行动差异、来源变化及旧回答、重启恢复。

原98组HTTP本轮重新运行，另存phase5前缀结果，不覆盖此前阶段报告。涵盖四格式解析/公式及图片告警、原件/重启、知识体系/候选/确认/关系、独立自评/指南、混合问答/校验/引用/异常恢复、个人题库/普通练习、受控原题提取及文字草稿。模型均注入模拟客户端，没有借测试实际发送教师课件或私人笔记。

## 单元/界面行为验证

新增18项后端测试见`backend/tests/test_phase5.py`：工程演示不冒充审核、无证据待诊断、显式分题及同编号回执、旧历史/旧未完分配、学生作用域（含标识恰为*）、草稿CAS、发布不可变、已审核门槛、候选ID拒绝、来源失效、真实评分后故障时事实与旁表同时回滚、本地来源限制、schema10迁移故障完整恢复、题目耗尽只读建议。

新增前端9项在`phase5.test.js`及`workbench.test.js`：启动/刷新不分题；教学会话→分题→提交走新契约；不确定命令只查回执；本地存储失败不写；双工作区与辅助入口；旧资料ID链接；新用户完整诊断/评分/刷新不分新题；独立构建草稿恢复；待确认讲解恢复原发布上下文/过期提示不重发模型。

已有前端测试针对新版导航与只读currentDecision替身调整，不删除原评分、来源、草稿和错误断言。旧迁移测试显式清除新增7表后构造旧schema，继续验证旧表保留和拒绝不兼容新库。

## 调试失败与修复

- 首轮新增后端有4处失败：测试把Question对象当字典、发布辅助函数缺参数；修正测试数据/调用，保留原功能断言，最终全套570通过。
- 首轮前端旧测试9处失败：旧导航名称与恢复时POST next的替身不符。按新GET恢复契约更新替身及导航期望，保留交互断言。
- 一轮前端断言通过但出现1个未处理渲染错误：新增测试的发布版本替身缺少question_versions。补齐替身后再次完整通过，无未处理错误。
- 最后检查发现待确认讲解读取旧Workbench回执时可能丢失旁表上下文；已补回原发布版本/过期标记并新增测试，最终158通过。
- 无迁移失败遗留，无失败HTTP组遗留。构建包体告警、人工验收及真实内容质量仍列为限制。

## 原事实与部署一致性

本轮重新核对实际基线为schema10/36表、24道个人题、1个提取任务；此前12题为旧阶段数字，不能拿来覆盖现状。原10演示题都pending，40候选含原10，额外30。

副本演练：[记录](../data/evaluation/phase5-migration-rehearsal-v1.json)。正式迁移：[记录](../data/evaluation/phase5-migration-v1.json)。部署：[记录](../data/evaluation/phase5-deployment-v1.json)。原36表按所有原列逐表核对摘要，原件和旧评估逐文件hash一致，完整性ok，外键0错误，部署前后12个旧标识读取不产生新分配。

迁移和只读部署检查时原事实：12个标识、14条掌握状态、37条分配、27条正式作答、7条旧助教运行、5篇笔记、21条原Workbench运行、1条指南、2份资料、4份解析记录、24道个人题、1个提取任务。原表中历史模型计数保持，不能算成本轮调用，也不能声称系统从未调用过模型。

新增7表中只有course_releases有1条预置demo，其他6表0。没有为验收往现用库写答题、课堂材料或模拟模型记录。评分/BKT/原策略与LearningService源文件和正式资料配置保持原字节；仓储只新增SAVEPOINT事务组合能力，以便来源旁表与原评分原子提交。

正式备份：`data/local/eduagent.before-v10-ecd743e05173.sqlite3`；SHA-256 `a773e6db0e5787dc9861dcde70e7c36a6d9f6f5cdf69d90fc872a785060a548b`。回退目录`data/local/phase5-rollback-90e7de09/`保存10恢复副本、11保留副本和归档旧代码；旧代码接受10/拒绝11。回退必须保留升级后的最新库，不能覆盖丢失新增会话。

服务仅127.0.0.1:8000，`data/local/phase5-server.json`记录当前启动；最终前端资源已通过HTTP访问。配置/.env和密钥未变更、未写入新报告。

## 待负责人浏览器人工验收

以下均为待办，DOM/HTTP通过不能替代真实浏览器操作。模型步骤可先本地模式；实际付费调用另行确认。

- [ ] 桌面打开学生端，预置课程显示工程演示/待审，不需后台预备；新标识选择目标后出现真实诊断题。
- [ ] 提交一题，核对评分、答题次数、BKT变化；自评单列，未答知识点仍待诊断。
- [ ] 从结果进入AI伴学，目标/课程版本/依据可见；不自动发送请求；本地检索公式/代码/引用抽屉可用。
- [ ] 从讲解返回正式复测，显式分题，作答后更新学情；普通练习完成后正式BKT不变。
- [ ] 刷新、前进后退、重复点击提交/查询回执，不重复分题/评分/模型调用；断网后状态和原请求编号可恢复。
- [ ] 切换课程构建，五个入口清晰；上传/解析、知识树、提取审核、旧链接正常，原笔记/自评/题目草稿保留。
- [ ] 创建课程草稿、离开再返回、刷新恢复；另一窗口修改时出现revision冲突，本机副本能保留并手工合并。
- [ ] 未审核不能发布reviewed；明确发布demo不自动启用候选题；已有发布快照不因编辑草稿改变。
- [ ] 恢复旧标识，历史注明未记录发布版本；旧未完题可明确进入新会话继续，其原分配版本仍未绑定。
- [ ] 390px、768px与桌面宽度，侧栏/按钮/公式表格/对话不遮挡；Tab顺序、Enter提交、Escape关闭引用、焦点恢复正常。
- [ ] 不同演示标识切换，私有课程草稿、笔记、会话和恢复状态不串用；不把演示标识描述为账号权限。
- [ ] 负责人独立审核原10题及40候选的题干/答案/解析与先修假设；本轮没有代审。

## 风险及后续范围

只有原运行题库可用于发布，不是任意课程版本执行引擎；目标和BKT仍按原演示标识累计。教师课件可纳入来源定位清单，尚未新增RAG索引。有限题库可能耗尽。检索原55例和5/15课程外误检保持，不声称本轮提升准确率。未验证真实模型在新教学上下文的质量，也未做教学效果研究。

建议先人工验收完整学习路径及内容，再另行确认模型小额质量评估或4B-3课件映射/RAG。没有推进新题生成、主观评分、正式BKT扩展或认证平台。本轮完成后停止。

## 实际修改文件

清单在下方按本轮开始的代码归档逐文件比较生成。未修改的换行差异已恢复；前端dist为生成文件，数据库/备份/测试临时目录不算源码变更。

### Backend

- [backend/src/eduagent/agent/workbench.py](../backend/src/eduagent/agent/workbench.py) (modified)
- [backend/src/eduagent/api/app.py](../backend/src/eduagent/api/app.py) (modified)
- [backend/src/eduagent/api/body_limit.py](../backend/src/eduagent/api/body_limit.py) (modified)
- [backend/src/eduagent/api/course_workspaces.py](../backend/src/eduagent/api/course_workspaces.py) (added)
- [backend/src/eduagent/services/course_releases.py](../backend/src/eduagent/services/course_releases.py) (added)
- [backend/src/eduagent/services/teaching.py](../backend/src/eduagent/services/teaching.py) (added)
- [backend/src/eduagent/services/workbench.py](../backend/src/eduagent/services/workbench.py) (modified)
- [backend/src/eduagent/storage/course_release_schema.py](../backend/src/eduagent/storage/course_release_schema.py) (added)
- [backend/src/eduagent/storage/migrations.py](../backend/src/eduagent/storage/migrations.py) (modified)
- [backend/src/eduagent/storage/sqlite.py](../backend/src/eduagent/storage/sqlite.py) (modified)
- [backend/tests/test_architectures.py](../backend/tests/test_architectures.py) (modified)
- [backend/tests/test_documents.py](../backend/tests/test_documents.py) (modified)
- [backend/tests/test_migrations.py](../backend/tests/test_migrations.py) (modified)
- [backend/tests/test_personal_bank.py](../backend/tests/test_personal_bank.py) (modified)
- [backend/tests/test_personal_migration.py](../backend/tests/test_personal_migration.py) (modified)
- [backend/tests/test_phase5.py](../backend/tests/test_phase5.py) (added)
- [backend/tests/test_self_assessments.py](../backend/tests/test_self_assessments.py) (modified)
- [backend/tests/test_semantic_extraction.py](../backend/tests/test_semantic_extraction.py) (modified)
- [backend/tests/test_tutor.py](../backend/tests/test_tutor.py) (modified)
- [backend/tests/test_web.py](../backend/tests/test_web.py) (modified)
- [backend/tests/test_workbench.py](../backend/tests/test_workbench.py) (modified)

### Frontend

- [frontend/src/__tests__/app.test.js](../frontend/src/__tests__/app.test.js) (modified)
- [frontend/src/__tests__/fixtures.js](../frontend/src/__tests__/fixtures.js) (modified)
- [frontend/src/__tests__/notes-ui.test.js](../frontend/src/__tests__/notes-ui.test.js) (modified)
- [frontend/src/__tests__/phase5.test.js](../frontend/src/__tests__/phase5.test.js) (added)
- [frontend/src/__tests__/study-guidance.test.js](../frontend/src/__tests__/study-guidance.test.js) (modified)
- [frontend/src/__tests__/workbench.test.js](../frontend/src/__tests__/workbench.test.js) (modified)
- [frontend/src/__tests__/workspace.test.js](../frontend/src/__tests__/workspace.test.js) (modified)
- [frontend/src/api.js](../frontend/src/api.js) (modified)
- [frontend/src/App.vue](../frontend/src/App.vue) (modified)
- [frontend/src/components/PersonalBankWorkspace.vue](../frontend/src/components/PersonalBankWorkspace.vue) (modified)
- [frontend/src/components/StudyWorkbench.vue](../frontend/src/components/StudyWorkbench.vue) (modified)
- [frontend/src/phase5.css](../frontend/src/phase5.css) (added)
- [frontend/src/useCourseBuilder.js](../frontend/src/useCourseBuilder.js) (added)
- [frontend/src/usePageRoute.js](../frontend/src/usePageRoute.js) (modified)
- [frontend/src/useStudyWorkbench.js](../frontend/src/useStudyWorkbench.js) (modified)
- [frontend/src/useTeachingWorkspace.js](../frontend/src/useTeachingWorkspace.js) (added)
- [frontend/src/useWorkspace.js](../frontend/src/useWorkspace.js) (modified)
- [frontend/src/views/CourseBuilderView.vue](../frontend/src/views/CourseBuilderView.vue) (added)
- [frontend/src/views/LearningHistory.vue](../frontend/src/views/LearningHistory.vue) (modified)
- [frontend/src/views/LearningInsights.vue](../frontend/src/views/LearningInsights.vue) (added)
- [frontend/src/views/LearningOverview.vue](../frontend/src/views/LearningOverview.vue) (modified)
- [frontend/src/views/LearningResources.vue](../frontend/src/views/LearningResources.vue) (added)
- [frontend/src/views/ResourcesView.vue](../frontend/src/views/ResourcesView.vue) (modified)

### Verification scripts

- [scripts/verify_architectures.py](../scripts/verify_architectures.py) (modified)
- [scripts/verify_documents.py](../scripts/verify_documents.py) (modified)
- [scripts/verify_phase4a.py](../scripts/verify_phase4a.py) (modified)
- [scripts/verify_phase5.py](../scripts/verify_phase5.py) (added)
- [scripts/verify_phase5_deployment.py](../scripts/verify_phase5_deployment.py) (added)
- [scripts/verify_phase5_migration.py](../scripts/verify_phase5_migration.py) (added)
- [scripts/verify_workbench_answers.py](../scripts/verify_workbench_answers.py) (modified)

### Documentation

- [docs/DEVELOPMENT_PLAN.md](../docs/DEVELOPMENT_PLAN.md) (modified)
- [docs/EXTRACTION_V2_GUIDE.md](../docs/EXTRACTION_V2_GUIDE.md) (modified)
- [docs/PHASE4B2_GUIDE.md](../docs/PHASE4B2_GUIDE.md) (modified)
- [docs/PHASE4C_GUIDE.md](../docs/PHASE4C_GUIDE.md) (modified)
- [docs/PHASE5_GUIDE.md](../docs/PHASE5_GUIDE.md) (added)
- [docs/PHASE5_VALIDATION.md](../docs/PHASE5_VALIDATION.md) (added)
- [docs/PROJECT_CONTEXT.md](../docs/PROJECT_CONTEXT.md) (modified)
- [docs/requirements/PHASE5_TASK_BRIEF.md](../docs/requirements/PHASE5_TASK_BRIEF.md) (added)
- [docs/WEB_GUIDE.md](../docs/WEB_GUIDE.md) (modified)
- [docs/WORKBENCH_GUIDE.md](../docs/WORKBENCH_GUIDE.md) (modified)

### Project files

- [AGENTS.md](../AGENTS.md) (modified)
- [README.md](../README.md) (modified)

