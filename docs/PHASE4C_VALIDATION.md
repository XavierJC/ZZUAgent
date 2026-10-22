# Phase4C-0～2 验证记录

2026-10-22。完整链路已实现并部署，停在4C-2；下一阶段未开始。工程验证不等于教师/学生内容审阅或真实教学效果。

| 验证 | 实际结果 |
| --- | --- |
| 后端全量 | 525项通过，含原501项回归、新提取/审核/练习/并发/迁移/来源保护 |
| 前端全量 | 143项通过，jsdom；非真实浏览器验收 |
| 构建 | 通过，主JS693.82kB；仍有默认500kB提示 |
| 新闭环隔离HTTP | 21组通过，2次模拟视觉，真实模型0 |
| 原课件HTTP | 15组通过，3次模拟视觉 |
| 原知识体系HTTP | 17组通过，模型0 |
| 原自评/指南HTTP | 18组通过，9次模拟模型 |
| 原工作台HTTP | 14组通过，15次模拟模型 |
| HTTP合计 | 85组；29次模拟，本轮真实0 |
| 主库迁移 | 8→9，27→34表；原27表摘要及文件保持，完整性ok/外键0错误 |
| 回滚副本 | 原代码接受恢复8库、拒绝9库；升级后副本保留，不覆盖现库 |
| 本机部署 | 首页/哈希资源/62条路径通过；新增题库7表仍空，没有测试数据写入主库 |
| 原学习配置 | BKT、正式题库、评分、先修图、学生revision及历史事实保持 |
| 真实材料 | 既有3页PDF只读提取21候选；既有两份视觉转录18/12候选，未人工验证、未写入题库 |
| 本轮真实模型 | 0；原库两条视觉记录/4次历史调用计数与备份一致，不计为本轮 |
| 浏览器人工 | 未执行；见指南清单，未绕过此前本机浏览器访问限制 |
| 真实教学效果 | 未验证 |

测试数据为独立数据库、自建PDF/图片/文本、合成答案和模拟模型。隔离HTTP最后单独执行一次原正式分配/作答，证明仍兼容；在此前个人题库操作中正式事实摘要完全一致。主库没有执行该合成作答。

本轮首先出现的失败及处理如实记录：旧迁移/路径计数断言仍预期schema8/50路径；新测试夹具对既有API参数和200响应的假定有误；HTTP脚本用错正式question嵌套字段。修正夹具/契约断言后重新通过完整回归。部署脚本曾误以为历史视觉调用计数应为0、且首个学生必有PDF，已分别改为与备份比较增量、使用实际资料所有者作用域；原数据始终未改。一次服务重启前保护检查将系统conhost当作未知子进程而拒绝停止，经只读核对后仅重启项目Python进程，没有误停其他程序。

代码复核额外修复：共有题设不能丢弃；旧本机草稿冲突需跨刷新保留；手工题在前的合并仍跟踪其他资料失效；用户修改答案后不能继续冒充原资料答案，原始类别另行保留。对应断言均已运行。

新增依赖0。原55条检索评估、5/15课程外误检与40题待审状态保持，没有使用原题识别候选数声称语义准确率提高。真实视觉外发/收费和新题生成均未执行。

详细JSON报告位于data/evaluation/phase4c-*.json。API/用法见[指南](PHASE4C_GUIDE.md)、[契约](PERSONAL_BANK_API.md)、[原题结构](PHASE4C_EXTRACTION_FORMAT.md)。

## 实际文件清单

下表由迁移前代码归档摘要与最终文件摘要生成；前端dist及本机数据库/日志为部署产物，不作为手工源码清单。API密钥和.env不在归档/报告中。

<!-- GENERATED_FILE_LIST -->

| 文件 | 状态 |
| --- | --- |
| `AGENTS.md` | 修改 |
| `README.md` | 修改 |
| `backend/src/eduagent/api/app.py` | 修改 |
| `backend/src/eduagent/api/body_limit.py` | 修改 |
| `backend/src/eduagent/api/document_schemas.py` | 修改 |
| `backend/src/eduagent/api/documents.py` | 修改 |
| `backend/src/eduagent/api/personal_bank.py` | 新增 |
| `backend/src/eduagent/documents/models.py` | 修改 |
| `backend/src/eduagent/documents/parsers/__init__.py` | 修改 |
| `backend/src/eduagent/documents/parsers/image.py` | 新增 |
| `backend/src/eduagent/documents/preflight.py` | 修改 |
| `backend/src/eduagent/documents/question_extraction.py` | 新增 |
| `backend/src/eduagent/documents/vision.py` | 修改 |
| `backend/src/eduagent/domain/personal_bank.py` | 新增 |
| `backend/src/eduagent/services/documents.py` | 修改 |
| `backend/src/eduagent/services/personal_bank.py` | 新增 |
| `backend/src/eduagent/services/resources.py` | 新增 |
| `backend/src/eduagent/storage/document_schema.py` | 修改 |
| `backend/src/eduagent/storage/migrations.py` | 修改 |
| `backend/src/eduagent/storage/personal_bank_schema.py` | 新增 |
| `backend/src/eduagent/storage/sqlite.py` | 修改 |
| `backend/tests/test_architectures.py` | 修改 |
| `backend/tests/test_documents.py` | 修改 |
| `backend/tests/test_migrations.py` | 修改 |
| `backend/tests/test_personal_bank.py` | 新增 |
| `backend/tests/test_personal_migration.py` | 修改 |
| `backend/tests/test_self_assessments.py` | 修改 |
| `backend/tests/test_tutor.py` | 修改 |
| `backend/tests/test_web.py` | 修改 |
| `backend/tests/test_workbench.py` | 修改 |
| `docs/DEVELOPMENT_PLAN.md` | 修改 |
| `docs/PERSONAL_BANK_API.md` | 新增 |
| `docs/PHASE4C_EXTRACTION_FORMAT.md` | 新增 |
| `docs/PHASE4C_GUIDE.md` | 新增 |
| `docs/PHASE4C_VALIDATION.md` | 新增 |
| `docs/PROJECT_CONTEXT.md` | 修改 |
| `docs/requirements/PHASE4C_TASK_BRIEF.md` | 新增 |
| `frontend/src/App.vue` | 修改 |
| `frontend/src/__tests__/personal-bank.test.js` | 新增 |
| `frontend/src/api.js` | 修改 |
| `frontend/src/components/DocumentManager.vue` | 修改 |
| `frontend/src/components/PersonalBankWorkspace.vue` | 新增 |
| `frontend/src/components/StudyWorkbench.vue` | 修改 |
| `frontend/src/personal-bank.css` | 新增 |
| `frontend/src/usePersonalBank.js` | 新增 |
| `scripts/verify_architectures.py` | 修改 |
| `scripts/verify_documents.py` | 修改 |
| `scripts/verify_personal_bank.py` | 新增 |
| `scripts/verify_personal_bank_deployment.py` | 新增 |
| `scripts/verify_personal_bank_migration.py` | 新增 |
| `scripts/verify_phase4a.py` | 修改 |
| `scripts/verify_workbench_answers.py` | 修改 |
