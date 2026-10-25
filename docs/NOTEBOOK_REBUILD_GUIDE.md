# 笔记本与练习工作区使用指南

日期：2026-10-24。用户恢复并授权的产品重建，依据[设计](NOTEBOOK_REBUILD_DESIGN.md)，与上一轮纯前端模块拆分分别记录。实际验证见[报告](NOTEBOOK_REBUILD_REPORT.md)。

## 现在怎样使用

启动方式保持README中的命令，打开 `http://127.0.0.1:8000/#/notebooks`。恢复原演示学习标识即可访问原资料；原资料不会自动复制或迁移到某个笔记本。

1. 在主页新建一个学习主题，例如“模型评估与选择”。
2. 打开“添加或管理资料”，勾选已有课程资料、上传文件或个人笔记；也可在这里显式上传并本地解析新资料。保存的是关联及版本，不复制正文。
3. 在左侧另行勾选参与这次问答的资料。**加入笔记本、打开原文、参与问答是三个不同动作**。个人笔记默认不参与问答。空选择不能发送或扩展全库。
4. 提问时选择本地检索或AI讲解。个人笔记、上传及教师资料相关片段外发需要本轮明确同意；下轮重新同意。无模型时仍可本地检索。
5. 点击正文编号或下方引用卡片查看原文快照。宽桌面在右侧显示原文，中等宽度及窄屏使用抽屉。Escape关闭并恢复触发控件焦点。
6. “回答另存为笔记”仅创建一次，随后可编辑Markdown/LaTeX；Ctrl+S保存。原回答和引用快照独立保留。普通笔记草稿沿用原机制，切换前提示保存或保留本机草稿。
7. 切换“练习”，从已有题库添加题目，或使用当前关联资料派生的已有普通题。明确点击开始才创建普通练习；挂载、刷新和恢复不分题。
8. 客观题只有人工确认的标准答案才判分；其他题记录作答和参考对照，不能冒充正式评分。切换练习前先保存未提交作答草稿。正式BKT诊断在独立入口。

主页支持搜索、归档与恢复。归档保留原件、笔记及历史，笔记本写入和新问答停用。资料更新后原关联显示过期，需重新选择当前版本。移除关联不删除原件。

## 架构与数据库

复用FastAPI、SQLite、Vue3、现有Workbench/普通练习服务及LangGraph单一Agent。新增 `services/study_workspace` 能力边界和 `NotebookRepository`，没有引入第三方项目运行时或新外部服务。

schema13→14增量新增5表，总表数45→50：

| 表 | 保存什么 |
| --- | --- |
| notebooks | 学生/课程、稳定UUID、标题、说明、独立revision、归档和时间 |
| notebook_sources | 显式资料或题目关联、来源类型/ID/版本、标题快照 |
| notebook_operations | 学生作用域内的请求摘要及写入回执 |
| notebook_runs | 笔记本问答关联、请求摘要、不可变上下文及执行前预留 |
| notebook_practice | 笔记本与独立普通练习会话的关联 |

关联类型区分course_material、uploaded_document、teaching_material、personal_note、personal_question。题目仅供练习，不作为聊天检索来源。来源本体及正式学习事实继续由原模块负责。

问答上下文固定学生、课程、笔记本ID/revision及来源ID/版本，再复用原受控检索与模型工具。请求预留先持久化；同ID同内容读取原结果，不同内容拒绝。预留后中断而无法确认执行时返回uncertain，不自动重发模型。普通元数据写入可由用户明确重试**同一编号/内容**。

历史引用保留原快照，笔记本范围变化及来源变更显式标记；历史快照不重新成为当前来源。笔记本只关联原笔记，因此同一篇笔记可以在多个主题中使用，修改后其他关联也可能过期。演示student_id仍不是身份认证。

## API契约

前缀 `/api/v1/students/{student_id}/notebooks`。所有请求均在服务端再次验证学生、课程、成员、版本与归档状态，未知控制字段拒绝。

| 方法/路径 | 用途与关键字段 |
| --- | --- |
| GET / | 当前笔记本；`?archived=true`读取归档 |
| POST / | `request_id,id,title,description`，稳定UUID；201 |
| GET /requests/{request_id} | 只读查询写入回执 |
| GET /{id} | 详情、当前关联状态及版本 |
| PATCH /{id} | `id,request_id,expected_revision,title,description,archived` |
| PUT /{id}/sources | `request_id,expected_revision,sources`；整体替换显式关联，至多150项 |
| POST /{id}/sources/open | 来源三元组、`expected_revision`、可选page |
| POST /{id}/questions | 原问答字段加`expected_revision`；1～55个明确来源 |
| GET /{id}/runs[/{request_id}] | 仅此笔记本历史与单轮回执 |
| POST /{id}/runs/{request_id}/note | 幂等另存并关联可编辑笔记 |
| GET /{id}/practice/questions[/{question_id}] | 当前笔记本的题目范围 |
| POST /{id}/practice | `request_id,expected_revision,question_id`，明确开始普通练习 |
| GET /{id}/practice/sessions[/{session_id}] | 范围内普通练习历史/详情 |
| POST /{id}/practice/sessions/{session_id}/answer | 原普通作答契约 |
| PUT /{id}/practice/sessions/{session_id}/draft | 原作答草稿契约 |
| GET /{id}/practice/requests/{request_id} | 限定笔记本的练习回执 |

冲突409、不可见资源404、请求结构错误422，数量上限使用既有413。旧Workbench、笔记、个人题库和正式学习API继续保留。Notebook前端的聊天/练习本机缓存增加笔记本命名空间，原缓存键保持可读，不自动混入新笔记本。

## 迁移与回退

已在备份副本完成迁移、完整性/外键、故障注入和旧代码边界验证，再执行现用迁移。生产备份：`data/local/eduagent.before-v13-0fc9ae3d034e.sqlite3`。原45表摘要全部保持。

基础备份/源码：`data/local/notebook-rebuild-20261024-213652/`。迁移副本记录见 `data/evaluation/notebook-rebuild-migration-v1.json`，现用记录见 `notebook-rebuild-production-migration-v1.json`。

**回退不得用旧备份覆盖升级后的现用库。** 先停写、用SQLite backup再保存schema14和新增数据；另建schema13恢复副本，配套原schema13代码及原资料目录，显式指定副本路径后核验。新笔记本数据保留在schema14副本，旧程序不能读取。演练副本中已同时保留一条升级后新增笔记本和独立schema13恢复库，旧13接受恢复副本且拒绝14。没有执行破坏性生产回退。

## 界面与验收

桌面主导航为学习笔记本、题库与练习、学习进度，资料维护/审核/知识体系/课程发布收进管理区。笔记本内聚焦问答、练习、笔记，保留原正式学习入口；不是独立移动App。

自动验证命令：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -c backend/pyproject.toml -q
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe scripts/verify_notebooks.py
.\.venv\Scripts\python.exe scripts/verify_notebook_migration.py
.\.venv\Scripts\python.exe scripts/verify_notebook_deployment.py
```

`deploy_notebook_database.py`是已完成的一次性显式13→14入口，不应重复执行。验证脚本使用独立数据，HTTP和浏览器测试为合成内容/模拟服务，没有真实付费模型请求。现有解析、检索精度及内容人工审核限制继续保留。
