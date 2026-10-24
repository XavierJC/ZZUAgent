# 学习体验整合验收报告

日期：2026-10-24。用户批准借鉴优秀项目后，完成现有资料学习、练习及进度的体验整合。使用/API/回退说明见 [指南](LEARNING_EXPERIENCE_GUIDE.md)。没有整体引入第三方项目代码或新增依赖。

## 实际交付

- 问答主区、按需原文侧栏/学习面板、折叠历史/版本/回答设置，保留蓝白风格和窄屏标签。
- 上传资料只读逐页预览，显示可检索状态、空白页与解析提示；引用仍为当时真实片段，当前读取重新校验作用域、版本和删除状态。
- 资料/知识点进入相关普通练习，按来源或稳定概念ID筛选；无关联时明确提示，不能自动扩展题目范围。
- 专注当前作答、返回列表、恢复上次作答、连续练习；导入显示实际阶段及整理结果入口。
- 进度优先显示目标、正式答题证据、下一步与原因，并连接资料问答、普通练习和原正式诊断。
- 建议只准备问题，已有问题草稿保留；跳转不自动复制题目原文外发。打开/历史/恢复/刷新不调用模型或分配正式题。
- 原BKT、评分、自评、指南、笔记草稿和课程构建保留；自动入库规范化可选字段，旧题缺失概念列表按无关联读取，不重写旧内容。

## 自动化及真实HTTP

| 项目 | 实际结果 | 范围 |
| --- | --- | --- |
| 后端全量回归 | **615通过** | 原学习闭环、评分、BKT、笔记、RAG、Agent及指南；新增11项页级/规范化与兼容验证 |
| 前端全量回归 | **195通过，17个文件** | 原185项基线；新增草稿、预览竞争、范围、页导航、焦点与证据显示等行为验证 |
| 构建 | **通过** | 主JS约795.45kB，gzip约265.66kB；保留超过500kB提醒 |
| 页级真实HTTP | **14组通过** | 隔离库、自建三页PDF、模型关闭，真实/模拟模型均0次 |
| 学习流程真实HTTP | **15组通过** | 隔离库，模拟模型4次，真实模型0；覆盖导入、去重、异常隔离、普通练习、引用、版本和重启 |
| 现用部署 | **通过** | schema13/45表；健康、资源、页预览、完整性/外键及45表摘要核对 |

HTTP实际启动本机服务后发送，模型输出使用模拟。单元测试另有各自的模拟提供方，不把HTTP的4次当作所有测试中的模拟总量，也不当作DeepSeek实测。

记录位于 `data/evaluation/`：`learning-experience-page-http-v1.json`、`learning-experience-workflow-http-v1.json`、`learning-experience-deployment-v1.json`、`learning-experience-browser-v1.json`、`learning-experience-changed-files-v1.json`。

## 真实浏览器检查

助手通过Codex内置浏览器实际操作。正式页面仅做读取；作答使用独立 `experience-browser` 夹具、自建资料/题目和关闭模型的测试服务，不写现用学习库。不是负责人对真实教学材料的人工审核。

已检查：桌面1440×1000引用/原文并排；900×900中等宽度；390×844窄屏来源/问答标签与焦点恢复。三个页面宽度分别1425/885/375，均未横向溢出。另验证所选PDF本地检索、第1页真实引用、空白第2页提示、单选未核验参考对照、刷新恢复反馈、下一道简答输入、文字草稿保存恢复、普通练习后正式答题仍0、建议只准备问题，以及没有概念关联时不扩展题目列表。

截图：[桌面引用](../data/evaluation/learning-experience-screenshots/desktop-citation.jpg)、[窄屏问答](../data/evaluation/learning-experience-screenshots/mobile-chat.jpg)。验收后停止8001隔离服务，恢复临时视口，8000本机服务保留。

## 发现与修复记录

- 初次后端运行因系统临时目录权限失败，改用项目内尚不存在的临时目录。Windows测试回环连接受限时通过正常审批运行，未修改保护措施绕过限制。
- 6项旧前端断言假定模态工作台或依赖旧文案/位置，改为验证旁栏行为；指南模态焦点测试保留。新进度测试夹具补齐草稿字段后通过，未删除用例掩盖失败。
- 自建浏览器夹具缺少可选概念列表，连续选题暴露KeyError。已增加入库规范化、旧记录兼容读取及2项后端测试，随后浏览器连续练习成功，旧题未改写。
- 窄屏关闭原文可能把焦点交回隐藏按钮，已恢复打开时的标签和焦点，自动化及真实浏览器复核通过。
- 浏览器曾保留旧前端构建；核对脚本名并用带构建标识的本机入口加载最终版本，没有绕过安全警告。

## 数据与回退

无DDL迁移，schema13/45表保持。开发前 `before.sqlite3`、`code-before.zip`、`baseline.json` 位于 `data/local/learning-experience-20261024-101218/`；最终45张表内容摘要与开发前一致，完整性及外键通过。测试只写隔离库，原评分、BKT、学生revision、自评、笔记、历史及原5点10题/40候选保持。回退保留当前数据库与后来新增数据，再恢复匹配的前后端源码并重新构建；无需旧库覆盖现库。

## 实际修改文件

后端：`backend/src/eduagent/api/workbench.py`、`workbench_schemas.py`；`backend/src/eduagent/services/document_sources.py`、`workbench.py`、`question_intake.py`、`personal_bank.py`；`backend/tests/test_learning_experience.py`。

前端：`frontend/src/App.vue`、`useStudyWorkbench.js`、`features/learning/journey.js`；组件 `StudyWorkbench.vue`、`SourceDrawer.vue`、`LearningNextStep.vue`、`QuestionImportPanel.vue`、`PersonalBankWorkspace.vue`；视图 `PracticeHub.vue`、`LearningInsights.vue`；`workbench.css`、`phase5.css`；测试 `__tests__/workbench.test.js`、`__tests__/learning-experience.test.js`。

脚本：`scripts/snapshot_learning_experience.py`、`verify_learning_experience.py`、`prepare_learning_experience_browser.py`、`verify_learning_experience_deployment.py`。文档：本报告、`LEARNING_EXPERIENCE_GUIDE.md`、`DEVELOPMENT_PLAN.md`、`PROJECT_CONTEXT.md`、`README.md`、`AGENTS.md`。另有重新构建产物、新验收JSON及截图；完整路径见文件清单JSON。

## 已知限制与未执行事项

- 没有更换OCR、解析引擎、嵌入模型或检索排序，不承诺识别精度提升。真实课件仍有未识别页，原55条检索/15条挑战与误检记录未改写，也没有被小样本覆盖。
- 来源约束和位置一致不等于语义正确。真实试卷、复杂公式仍待负责人核对；本轮没有真实DeepSeek调用或教学试验。
- 浏览器未逐项重测大文件上传、断网和所有指南/笔记操作，关键工程行为由已有回归覆盖；不宣称所有设备已验收。
- 普通练习丰富不代表新增BKT测量证据。正式题准入与题量保持原边界；没有保存概念关联时，相应练习筛选为空。
- 主JS仍偏大，后续可在保护草稿和旧路由的前提下拆包。新模型服务、正式题准入和BKT扩点不自动推进。
