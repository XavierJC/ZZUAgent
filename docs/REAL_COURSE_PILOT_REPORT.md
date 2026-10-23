# 真实课程闭环试点验收报告

2026-10-23。本轮完成小范围工程接通、真实资料检查、非破坏性迁移和本机部署。**现用资料尚待负责人确认，不能宣称已完成真实教学效果验证或已审核课程发布。** [使用及审核步骤](REAL_COURSE_PILOT_GUIDE.md)。

## 核查出的真实能力与缺口

| 项目 | 实施前真实状态 | 本轮处理 |
| --- | --- | --- |
| Phase5 | 双工作区/不可变发布/正式学习主流程已存在，schema11/43表 | 复用，不新建教师端或评分系统 |
| 资料 | 原2份PDF各有不同指纹；桌面测试题2/3分别命中，标题有一处不准确 | 保留原记录，不按同名误合并；不重写旧题/标题 |
| 教师RAG | 所有教师PDF只解析，SourceType仅原课程说明/个人笔记 | 新增已确认页片段适配器，独立来源/版本/逐轮外发 |
| 知识体系 | 已发布版本0份 | 创建1章/1概念候选，明确需负责人确认；没有虚构已有确认ID |
| 个人题 | 24题全部draft，含旧other及错误分类 | 原24题保持；复用其中同源3题到独立试点作用域，未重新收费识别 |
| 正式学习 | 原5点/10题，模型评估2题，配置绑定历史 | 不替换题库、不调参数，新个人题不能写BKT |

原标识固定目标为梯度下降，试点新标识`pilot-model-evaluation`仅选择原model_evaluation。不同标识不能通过公共接口读取对方笔记/课件；试点按明确选定原文件在自身作用域保存1课件/1习题，并复用已有同文件指纹的提取结果。曾为真实视觉试验登记在原标识的那份课件及故障回执保留，故现库文档总行数5，不应误报仍只有2份或称没有跨作用域副本。

## 真实内容检查

选择《机器学习-第2讲-模型评估与选择.pdf》72页，重点11、12、20、32、35；《机器学习测试题3.pdf》第1页第1～3题。使用pypdf查文字层，并用既有pdfium本地渲染检查5张课件原图和1张习题原图，未调用视觉模型来完成这次助手原图对照。

第11/12页原文本各约11字符，第32/35页各27字符，主要只有标题；页面正文、公式、混淆矩阵实际在图片中，不能把本地partial说成识别完整。第20页原生578字符，二维表格仍需对照。5处已保存为候选，四处为助手对原图阅读整理的待核对转录，第20页使用原生文本；不是成功的DeepSeek识别结果，也不是人工已审。

第32页真实类别在行、预测类别在列，第35页方向交换，候选保留差异。第12页源资料本身的“无偏估计”表述保留并列待内容审阅，没有改成权威正确结论。3题均为单选，题干和A～D选项经助手对照原图检查，原文没有答案；answer仍null，不代填人工确认。全部其他页/题的正确性不在本次检查结论内。

具体状态与范围见[内容检查记录](../data/evaluation/pilot-content-check-v1.json)。原件、页图、候选正文及完整审核包仅在被忽略的`data/local/`保存，不将整份教师内容放入公开源码。

## 真实模型与费用

用户另外批准为识别质量调用DeepSeek，先明确选定第11/12/32页。现有视觉任务记录**实际1次请求**后发生`network_error`，状态`uncertain`，未取得可用转录，后续页没有继续发送。没有自动重发这笔执行不明请求。

上游报告prompt/completion token均0，但请求可能已经到达服务方，**实际计费未知**，不能声称免费或已识别成功。个人笔记外发0，真实聊天调用0；没有将整份课件或习题发给DeepSeek。本轮不能报告DeepSeek识别准确率、真实课件模型问答质量或模型效果提升。

授权允许继续以质量为目标调试费用，但材料外发范围仍是具体选择；不把该回答解释为所有文件自动外发授权。已保存请求/状态，后续若继续调试须明确处理原不确定状态，不通过刷新或脚本重跑自动付费。

## 自动化与HTTP

