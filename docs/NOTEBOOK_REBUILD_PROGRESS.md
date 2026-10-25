# 笔记本与习题产品重建：历史暂停检查点

> 此为暂停时原始记录。用户随后明确回复“继续工作”，已恢复并完成，当前状态见[CURRENT_STATUS](CURRENT_STATUS.md)和[本轮报告](NOTEBOOK_REBUILD_REPORT.md)。以下“未完成”“4表/49表”“未迁移”只描述暂停时状态，当前已为5表/50表。

状态：**用户于2026-10-24（Asia/Shanghai）明确要求暂停，等待之后继续。** 不因本文件或旧计划自行恢复开发。当前未完成、未部署本轮重建。

## 已完成的审查

已读取三个项目的固定提交与许可证，并下载针对性源码到`data/reference-code/`，未运行第三方项目：

- Exameow：`ab792a9ae961a128de664b17268cd062587bb95e`，Apache-2.0。已读PracticeView、practice store、QuestionCard、AnswerSheet、PracticeResult、BankListCard、ModeSelector、题目表格与错题存储。
- Open Notebook：`a0f6f3081ae06328f0a451b3a3ef2959ca25721d`，MIT。已读Notebook领域/API、来源/聊天/笔记列、上下文构建、架构及Notebook范围检索ADR。
- DeepTutor：`a31d82624c27d75f4e771d4fcb78dce16470b383`，Apache-2.0。已读工作区上下文/导航/服务、AppShell/Sidebar、练习页面、问题流水线等。

方向已记录于[本轮设计](NOTEBOOK_REBUILD_DESIGN.md)：Notebook关联共享资料与笔记，问答历史按Notebook隔离；练习拆分题库/单题/结果；桌面优先重新设计默认页面，保持现有正式学习边界。

## 备份与现用系统

本轮开发前备份：`data/local/notebook-rebuild-20261024-213652/`。

- `before.sqlite3`：实际schema13、45表；完整性和外键通过。
- `code-before.zip`：本轮修改前的前后端、测试、文档、脚本和包清单。
- `baseline.json`：原45表摘要、列及141个既有资料/评估文件指纹。
- 指针：`data/local/notebook-rebuild-current.json`。

**没有执行现用库迁移，没有本轮前端构建/部署，没有真实模型调用。** 现用前端仍为上一轮`index-CtJnKjKI.js`。现用schema仍应为13；源码已开始改为14，因此恢复后不可直接重启新代码连接现库，必须先完成副本迁移验证和受控切换。

## 已写入但未完成验收的代码

新增：

- `backend/src/eduagent/storage/notebook_schema.py`：4张增量表的DDL，notebooks/notebook_sources/notebook_operations/notebook_runs；拟schema14，若采用当前DDL总表数为49。
- `backend/src/eduagent/storage/notebooks.py`：Notebook仓储。
- `backend/src/eduagent/services/study_workspace/__init__.py`、`context.py`：不可变Notebook请求上下文。
- `backend/src/eduagent/services/study_workspace/notebooks.py`：Notebook创建/修改/归档、来源关联、幂等、预览、受控问答/历史/另存笔记、题目范围与普通练习启动的初步服务。
- `backend/src/eduagent/api/notebooks.py`：学生子资源API及严格输入模型。
- `scripts/snapshot_notebook_rebuild.py`：开发前备份和指纹。

已修改：

- `storage/migrations.py`：SCHEMA_VERSION改为14，新增表迁移和完整性要求；尚未执行现用库迁移。
- `storage/sqlite.py`：不兼容版本提示改为schema14。
- `api/app.py`：注册Notebook路由。
- `docs/NOTEBOOK_REBUILD_DESIGN.md`、`CURRENT_STATUS.md`、`DEVELOPMENT_PLAN.md`：记录新授权与范围。

本轮**尚未修改新的前端页面**；源码当前为进行中的后端增量，不是可宣布交付的完整版本。

## 实际验证

执行了独立测试：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_bkt.py backend/tests/test_notes.py -c backend/pyproject.toml -q --basetemp data/local/notebook-core-pytest
```

结果：**47项通过**。这是原BKT/笔记的局部回归，不能当作新Notebook能力、完整回归、真实HTTP或浏览器验收。新功能专项测试、迁移演练及全部前端工作均未完成。

## 恢复后的具体顺序

1. 先读AGENTS、CURRENT_STATUS、本检查点和NOTEBOOK_REBUILD_DESIGN；确认用户已恢复任务。
2. 审查当前Notebook服务，补新功能专项测试，验证幂等、范围、学生隔离、历史恢复和版本竞争。
3. 完成普通练习的Notebook关联：计划增加独立`notebook_practice`表和会话/答案/草稿的范围接口，但**目前没有实现，也没有加入DDL**。先确定最终表数，再完成迁移测试。
4. 补Notebook写操作回执GET，供前端超时后只读恢复；不自动重发。检查已有请求与全局工作台请求编号的冲突处理。
5. 复核`save_answer`：归档/作用域检查应先于任何笔记写入；删除笔记重放不恢复、不另建。检查Notebook变更期间的模型前/工具/返回校验。
6. 在独立数据库验证13→14：原45表逐表摘要保持、事务失败回滚、完整性/外键、旧13代码拒绝14、新库和新增数据可保留回退。调整旧测试中“当前schema”断言，不能盲目替换历史版本测试。
7. 新增Notebook前端状态/API和真实持久化主页/详情。资料、对话和笔记归属Notebook；默认个人笔记不选，授权逐轮独立。原有草稿和路由保留兼容。
8. 以DeepTutor为参考重做桌面布局、侧栏和问答区；以Exameow为参考重做题库卡片、专注题目、答案区与结果页。无需引入其整套前后端或复杂基础设施。
9. 完整回归、隔离HTTP、桌面/窄屏/键盘验收；通过后再停旧服务、执行已验证迁移、构建并部署。

后续设计细节尚属工作草案：Notebook可通过来源派生相关原题，也可显式关联个人题；原件/笔记/题目本体仍各自权威。Notebook范围由后端执行，不能仅前端过滤；空范围不查全库。付费模型本轮先为0，原BKT、正式题库和评分规则不改。

恢复时避免重新审查/下载全部仓库；`data/reference-code/<project>/reference.json`和`tree.json`已固定提交，直接读取保存的源码即可。
