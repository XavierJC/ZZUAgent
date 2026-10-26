# 重构第一阶段验收报告

> 2026-10-26PDF局部容错与单份真实课件恢复另见[报告](PDF_PARTIAL_RECOVERY_REPORT.md)；以下保留原阶段验证，最新数字只以CURRENT_STATUS为准。

> 后续失败资料删除入口及实际删除验证另见[SOURCE_DELETE_REPORT](SOURCE_DELETE_REPORT.md)，本页仍保留原阶段证据。

> 2026-10-25后续人性化流程简化另见[本轮报告](HUMAN_WORKFLOW_REPORT.md)。本页保留旧阶段证据，不能将旧测试数字当作最新结果。

> 2026-10-25新增前端UI/UX全面优化已交付，另见[本轮报告](UI_UX_REFACTOR_REPORT.md)。本页以下保留旧阶段数字与失败证据；最新结果只读CURRENT_STATUS。

> 本报告保留2026-10-24纯前端重构的原验证结果。后续笔记本产品重建另见[报告](NOTEBOOK_REBUILD_REPORT.md)；2026-10-25收尾只补文档与只读核验，未据此扩展新后端范围。

日期：2026-10-24（Asia/Shanghai）。[使用与模块契约](REFACTOR_STAGE1_GUIDE.md) · [当前状态](CURRENT_STATUS.md)。

## 结果

已完成课程学习空间、应用外壳/页面/业务状态拆分、独立资料目录、按域API封装和文档归档。学生保留三个主入口和原辅助/管理能力，旧hash链接与本机草稿兼容。没有复制第三方仓库代码或新增依赖。

本轮按用户批准的第一阶段实施，未进入解析/检索算法升级、正式题库或BKT调整。

## 实际验证

| 项目 | 实际结果 | 说明 |
| --- | --- | --- |
| 开发前前端 | 195/195通过 | 原测试基线 |
| 本轮后端 | 615/615通过 | 87.99秒；后端源码/测试未修改，隔离测试库 |
| 最终前端 | 210/210通过，18文件 | 195原有＋15专项；最终12.34秒 |
| 构建 | 通过 | 11个异步页面块；入口JS179081字节/gzip约63.19kB |
| 原入口对照 | 约795.45kB/gzip265.66kB | 公式渲染拆为约433.97kB块；不是总下载/弱网基准 |
| 实际HTTP | 29组通过 | 工作流15＋页级预览14；服务重启/原回执恢复覆盖 |
| HTTP模型 | 模拟4次、真实0次 | 本地合成资料，无真实笔记/课件外发 |
| 助手真实浏览器 | 14组检查 | 合成隔离库；1280/1440/900/390宽度 |
| 现用数据 | schema13、45表内容摘要全部保持 | 完整性/外键、备份、源码ZIP和归档一致 |

HTTP记录：[工作流](../data/evaluation/refactor-stage1-workflow-http-v1.json)、[逐页预览](../data/evaluation/refactor-stage1-pages-http-v1.json)。部署/数据：[核验](../data/evaluation/refactor-stage1-deployment-v1.json)。浏览器：[检查记录](../data/evaluation/refactor-stage1-browser-v1.json)。

新增专项测试覆盖：状态按需创建/释放、循环依赖拒绝、存储失败保护、页面请求隔离、来源与问题草稿保留、浏览器返回、上传文件保留、导航意图消费、学生切换/旧响应拒绝、资料目录独立恢复、关联保存期间输入保护、不确定回执和草稿副本。

原App集成测试改为等待真实动态页面导入；保留原行为断言，没有以屏蔽页面或取消验证使测试通过。

## 浏览器实际路径

使用自建三页PDF和两道合成普通题，模型服务禁用：

1. 选择课程资料及自建PDF，本地提问，取得第3/1页真实片段；点击引用查看当时快照与原件版本。
2. 输入新问题，跳到进度，再浏览器返回；问题和2项选择保留。进度为正式作答0次、0/5有依据，其余待诊断。
3. 显式开始单选题，提交后仅显示未核验参考对照；下一题进入简答，保存文字草稿，跨页/刷新恢复。
4. 进入独立资料目录，打开原文，保存合成资源用途；按稳定资源ID跳转习题导入，预选正确资料。未点击发送，识别调用0。
5. 新建合成笔记，验证取消/保留草稿、焦点、返回和Control+S保存。
6. 窄屏标签、原文Escape关闭/焦点恢复；页面scrollWidth均未超过视口，辅助导航自身允许滚动。最终控制台无error。

