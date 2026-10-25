# 重构第一阶段：课程空间与模块边界

> 2026-10-25后续UI/UX交付已统一这些模块的视觉和导航；新版使用、截图与限制见[UI/UX报告](UI_UX_REFACTOR_REPORT.md)和[设计系统](FRONTEND_DESIGN_SYSTEM.md)。本指南原模块/API约束继续保留。

> 历史阶段指南。用户随后批准的笔记本与习题产品重建已交付，当前入口、schema及使用方式见[CURRENT_STATUS](CURRENT_STATUS.md)和[Notebook指南](NOTEBOOK_REBUILD_GUIDE.md)。以下保留原阶段契约，不代表当前版本编号。

交付日期：2026-10-24（Asia/Shanghai）。[当前状态](CURRENT_STATUS.md) · [验收报告](REFACTOR_STAGE1_REPORT.md)。

## 使用

启动现有FastAPI服务后打开 `http://127.0.0.1:8000/#/study`。恢复原学习标识即可继续，无需重复上传资料或创建课程。

- **资料学习**：勾选本轮资料、提问、点击编号查看原文快照。桌面显示资料/问答，原文按需展开；窄屏用资料来源/助教问答/学习工作室标签。
- **练习**：明确开始或继续普通练习。原题识别和待处理题保留；未核验参考对照不冒充评分或BKT证据。
- **学习进度**：展示正式答题证据、自评和程序确定的下一步。没有正式答题时显示待诊断。
- **更多工具**：笔记、正式学习与复习、历史、原文资料。笔记未保存时仍有保存/保留/取消对话框。
- **课程管理**：课程构建、资料目录、知识体系、习题审核、发布。资料目录现在独立于题库；习题提取跳到练习区并预选资料，页面跳转本身不发识别请求。

资料目录的原文查看和资源用途/知识关联保留，关联草稿独立保存。读取最新资料前可以保留副本；旧revision不能覆盖新数据。上传、解析版本、选页视觉识别及删除仍在展开的“上传文件/图片，查看解析与版本”中。

可读上传仍能直接问答，不以知识体系确认或发布为阅读前置。目录标注部分提取；空文本页明确说明未识别内容不能参与检索，不宣称公式/图片已正确提取。

## 模块职责

| 路径 | 职责 |
| --- | --- |
| `app/CourseShell.vue`、`CourseWelcome.vue` | 布局、导航、课程提示及学习标识入口 |
| `app/CoursePage.vue` | 按路由加载页面，加载/失败反馈；不重试业务操作 |
| `app/courseSpace.js` | 当前学习者、既有学习会话、只读路由恢复与跨模块导航意图 |
| `app/featureRegistry.js`、`featureDefinitions.js` | 首次使用创建、已创建状态保留、草稿保护与最终释放 |
| `features/materials` | 文档状态、独立资源目录/关联、原文与本地课程片段检索 |
| `features/chat` | 来源选择、问答、引用、历史、不确定请求 |
| `features/practice` | 个人题库、普通练习、作答及提取任务 |
| `features/notes` | 笔记编辑、版本、独立草稿 |
| `features/learning` | 正式学习、复习、自评、指南与既有规则建议 |
| `features/authoring` | 课程构建与知识体系 |
| `shared/http.js` | 原请求超时、错误与不确定状态契约 |

App.vue仅组合空间、布局、通用提示和异步页面。既有组件和视图逐步复用；根级use*.js以及api/notes、workbench、resources保留兼容导出，旧测试和调用无需同时改路径。

业务状态工厂仍静态导入，**实例首次访问才创建**；页面视图和大型渲染依赖拆成异步构建块。没有引入新状态框架或事件总线。

## 生命周期与跨模块契约

