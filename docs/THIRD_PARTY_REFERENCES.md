# 本轮开源参考与归属

2026-10-24，按用户指定仓库阅读固定版本源码。参考文件和许可证存放在本机忽略目录 `data/reference-code/`，未执行第三方程序。EduAgent保留Vue3/FastAPI/SQLite及原服务，没有嵌入三个项目的完整运行时。本轮功能为独立实现，尚无直接移植的第三方源码段或图标/品牌资产；后续若直接移植应另附许可和来源。

| 项目/固定提交 | 许可证 | 实际参考 | 在EduAgent中的实现 |
| --- | --- | --- | --- |
| [Exameow](https://github.com/heshengtao/exameow/tree/ab792a9ae961a128de664b17268cd062587bb95e) | [Apache-2.0](https://github.com/heshengtao/exameow/blob/ab792a9ae961a128de664b17268cd062587bb95e/LICENSE) | PracticeView、practice store、QuestionCard、PracticeResult及分类列表 | 题库过滤→专注单题→反馈拆分为ExerciseDesk、ExerciseCard、PracticeFeedback；继续使用原服务端普通练习 |
| [Open Notebook](https://github.com/lfnovo/open-notebook/tree/a0f6f3081ae06328f0a451b3a3ef2959ca25721d) | [MIT](https://github.com/lfnovo/open-notebook/blob/a0f6f3081ae06328f0a451b3a3ef2959ca25721d/LICENSE) | notebook领域/API、Sources/Chat/Notes列、来源关联及范围检索ADR | 持久Notebook、共享原件关联、分主题会话/笔记/练习；空来源仍拒绝全库扩展 |
| [DeepTutor](https://github.com/HKUDS/DeepTutor/tree/a31d82624c27d75f4e771d4fcb78dce16470b383) | [Apache-2.0](https://github.com/HKUDS/DeepTutor/blob/a31d82624c27d75f4e771d4fcb78dce16470b383/LICENSE) | workspace context/service/navigation、AppShell/Sidebar、练习页面 | 固定服务端NotebookContext、组合现有能力、桌面侧栏/紧凑工具栏与按任务分区 |

没有采用其自动生成题或模型判分替换正式评分，没有引入多智能体、大型数据库或认证平台。普通题型、回答校验、BKT和来源外发规则仍由EduAgent原有契约约束。

上述是源码和设计参考，不是对第三方仓库当前部署质量、识别准确率或真实教学效果的验证。固定版本有利于复核；不把后续仓库变化自动视为本轮已经吸收。