隔离库最终：正式attempts/decisions/tutor_runs/自评记录均0，学生revision0；2个普通练习会话、1次普通作答、1篇合成笔记、1轮本地问答，模型调用0。未写现用库。

截图：[桌面](../data/evaluation/refactor-stage1-screenshots/desktop-study.jpg)、[窄屏](../data/evaluation/refactor-stage1-screenshots/mobile-study.jpg)。图中为本地合成资料反馈，不是模型质量展示。

## 失败与处理

- 初次受限环境后端回归在FAISS原生导入发生Windows异常，12项收集错误；记录后改在正常本机执行，615项全部通过。没有修改原生库或业务校验。
- 页面异步化使原有“单次flush即可渲染”假设失效，先出现15项、随后7项前端失败。补充动态导入等待与明确页面切换等待后原195项通过。
- 新专项学情夹具缺少versions导致3项失败/渲染异常，补齐真实响应契约后通过；没有放宽产品字段校验。
- 浏览器初次练习读取到同源旧合成库的本机session指针，提示不存在；显式选择当前题目后继续正常，未套用旧答案。该提示仍是更换演示数据库时的兼容限制。
- 自动操作有标题/焦点目标定位失败，改按实际可见控件完成；没有绕过浏览器安全警告或模型授权。

## 数据与回退

备份目录：`data/local/refactor-stage1-20261024-202146/`。SQLite backup、code-before.zip、baseline.json均验证可读；结束时45表摘要和schema13保持，完整性/外键通过。旧AGENTS/README/上下文/开发计划归档与源码ZIP中的原件逐字节相同。

未执行DDL或数据迁移，后端业务与测试内容摘要保持。回退只需保留当前数据后恢复旧前端代码并重建；不得以before.sqlite3覆盖后来新增的学习数据。

## 实际修改文件

完整逐路径清单见[文件清单JSON](../data/evaluation/refactor-stage1-files-v1.json)，与开发前源码ZIP计算比较。

- 应用：App.vue；app目录中的CourseShell/CourseWelcome/CoursePage、courseSpace、featureRegistry/Definitions、navigation与usePageRoute。
- 业务：features的materials/chat/practice/notes/learning/authoring状态与页面包装；materials独立ResourceLibrary、useResourceLibrary和样式；各域api及shared/http。
- 兼容入口：原use*.js、api.js及api目录导出；原组件和views继续复用。
- 交互：PracticeHub、QuestionImportPanel的指定资料上下文；笔记作用域同步重置。
- 测试：refactor-stage1与course-page-testing新增；原8份App相关集成测试适应异步页面。
- 工具：snapshot_refactor_stage1、verify_refactor_stage1_deployment；已有页级HTTP/浏览器夹具脚本增加独立输出参数，未覆盖旧验收报告。
- 文档：精简AGENTS、README、PROJECT_CONTEXT、DEVELOPMENT_PLAN；CURRENT_STATUS、指南/报告和完整历史归档。

## 负责人可复核清单与限制

- 在现用标识核对资料、笔记、历史与旧链接；真实资料内容尚需负责人核对。
- 桌面/窄屏重复一次读资料→提问→原文→练习→进度；需要使用模型时仍逐轮确认私有来源外发。
- 模拟网络失败/存储失败有自动化覆盖，浏览器未穷举弱网、大文件上传、全部发布/知识树/指南操作和所有设备。
- 旧复杂组件和兼容导出暂时保留，业务工厂代码仍静态导入；本轮优先改变生命周期和职责，不强制一次删除全部历史实现。
- OCR、复杂公式和真实原题精度、词项检索漏检未解决；原55/15评估及失败保持。
- 正式仍原5点10题，40候选待审；普通练习不扩展BKT证据。真实教学效果未验证。

第一阶段完成后停止。下一阶段建议为固定真实资料质量评估，须另行确认。