| 验证 | 本轮实际结果 |
| --- | --- |
| 全套后端pytest | **583通过**，原570+新增13 |
| 全套前端Vitest | **163通过，14文件**，原158+新增5 |
| 生产构建 | 通过；主JS753.11kB/gzip252.58kB，CSS79.18kB，包体提示仍在 |
| 新真实资料隔离HTTP | **13组通过**，最终1次模拟聊天响应、真实聊天0 |
| 原模块隔离HTTP重跑 | **117组通过**，最终35次模拟模型、真实0 |
| 最终HTTP集合合计 | **130组，36次模拟**；不是全部调试轮次累计用量 |
| 真实模型识别 | **1次执行不明/网络错误，0份成功结果** |
| 迁移演练/正式迁移/部署 | 通过，完整性ok/外键0，旧11代码接受恢复11且拒绝12 |
| 浏览器桌面/窄屏/键盘 | **未执行**；既有localhost浏览器拒绝未绕过，DOM不代替人工 |
| 负责人内容审核/真实教学效果 | **未完成/未验证** |

新增13项后端覆盖候选排除、确认概念门槛、原文/页码、学生隔离、空集、幂等/CAS、撤回/删除/重解析/原件损坏失效、独立外发、越权工具拒绝、发布来源及知识体系版本一致性、转录缺项。前端新增5项覆盖教师逐轮授权、旧版本原页URL、候选草稿隔离、不确定回执不重发、确认门槛。

新HTTP使用现用库和原件的隔离副本，仅脚本在副本模拟内容审核后，实际走通：确认概念和5页→教师TF-IDF/真实页图→demo发布→原题库模型评估诊断（第一次错）→本地课件讲解→无同意零模型传输→模拟模型引用→普通练习不写BKT→第二道正式复测（对）→题目耗尽→新标识无证据不同建议→重启恢复→撤回确认使检索和发布失效、历史引用保持。**脚本确认不代表现用数据已被负责人审核。**

报告分别为：

| 报告（data/evaluation/） | 组数 | 模拟调用 |
| --- | --- | --- |
| [pilot-http-v1.json](../data/evaluation/pilot-http-v1.json) | 13 | 1 |
| [pilot-phase5-http-v1.json](../data/evaluation/pilot-phase5-http-v1.json) | 19 | 2 |
| [pilot-documents-http-v1.json](../data/evaluation/pilot-documents-http-v1.json) | 15 | 3 |
| [pilot-architectures-http-v1.json](../data/evaluation/pilot-architectures-http-v1.json) | 17 | 0 |
| [pilot-guidance-http-v1.json](../data/evaluation/pilot-guidance-http-v1.json) | 18 | 9 |
| [pilot-chat-http-v1.json](../data/evaluation/pilot-chat-http-v1.json) | 14 | 15 |
| [pilot-bank-http-v1.json](../data/evaluation/pilot-bank-http-v1.json) | 21 | 2 |
| [pilot-extraction-http-v1.json](../data/evaluation/pilot-extraction-http-v1.json) | 13 | 4 |

原55条检索记录及15条课程外挑战集的全部文件hash保持，包含原5/15误检，未通过隐藏失败案例声称提升语义准确率。试点只验证少量真实片段/来源/引用，不代表整个72页或课程的检索准确率。

## 失败与修复记录

- 新增后端首轮10失败来自合成知识体系夹具缺章节；补齐后保留原断言，最终全套583通过。
- 首轮真实HTTP暴露来源摘要遗漏教师文档字段导致响应500，已修复严格响应契约并重跑。
- HTTP普通练习断言曾错读回执顶层，按原result结构修正，没有更改评分/BKT行为。
- 准备脚本曾使用错误的version字段、超过现有20单位分页限制、候选JSON公式转义错误；均已修正并按保存状态继续，未重复模型调用或产生重复现用试点草稿。
- DeepSeek网络错误仍未解决，保持uncertain，不能算修复或识别通过。
- 最终无自动测试/HTTP失败遗留；浏览器、负责人审核、真实模型质量和教学效果保留待办。

## 数据与部署

schema11/43→12/45只新增2表，无旧表改列。迁移前已备份，副本演练和正式迁移均逐表验证旧43表摘要。后续授权准备追加记录，部署再次逐行确认原43表所有旧行内容保持，而不是把新增资料误报成旧表总行数不变。

现库13标识、27个人题、5笔记、5文档、8解析记录、5页关联、1个原demo发布、27条原正式作答。试点1章/1概念仍未发布，5关联candidate，3题draft/答案未知，试点答题revision0。原mastery/decisions/attempts/tutor、自评/指南等事实表与基线完全一致，LearningService、BKT、原策略、Catalog以及正式题目/资料文件保持原字节；旧24题没有自动修改。

