# 简化学习流程交付报告

> 后续失败资料删除入口已补齐，见[SOURCE_DELETE_REPORT](SOURCE_DELETE_REPORT.md)。本页保留该轮248项验证和当时全部50表不变的证据，不能作为后来删除操作后的即时摘要。

日期：2026-10-25（Asia/Shanghai）。[使用指南](HUMAN_WORKFLOW_GUIDE.md) · [当前状态](CURRENT_STATUS.md)。

## 交付结果

按用户本轮明确要求，在现有Vue3工作区内减少正常学习的设置和重复确认。主导航收拢为学习、练习、进度，练习内区分自由练习与测一下；昵称、主题名称和学习目标可用默认值。正常问答不要求先构建/发布课程，诊断开始按钮复用原后端完成绑定和分题。

资料单项加入即保存；成功上传后自动加入当前主题并选中新增非笔记资料。没有扩大已有选择、自动勾选个人笔记或授予外发同意。习题整理完成可直接开始练习，缺项单独提示。模型禁用时明确降级本地整理/检索，不以本地规则冒充AI输出。旧路由、管理功能和原草稿键保留。

## 实际修改

- 应用入口与导航：`App.vue`、`app/AppSidebar.vue`、`CourseShell.vue`、`CourseWelcome.vue`、`courseSpace.js`，新增`shared/human-workflow.css`。
- 学习主题：`features/notebooks/LearningHome.vue`、`NotebooksPage.vue`、`NotebookPage.vue`、`NotebookSources.vue`、`NotebookChat.vue`、`useNotebooks.js`。晚到的保存回执不能把用户拉回旧主题。
- 练习与诊断：`features/practice/PracticePage.vue`、新`PracticeModes.vue`、`ExerciseDesk.vue`、`ExerciseCard.vue`、`PracticeFeedback.vue`；`features/learning/FormalLearningPage.vue`、`useWorkspace.js`；`views/LearningInsights.vue`。
- 共用入口：`components/QuickDocumentUpload.vue`、`QuestionImportPanel.vue`、`QuestionPanel.vue`。失败解析不自动关联，上传组件关闭后不再发出完成事件，正式题同一decision只读刷新保留选择。
- 验证：新增`frontend/src/__tests__/human-workflow.test.js`与`scripts/verify_human_workflow_deployment.py`。同步当前状态、计划、项目约束、README、AGENTS及旧阶段文档指针。

完整本轮前后文件差异清单见[部署记录](../data/evaluation/human-workflow-deployment-v1.json)。之前正式准入的未提交后端修改予以保留，本轮未再修改后端源码或测试。

## 参考与实现

实际重新阅读固定缓存中的Open Notebook `SourcesColumn.tsx`、Exameow `QuestionCard.vue`、DeepTutor `AppShell.tsx`，采用围绕资料的学习主题、单题专注与低频设置收起的原则。在现有Vue组件独立实现，没有复制第三方代码、运行第三方依赖或新增服务。完整commit与许可证见[参考记录](OPEN_SOURCE_UI_REFERENCES.md)。

## 验证结果

| 验证 | 实际结果 |
| --- | --- |
| 前端全量 | 248/248，21文件；原234项加14项专项 |
| 最终文案修正后专项 | 14/14通过；将本地整理也会出现的“AI整理”改为“自动整理” |
| 生产构建 | 通过，162模块；入口JS约139.85kB，13个页面chunk |
| 本机部署只读检查 | 入口、入口资源与13个页面chunk均和本地dist一致，健康接口正常 |
| 现用数据 | schema14/50表，全部50表摘要与本轮前备份一致，185个既有资料/题库/知识/评估文件指纹保持 |
| 后端和依赖 | 全部后端源码/测试及前端package/lock与本轮前指纹一致；本轮没有重跑或冒称新增后端全量结果 |
| 助手浏览器 | 合成独立库，桌面1280×720、手机390×844；五个手机页面均无文档横向溢出 |
| 模型 | 真实付费及其他真实模型请求0；浏览器明确禁用Agent/视觉，仅本地检索/整理，单元测试使用模拟接口 |

14项专项覆盖主导航、默认昵称、显式开始后绑定/分题、切换学生/关闭页面后停止后续分题、原待提交恢复、主题默认名及单一初始创建入口、单项关联、成功上传选择范围、个人笔记保持未选、失败解析、晚到主题保存和同题/换题刷新选择。

浏览器实际完成：开始学习→空名创建主题→上传合成资料→自动关联并只选新资料→本地问答与引用；练习→测一下→单次开始取得题目→选择答案→只读刷新仍保留选择→明确提交更新一次；粘贴合成习题→本地整理→直接开始练习→提交普通作答并显示参考对照。隔离学生最终revision仍为1，证明后一条普通练习没有新增正式revision。现用库没有新增学生、作答或任何其他表变动。

证据：[浏览器流程与尺寸](../data/evaluation/human-workflow-browser-v1.json)、[部署与指纹](../data/evaluation/human-workflow-deployment-v1.json)、[学习截图](../data/evaluation/human-workflow-study.png)、[测评截图](../data/evaluation/human-workflow-diagnosis.png)、[手机截图](../data/evaluation/human-workflow-mobile.png)。截图均使用合成资料，不代表真实模型回答或教学效果。

核验中出现并处理的问题：部署脚本首次漏统计基线中的`.gitignore`，补入后所有基线文件存在；受限环境阻止本机套接字，使用获准的只读本机验证后通过。构建替换时浏览器仍持有旧页面chunk，触发原有资源失败提示，刷新最终构建后恢复。手机菜单与主题内按钮同名导致自动化定位歧义，按已显示的菜单作用域定位后正常。没有通过关闭来源校验或取消断言使检查通过。

## 边界与剩余事项

本轮没有新增AI识别能力、算法精度、自动补答案、主观评分、BKT扩点或以后新题自动正式准入。既有40共享题及3道仅原标识可用的个人题、缺项/争议题处理沿用此前交付。真实模型通路未在本轮调用验证，不能据此保证识题准确率。真实移动设备、读屏、真实学生使用效果待实际体验。

备份`data/local/human-workflow-20261025-211109/`含现用库在线备份、代码ZIP和逐表/文件基线。助手浏览器使用8139端口与独立合成库，完成后停止临时服务；8000现用服务保留。没有数据库迁移，界面回退不覆盖学习数据。本轮到此结束，后续范围依据实际反馈另行确定。
