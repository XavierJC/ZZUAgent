# 笔记本与练习工作区重建验收

收尾日期：2026-10-25（Asia/Shanghai）。实现与迁移发生于2026-10-24恢复的产品重建任务；本次仅补文档和复核。[指南/API](NOTEBOOK_REBUILD_GUIDE.md) · [设计](NOTEBOOK_REBUILD_DESIGN.md) · [参考归属](THIRD_PARTY_REFERENCES.md)。

## 实际完成

新增持久Notebook、不可变请求上下文、资料关联、独立问答历史和普通练习关联。前端包含主题主页、来源/问答/原文工作台、笔记编辑、题库过滤、单题作答及反馈。归档保留资料，版本变化显式提示，回答幂等另存。旧API/路由/本机草稿及原学习闭环保留。

参考Exameow题库/单题/反馈、Open Notebook的来源/聊天/笔记关联，以及DeepTutor工作区与布局边界，采用固定提交审查并独立实现。无新增依赖、第三方运行时或真实模型调用。进度、正式诊断和管理继续复用原页面，未全面重写算法和每个页面。

## 数据、迁移和回退

schema13/45表升级为schema14/50表，仅增Notebook相关5表。现用迁移前后原45表摘要一致，141个既有资料/题库/知识及评估文件指纹保持；备份、副本及现用完整性/外键通过。副本在版本提交前注入失败，13库原表保持；回退先另存14库及新增Notebook，再建独立13恢复副本。旧代码接受恢复副本、拒绝14。

基础备份/源码：`data/local/notebook-rebuild-20261024-213652/`。现用备份：`data/local/eduagent.before-v13-0fc9ae3d034e.sqlite3`。旧服务在迁移后按保护规则拒绝新库；核对命令/父子进程后已重启本项目8000服务。未覆盖现用数据或进行破坏性回退。

证据在data/evaluation：`notebook-rebuild-migration-v1.json`、`notebook-rebuild-production-migration-v1.json`、`notebook-rebuild-deployment-v1.json`。恢复步骤详见指南。2026-10-25收尾不再迁移。

## 自动化及失败记录

| 验证 | 实际最终结果 |
| --- | --- |
| 后端全部回归 | 625通过，含Notebook专项10项 |
| 前端全部回归 | 225通过，含新交互及恢复专项15项 |
| 隔离真实HTTP | 23组通过，最终运行模拟provider2次、真实模型0次，含重启 |
| 构建/部署 | 构建、入口/页面块/API文档及数据摘要核验通过 |

HTTP使用临时数据库、真实本机端口、合成PDF/笔记/题目。覆盖创建/幂等/冲突、跨学生及Notebook隔离、空范围/越权拒绝、当前原文、受限模型证据、逐轮私人许可、PDF页码/空白页、本地检索、文件修改删除失效、历史快照、回答另存、题目关联、普通作答及重启不重放。正式学习事实和students.revision保持。模拟测试不代表真实模型或教学质量。

实际失败及修复如下，日志保留于data/local：

- Notebook专项初次9通过/1失败，为测试误用NotesService.update签名；修正后10通过。
- 首次构建暴露NotebookPage括号错误，已修正。
- 首次新前端12通过/1失败，聊天persist未导出导致异常；补齐后通过，再增加同ID重试及只读刷新测试。
- 首次后端612通过/13失败，涉及旧schema夹具/当前表数/路由数预期。补剥离新增5表后模拟旧库，保留历史版本断言；最终625通过。
- 首次HTTP误把原个人题创建200写成201预期，修正后通过，后续补PDF场景至23组。失败运行也是模拟模型，未产生真实模型请求。
- 浏览器发现原文样式依赖旧页面CSS块；已放回共享组件并复核900模态/1600并列region。另修复只读刷新覆盖未提交输入和切题保护。
- 文档收尾曾尝试替换CURRENT_STATUS失败，随后改为原位更新；没有因此删除或丢失文档。

最终HTTP的2次模拟与单元测试、早期失败运行、浏览器分别统计；所有真实付费调用为0。原55/15评估及其失败保留，不宣称识别或语义精度提升。

## 助手浏览器及待人工验收

实际操作在隔离库/合成内容，未向现用库写浏览器测试事实：

- [x] 恢复标识、主页、创建主题、卡片及真实内容计数。
- [x] 添加资料与本轮勾选分开，单一来源本地问答及匹配引用。
- [x] 点击引用、Escape关闭、焦点恢复至“查看引用1”。
- [x] 回答另存、Markdown/LaTeX预览、Ctrl+S、刷新恢复，未保存切换保护。
- [x] 关联已有题、明确开始、选择错误答案、普通反馈及不更新BKT提示。
- [x] 桌面1280/1600、中等900、窄屏390，实际检查无横向溢出；宽屏region及其他宽度模态正确。
- [x] 个人笔记默认未选；所查控制台无error/warn；浏览器无真实模型调用。
- [ ] 负责人用真实课件/习题核对识别、引用完整性和题型。
- [ ] 长时间弱网、所有题型/管理页、完整屏幕阅读器及真实模型新界面冒烟。
- [ ] 真实教学效果与BKT参数标定。

截图为隔离演示，位于data/evaluation：`notebook-rebuild-workspace.png`、`notebook-rebuild-practice.png`、`notebook-rebuild-narrow.png`、`notebook-rebuild-home.png`。2026-10-25默认1280桌面已复核主页与历史恢复，所查控制台无error/warn；本次未设置视口覆盖。

最终只读部署核验再次通过：schema14/50表、原45表摘要、141份既有文件指纹、所有入口/页面块；入口JS193511字节。相对基线实际68个文件新增或修改、没有源文件删除或新增依赖声明。后台服务停止的问题已通过启动现有兼容版本恢复；未再执行迁移。

## 文件与范围

完整文件清单为 `data/evaluation/notebook-rebuild-files-v1.json`，相对本轮源码ZIP逐文件比较。主要修改：

- 后端api/notebooks.py及app注册、services/study_workspace、Notebook仓储/DDL/迁移保护，专项测试与历史迁移夹具。
- 前端features/notebooks主页/问答/来源/笔记/API/状态，practice题库/卡片/反馈及输入恢复，app新布局/入口，SourceDrawer/ProductDialog与交互测试。原NotesWorkspace增加可选导航回调。
- snapshot_notebook_rebuild.py、verify_notebook_migration.py、verify_notebooks.py、deploy_notebook_database.py、verify_notebook_deployment.py。
- 当前状态、上下文、计划、README、设计/指南/报告/参考/历史检查点。AGENTS遵循用户最新内容，不自行改变授权范围。

原5点10题、40候选、BKT/评分/自评/课程体系/历史保持。未替换OCR、检索排序，未增加正式题或主观评分、多智能体/多租户平台。管理/正式学习页面仍有改进空间；后续依实际反馈选定目标，本轮结束后停止。