迁移记录：[副本演练](../data/evaluation/pilot-migration-rehearsal-v1.json)、[正式迁移](../data/evaluation/pilot-migration-v1.json)；[实际部署](../data/evaluation/pilot-deployment-v1.json)。备份`eduagent.before-v11-704d1bf4a0aa.sqlite3`及回退路径见指南。部署启动记录`data/local/pilot-server.json`，只监听127.0.0.1；无真实认证或角色平台。

## 负责人浏览器验收清单

- [ ] 恢复pilot-model-evaluation，原梯度下降标识目标与学情保持；未答仍显示待诊断。
- [ ] 构建知识体系，核对后发布1章/1概念；不增加正式BKT点。
- [ ] 课程资料页对照11/12/20/32/35原图、公式、表格与片段，确认或保留待审；刷新和窄屏可操作。
- [ ] 3道习题逐题核对、独立解答、确认答案后进入普通练习；未审核题不能开始普通客观评分。
- [ ] 新建课程草稿，选相同知识体系版本及可检索教师课件，明确发布demo；检查旧课程未被覆盖。
- [ ] 学生选择该版本，诊断→学情→一键进入关联教师讲解；默认本地，不自动调用模型。
- [ ] 点击引用打开片段、原文件版本/页码和原图；Tab/Shift-Tab、Escape及焦点恢复正常。
- [ ] 模型模式教师外发同意独立，换问题/来源/刷新不复用旧授权；真实聊天先明确本轮范围及预算。
- [ ] 普通练习反馈不伪装BKT更新；正式复测更新实际状态，2题耗尽明确提示。
- [ ] 刷新/前进后退/断网后只读回执，不重复分题、评分或付费请求；原笔记/自评草稿正常。
- [ ] 撤回片段确认或更新资料，当前检索/旧发布失效，历史引用保留；不把软删除称物理清除。
- [ ] 桌面、768px、390px布局，长公式/表格/原图不遮挡；这些尚未由真实浏览器检查。

## 未完成及边界

现用教师RAG要等负责人确认后才有有效内容；尚无已审核真实课程发布。网络错误导致没有本轮成功模型识别输出。完整PDF公式/扫描识别、全量语义映射、全量资源导入、BKT新知识点、正式新题准入、主观评分、多智能体/认证平台均不在本轮实施。老师原文也可能有表述问题，片段确认不能代替学术正确性验证。

后续首先完成上述人工审核；若需要继续诊断，应另批正式题库准入，不能通过普通练习刷掌握度。再单独开展检索质量样本及真实模型故障调试，不将工程验收当教学效果证据。

## 实际修改文件

以下按本轮开始的代码归档逐文件比较；生成dist、真实正文、数据库及备份另存，不纳入源码清单。

### Backend

- [backend/src/eduagent/agent/workbench.py](../backend/src/eduagent/agent/workbench.py) (modified)
- [backend/src/eduagent/api/app.py](../backend/src/eduagent/api/app.py) (modified)
- [backend/src/eduagent/api/body_limit.py](../backend/src/eduagent/api/body_limit.py) (modified)
- [backend/src/eduagent/api/document_schemas.py](../backend/src/eduagent/api/document_schemas.py) (modified)
- [backend/src/eduagent/api/documents.py](../backend/src/eduagent/api/documents.py) (modified)
- [backend/src/eduagent/api/knowledge_schemas.py](../backend/src/eduagent/api/knowledge_schemas.py) (modified)
- [backend/src/eduagent/api/teaching_materials.py](../backend/src/eduagent/api/teaching_materials.py) (added)
- [backend/src/eduagent/api/workbench_schemas.py](../backend/src/eduagent/api/workbench_schemas.py) (modified)
- [backend/src/eduagent/services/course_releases.py](../backend/src/eduagent/services/course_releases.py) (modified)
- [backend/src/eduagent/services/documents.py](../backend/src/eduagent/services/documents.py) (modified)
- [backend/src/eduagent/services/knowledge.py](../backend/src/eduagent/services/knowledge.py) (modified)
- [backend/src/eduagent/services/resources.py](../backend/src/eduagent/services/resources.py) (modified)
- [backend/src/eduagent/services/study_guides.py](../backend/src/eduagent/services/study_guides.py) (modified)
- [backend/src/eduagent/services/teaching_sources.py](../backend/src/eduagent/services/teaching_sources.py) (added)
- [backend/src/eduagent/services/workbench.py](../backend/src/eduagent/services/workbench.py) (modified)
- [backend/src/eduagent/storage/migrations.py](../backend/src/eduagent/storage/migrations.py) (modified)
- [backend/src/eduagent/storage/sqlite.py](../backend/src/eduagent/storage/sqlite.py) (modified)
- [backend/src/eduagent/storage/teaching_source_schema.py](../backend/src/eduagent/storage/teaching_source_schema.py) (added)
- [backend/tests/test_architectures.py](../backend/tests/test_architectures.py) (modified)
- [backend/tests/test_documents.py](../backend/tests/test_documents.py) (modified)
- [backend/tests/test_migrations.py](../backend/tests/test_migrations.py) (modified)
- [backend/tests/test_personal_bank.py](../backend/tests/test_personal_bank.py) (modified)
- [backend/tests/test_personal_migration.py](../backend/tests/test_personal_migration.py) (modified)
- [backend/tests/test_phase5.py](../backend/tests/test_phase5.py) (modified)
- [backend/tests/test_self_assessments.py](../backend/tests/test_self_assessments.py) (modified)
- [backend/tests/test_semantic_extraction.py](../backend/tests/test_semantic_extraction.py) (modified)
- [backend/tests/test_teaching_sources.py](../backend/tests/test_teaching_sources.py) (added)
- [backend/tests/test_tutor.py](../backend/tests/test_tutor.py) (modified)
- [backend/tests/test_web.py](../backend/tests/test_web.py) (modified)
- [backend/tests/test_workbench.py](../backend/tests/test_workbench.py) (modified)