1. 页面进入只初始化所需模块；study不创建题库/笔记/指南/发布，insights不创建Chat或读取私人来源目录。
2. 模块使用独立effectScope，离开页面不销毁状态；最终应用卸载停止监听。页面自己的计时器仍由原卸载逻辑清理。
3. 学生切换同步重置模块视图和授权，异步响应仍由各模块epoch/owner校验。笔记重置补为同步，避免旧响应短暂出现在新作用域。
4. 模块之间传稳定对象ID、来源版本和明确导航意图；指南读取已创建Chat的所选来源，不为了打开进度而初始化Chat。空选择仍不检索全库。
5. 问题导航通过prepare保护原问题，应用后消费路由意图；刷新不覆盖后来输入。
6. 导航保护只检查已创建模块，不为了保存草稿而初始化其他模块。存储失败时阻止离开；笔记保留原确认弹窗。
7. 旧本机存储键保持。资料目录新增`eduagent.material-library.v1.<student>`，只读迁移旧题库缓存的所选资源ID，不复制/修改原题目草稿。
8. 不确定请求继续查询原回执。页面挂载、刷新、前进/后退不会提交模型、分配正式题或提交作答。

旧hash路径均保留：study/practice/insights/learn/notes/history/resources/materials/bank/architecture/builder/publish。旧bank?view=practice转到practice并保留参数；资料、题目、笔记ID继续可定位。

## 接口与后端

没有修改FastAPI业务、数据库schema或后端测试。现有公开客户端createApi/ApiError不变，各业务域拥有自己的端点封装；新增客户端命名方法只是包装既有course-resources和回执路径。

资料目录只读取course-resources及明确选择的资源详情；不会顺带读取personal-bank/questions或practice会话。关联保存仍用既有PUT、expected_revision和request_id。保存期间后来输入不会被误标为已保存。

来源校验、引用、模型工具约束及逐轮外发由原后端继续强制执行。Chat、指南、视觉识别不共享外发同意。本阶段真实模型0次。

## 运行与验证

```powershell
# 根目录，服务需持续运行
.\.venv\Scripts\python.exe -m uvicorn eduagent.api.app:create_app --factory --host 127.0.0.1 --port 8000

Set-Location frontend
npm.cmd test
npm.cmd run build
Set-Location ..
.\.venv\Scripts\python.exe -m pytest backend/tests -c backend/pyproject.toml -q --basetemp data/local/refactor-stage1-new-run
.\.venv\Scripts\python.exe scripts/verify_learning_simplification.py --output data/evaluation/refactor-stage1-workflow-http-v1.json
.\.venv\Scripts\python.exe scripts/verify_learning_experience.py --output data/evaluation/refactor-stage1-pages-http-v1.json
.\.venv\Scripts\python.exe scripts/verify_refactor_stage1_deployment.py
```

测试使用独立库。Windows受限环境若在FAISS原生导入或loopback初始化失败，应记录环境失败，在正常本机环境运行已授权测试；不关闭来源/网络校验以凑通过。

## 数据与回退

没有数据库迁移。备份：`data/local/refactor-stage1-20261024-202146/`内的before.sqlite3、code-before.zip、baseline.json。部署检查同时验证备份可读、ZIP完整、原45表内容、schema、外键和历史归档原文。

回退前先保留当前数据库、原件及后来新增数据，停止服务；恢复匹配的旧前端源码/包清单并重建，再启动服务。后端和schema没有改变，因此不需要用旧数据库覆盖现库。不要在服务写入期间直接复制数据库文件；需要新的回退保留副本时使用SQLite backup。

旧项目状态原文按字节存于docs/history/pre-refactor-stage1，后续读CURRENT_STATUS，避免重复“最新”覆盖实际进度。

## 边界与下一阶段

原BKT/评分、5点10题/40候选、普通练习、自评和历史保持。未升级OCR、嵌入、检索排序、正式题准入或教学规则。入口包减少不代表全部模块总下载量或真实学习效果改善。

后续可优先验证真实课件解析覆盖与真实题目完整性；须另行确认，本阶段完成即停止。
