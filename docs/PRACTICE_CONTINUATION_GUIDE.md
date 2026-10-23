# 正式题耗尽后的练习续接（2026-10-23）

## 原因与修复

原正式库只有10道工程演示题，每个知识点2道。正式规划不重复分配已经作答的题；两题做完仍未达到推进条件时，返回 `insufficient_questions`。原页面只有暂停说明，导致学生无法继续作答。不是网络或模型阻塞，也不能把题量不足解读成已经掌握。

本次增加“复习已做题（不更新掌握度）”，可循环复习、核对原答案和解析，错题优先。直接使用当前学习标识的已评分分配快照，不依赖个人题库是否已有审核通过的题。原10题仍待内容审阅，未自动确认个人题、40道候选或真实试卷答案。

## 使用

1. 刷新本机网页，在“我的学习”的新题耗尽提示中点击“复习已做题（不更新掌握度）”。
2. 选择答案，点击“核对复习答案”，查看原解析，再点击“复习下一题”。一题范围支持“再练一遍”。可切换全部已做题或某个已学知识点。
3. “返回正式学习”回到原安排；“请助教讲解薄弱点”和“进入普通练习”复用现有入口，不自动调用模型。

进度、未提交选项及最近50次本机复习回执单独存于当前浏览器，按演示标识分开。切换页面或刷新可恢复；清理浏览器/换设备不会同步。存储不可用时显示仅当前页面保留。正式作答次数与掌握度不包含本机复习，不能将其当作服务端评分事实或教学效果证据。演示标识仍不是真实身份认证。

## 数据与API

`GET /api/v1/students/{student_id}/review-exercises` 返回当前标识已经作答的题目，包括 `review_key`、原 `event_id`、原题目版本/题干/选项、原参考答案与解析、原作答结果/时间、原题库版本。`mode=self_review`、`bkt_updated=false`、`record_storage=browser_only`。

后端在一致事务内读取当前学生、原分配与原评分回执；不从现用题库替换历史题干。题目ID/版本/答案选项不匹配时跳过；未知标识404，未做题返回空列表。没有复习POST接口；前端仅作非正式自查，从不调用正式 `/answers`、分题、个人题准入或模型接口。快照摘要只用于恢复校验。

数据库仍schema12/45表，**没有迁移或新增表**。修改前备份 `data/local/review-continuation-dc3dafcd/before.sqlite3`，SHA256 `6667a6862bbe1849983e8f48b9a3ddddc5ca0cd29f065a3f5b7b60977499d20f`。部署后45表数据摘要与备份全部一致，完整性/外键通过。无需数据库回滚；代码回退时保留现库和本机复习记录，不覆盖数据库。正式题库、BKT参数、教学策略、先修图、题目审核及所有旧事实保持。

## 实际验证

- 后端全量 **587 passed**；前端全量 **172 passed**；构建通过。主JS761.64kB，原有大于500kB包体提示仍存在。
- 新后端4项验证只读复习、原快照、学生隔离、HTTP恢复及正式状态保持；新前端9项覆盖页面入口、重复核对、刷新恢复、跨页面、学生切换异步竞争、存储失败、过期快照及失败重读。
- 独立真实HTTP **9组通过**，服务启动2次；复现旧流程和发布会话的两题耗尽、个人库为空仍可复习、其他学生隔离、原题/待审标记、重复GET及禁止POST、全部45表不变。复习作答是客户端自查，由前端自动测试验证，未声称服务端新增评分。
- 本机8000部署检查通过：新静态资源/新GET接口可用，7个已有作答标识均能读取自己的复习题，45表摘要保持。真实和模拟模型均0次。
- 报告：[隔离HTTP](../data/evaluation/review-continuation-http-v1.json)、[本机部署/数据核对](../data/evaluation/review-continuation-deployment-v1.json)。

实际浏览器桌面/窄屏/键盘验收未执行，未绕过此前本机浏览器访问拒绝。待人工检查：刷新后出现入口；Tab/方向键选择并Enter核对；翻题和切换知识点；离开再返回；刷新恢复；窄屏长题干/公式不溢出；正式统计不增加。

## 修改文件

- 后端：`backend/src/eduagent/services/review.py`、`backend/src/eduagent/api/course_workspaces.py`。
- 前端：`frontend/src/api.js`、`useReviewPractice.js`、`App.vue`、`components/QuestionPanel.vue`、`components/ReviewPracticePanel.vue`、`views/LearningOverview.vue`；构建产物 `frontend/dist/`。
- 验证：`backend/tests/test_review.py`、`backend/tests/test_web.py`、`frontend/src/__tests__/review-practice.test.js`、`scripts/verify_review_continuation.py`、上述2份JSON报告。
- 上下文：本指南、`AGENTS.md`、`README.md`、`docs/PROJECT_CONTEXT.md`、`docs/DEVELOPMENT_PLAN.md`。

## 仍存在的限制

本次解决耗尽后无法继续作答的页面断点，没有增加新的正式测评证据。正式复测仍需独立准入/评分配置/版本发布的新题，或原有其他未耗尽的合法正式分配；复习不能绕过先修条件、重置历史或靠背答案反复抬升BKT。待审草稿与真实课程候选保持待审，不自动推进正式题库准入、BKT扩点或其他阶段。