### Frontend

- [frontend/src/__tests__/teaching-links.test.js](../frontend/src/__tests__/teaching-links.test.js) (added)
- [frontend/src/__tests__/workbench.test.js](../frontend/src/__tests__/workbench.test.js) (modified)
- [frontend/src/api.js](../frontend/src/api.js) (modified)
- [frontend/src/App.vue](../frontend/src/App.vue) (modified)
- [frontend/src/components/SourceDrawer.vue](../frontend/src/components/SourceDrawer.vue) (modified)
- [frontend/src/components/StudyWorkbench.vue](../frontend/src/components/StudyWorkbench.vue) (modified)
- [frontend/src/components/TeachingMaterialReview.vue](../frontend/src/components/TeachingMaterialReview.vue) (added)
- [frontend/src/useStudyWorkbench.js](../frontend/src/useStudyWorkbench.js) (modified)
- [frontend/src/useTeachingLinks.js](../frontend/src/useTeachingLinks.js) (added)
- [frontend/src/views/CourseBuilderView.vue](../frontend/src/views/CourseBuilderView.vue) (modified)

### Verification and preparation

- [scripts/prepare_pilot_review.py](../scripts/prepare_pilot_review.py) (added)
- [scripts/prepare_real_pilot.py](../scripts/prepare_real_pilot.py) (added)
- [scripts/verify_architectures.py](../scripts/verify_architectures.py) (modified)
- [scripts/verify_documents.py](../scripts/verify_documents.py) (modified)
- [scripts/verify_phase4a.py](../scripts/verify_phase4a.py) (modified)
- [scripts/verify_phase5.py](../scripts/verify_phase5.py) (modified)
- [scripts/verify_pilot_deployment.py](../scripts/verify_pilot_deployment.py) (added)
- [scripts/verify_pilot_migration.py](../scripts/verify_pilot_migration.py) (added)
- [scripts/verify_real_pilot.py](../scripts/verify_real_pilot.py) (added)
- [scripts/verify_workbench_answers.py](../scripts/verify_workbench_answers.py) (modified)

### Documentation

- [docs/DEVELOPMENT_PLAN.md](../docs/DEVELOPMENT_PLAN.md) (modified)
- [docs/PHASE5_GUIDE.md](../docs/PHASE5_GUIDE.md) (modified)
- [docs/PROJECT_CONTEXT.md](../docs/PROJECT_CONTEXT.md) (modified)
- [docs/REAL_COURSE_PILOT_GUIDE.md](../docs/REAL_COURSE_PILOT_GUIDE.md) (added)
- [docs/REAL_COURSE_PILOT_REPORT.md](../docs/REAL_COURSE_PILOT_REPORT.md) (added)
- [docs/RESOURCE_INTEGRATION_PLAN.md](../docs/RESOURCE_INTEGRATION_PLAN.md) (modified)

### Project files

- [AGENTS.md](../AGENTS.md) (modified)
- [README.md](../README.md) (modified)

