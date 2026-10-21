# 资料与模型知识结合的问答

最新响应诊断/预算及真实模型结果见[MODEL_RESPONSE_GUIDE.md](MODEL_RESPONSE_GUIDE.md)：403/106项、30组模拟HTTP通过，另行授权的1次真实DeepSeek完整返回；下文391/104和“真实模型未执行”是本次修复前的历史记录。

2026-10-21。用户澄清目标：RAG提供参考上下文，大模型负责综合生成；资料未覆盖的知识也可以解释。此前将“北京时间”这个例子误解为时钟功能，已移除该专用实现。继续修复同一问答链路，不新增学习模式、模型或外部服务。

## 回答行为

流程仍为：问题→检索明确选中且版本有效的资料→把相关片段和问题交给模型→解释、补充并显示引用。

资料是优先参考依据，不是知识边界。模型逐项回答复合问题：

- 有本地片段支持的部分写入`answer`，引用必须来自本轮真正取得的片段。
- 资料未覆盖的应用、举例和其他知识写入`supplement_md`。服务端统一增加“模型知识补充（无本地资料引用）”标题；补充不得借用本地片段编号。
- 即使检索有命中，若模型没有使用这些片段，也可只返回知识补充。兼容旧两字段输出：没有本地引用且没有内联资料标记的普通回答转为明确的模型补充，不强迫添加无关引用。
- 无命中仍可回答。资料之外的解释不是权威材料或经验证事实；不能据此更新BKT、改分或改变正式策略。

`answer_basis`新增`mixed`，表示同时有资料引用和模型补充。其余`selected_sources/model_knowledge/local_excerpts/none`保留。原问答入口及`local/model`选项保持。

## 用户澄清与生成链路

不为示例硬编码答案或新增工具。删除了专用时钟模块、时间上下文注入、界面和API字段。旧数据库原文及旧报告保持，不通过覆盖历史掩盖误解。

验证重点改为：本地只有PCA定义时，将问题及命中片段打包给DeepSeek适配器，由模型生成PCA应用及另一个未覆盖知识点（注意力机制）的解释。还覆盖完全无命中、命中但不采用、历史恢复及授权边界。

使用真实HTTP适配器加`httpx2.MockTransport`检查上游请求包，确认发送的是问题与RAG片段，并接收模型生成结果。MockTransport不会连接DeepSeek或计费；不能将这项验证描述为真实模型效果。

## 边界和兼容

原来源选择、学生作用域、版本校验、索引状态及逐轮个人笔记同意继续执行。未同意个人外发仍整轮本地；空来源列表仍拒绝，不查全库。无命中问答不提供检索/学情工具，不发送学习历史。

学习指南继续使用原确定性重点、依据和严格引用边界，不接受`supplement_md`，不改BKT/评分/先修关系。聊天模型不能通过新字段覆盖来源、学生或学习状态。

`parse_answer`保留严格JSON/单层围栏解析、长度限制及具体错误。`supplement_citation`表示模型补充借用或伪造了本地引用。旧输出两字段继续兼容，模型提供的未知字段仍拒绝。

新元数据仍存既有`workbench_runs.result_json`；schema6/29路径不变，无依赖变更或迁移。旧问答只补默认字段，不重写历史。另存笔记保留混合来源说明、补充标题、引用快照，继续幂等和可编辑，不改BKT。

## 实际验证

- 后端：**391 passed in 22.68s**，验证模型请求打包/返回接收、PCA复合问题、资料未采用、一般知识、引用隔离、指南边界及历史不重发。时钟测试已改为RAG→模型适配器验证。
- 前端：**104 passed in 5.52s**，8文件；补充区、引用、无专用时钟、历史只读通过。
- 构建成功：67模块；主JS600.06kB/gzip207.15kB、CSS70.30kB/gzip17.73kB。500kB原警告继续保留。
- [10组问答HTTP](../data/evaluation/workbench-generation-http-v1.json)：独立临时数据库、两次服务启动、9次模拟模型、0次真实模型。覆盖PCA资料+应用和其他知识补充、资料未采用、一般知识、引用错误、外发同意、学生隔离、笔记来源和重启恢复。
- [18组4A HTTP回归](../data/evaluation/workbench-generation-phase4a-regression-v1.json)：独立数据、9次模拟模型、0次真实模型，保持指南、BKT、评分及历史。
- 本次没有失败测试。模型次数为最终两份HTTP报告合计，不包含单测和开发中间运行。此前hybrid报告保留为历史，不覆盖。

复现：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -c backend/pyproject.toml -q
Set-Location frontend
npm.cmd run test
npm.cmd run build -- --outDir dist-phase4a
Set-Location ..
.\.venv\Scripts\python.exe scripts/verify_workbench_answers.py --output data/evaluation/workbench-generation-http-v1.json
.\.venv\Scripts\python.exe scripts/verify_phase4a.py --output data/evaluation/workbench-generation-phase4a-regression-v1.json
```

部署、文件和数据完整性记录见[交付报告](../data/evaluation/workbench-generation-validation-v1.json)。本轮代码快照在`data/local/rag-generation-2a863b4e/before-code.zip`。原55条检索评估和5/15课程外误检不变，40题仍待审，未实施新阶段。

## 待验证

本次未发起真实DeepSeek请求，仍需单独确认预算。模拟模型能验证调用链路、结构化补充及边界，不能保证真实模型每次正确区分依据或完全服从提示，也不能证明教学效果或彻底消除幻觉。没有因此获得联网搜索或实时事实校验能力。

浏览器人工视觉/窄屏/键盘验收未执行。刷新本机页面并新建问答后，可核对“PCA可以做什么、举出应用、另解释注意力机制”：应有可回溯PCA片段、模型生成的补充，不应只复述本地片段。旧回答保留当时原文，不会自动改写或重发。真实模型操作可能计费。
