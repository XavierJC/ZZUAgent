# 学习体验整合与使用说明

日期：2026-10-24。用户批准借鉴优秀学习项目后实施本轮改进。此文记录实际交付，不把参考项目的能力视为 EduAgent 已有能力。

## 本轮范围

复用 Vue 3、FastAPI、SQLite、现有检索和 Agent。学生主入口仍为资料学习、练习、学习进度，课程构建和旧深链接继续保留。没有引入新服务、数据库或前端框架，没有复制第三方项目代码、图标或品牌。

| 参考项目 | 借鉴到本轮的设计 |
| --- | --- |
| [nano-NotebookLM](https://github.com/ArthurYangX/nano-NotebookLM) | 以资料为中心、回答与页码原文相互定位 |
| [Open Notebook](https://github.com/lfnovo/open-notebook) | 将资料、对话和笔记放在连续学习路径中 |
| [Exameow](https://github.com/heshengtao/exameow) | 导入后尽快开始练习，异常集中处理 |
| [Adaptive Knowledge Graph](https://github.com/MysterionRise/adaptive-knowledge-graph) | 将客观学情、推荐原因和后续资料/练习衔接 |

本轮借鉴工作流和交互组织。参考项目的生成题、BKT参数、判分和基础设施没有直接套用；后续若复用代码须逐模块保留许可与署名。

## 资料学习

1. 添加课件，或勾选已有来源。打开原文与选择参与问答分开。
2. 中间为主要问答区，右侧学习面板默认收起。打开资料或引用时在旁边查看原文；窄屏使用资料、问答、工作室标签。
3. 上传文件可按页切换，逐页显示可检索/待识别状态及解析提示。空白页、图片和公式缺失不会用模型内容伪装成原文。单页预览上限60000字符，截断会提示。
4. 引用为回答生成时的片段快照。原文件访问绑定版本；当前资料修改或软删除后，新读取重新校验，历史快照不冒充当前资料。
5. 回答可另存为笔记，复用既有幂等与编辑来源记录。问答历史默认折叠，查看不重新生成。
6. Ctrl / Command + Enter 可显式发送；建议问题只准备草稿，不发送请求。已有问题草稿不会被学习建议静默覆盖。

本轮没有更换解析引擎或检索排序算法。可读页数是覆盖提示，不是识别准确率。缺失内容仍需选择页面并明确授权识别。原55条检索评估及15条挑战记录保持，不能以新页面展示声称语义准确率提高。

## 练习与进度

- 练习可按题目文字、资料来源或已保存的知识关联查找。知识关联使用体系/概念稳定ID，不按相同名称或文字相似自行认定。
- 由资料或知识点进入时，范围为空会明确提示；不会偷偷扩大范围或展示其他范围的上次练习。
- 开始、下一道练习、恢复上一题均由明确按钮触发。无筛选时保留现有普通选题策略，有筛选时仅使用当前列表内的题目。
- 作答时突出当前题目，题库管理头、筛选和历史收起；可返回列表、继续作答，或去助教选择资料讲解。
- 练习跳转不会自动复制题目原文到模型请求，不借跳转绕过材料外发选择。
- 学习进度优先显示目标、正式作答数、已有证据的知识点、下一步及原因。无证据显示待诊断，自评与BKT分别显示。
- 自评、指南、正式诊断和复习沿用原接口；推荐和普通练习不修改正式学习事实。

题目识别仍复用现有 Agent，按选定范围读取原题，不生成缺失答案。本轮增加实际阶段提示及“查看已整理题目”入口。自动入库规范化可选字段，旧题缺失概念列表按无关联读取，不改写旧内容；避免连续练习因此报错。

## 兼容 API

`POST /api/v1/students/{student_id}/workbench/sources/open` 保持原来源引用请求兼容，增加可选 `page`：

```json
{
  "source_type": "uploaded_document",
  "source_id": "已有资料ID",
  "source_version": "来源列表返回的当前版本",
  "page": 1
}
```

`page` 必须为1～200的整数；布尔值、字符串、越界及额外控制字段拒绝。按页仅支持上传资料；其他来源沿用原读取方式。指定页不存在返回404，版本过期409，非法请求422。学生作用域沿用演示标识，不能当作身份认证。

响应保留 `raw_md`、来源ID/版本等原字段，增加 `page_number`、`pages[{ordinal,readable,warnings}]`、`truncated`。不传页码仍返回原聚合预览，保证旧客户端兼容。接口是只读操作，不调用模型或分题。

前端阻止慢预览覆盖后来点击的引用；关闭原文或切换标识后丢弃旧响应。指南仍使用有焦点约束的模态抽屉，工作台使用不锁住问答区的侧栏，均支持 Escape 与焦点恢复。

## 数据保护与回退

- 现用库保持 schema13 / 45表；没有DDL迁移，也没有重写学习历史或题目。
- 修改前使用 SQLite backup 保存数据库，并记录45表摘要、完整性和外键；源码与文档保存为恢复ZIP。路径见 `data/local/learning-experience-current.json`。
- 回退时停止当前服务，保留当前数据库及之后的新数据，再恢复本轮前源码并重新构建前端。数据库结构兼容，不需要覆盖现用数据库，更不能用旧备份覆盖后来作答。
- 评分、BKT参数、正式五知识点/十道演示题和40候选待审状态保持。自动题仍未核验，参考对照不算客观分数，不更新BKT。
- 资料选择与外发同意分开，逐轮重新确认。实际收费模型调用0，没有把真实资料批量发送给外部服务。

## 验证方法

实际自动化、HTTP、浏览器、数据摘要与未验证项目见 [验收报告](LEARNING_EXPERIENCE_REPORT.md)。运行方式与依赖沿用README，新增依赖0。

```powershell
$learningTestDir = 'data/local/experience-tests-' + [guid]::NewGuid().ToString('N')
.\.venv\Scripts\python.exe -m pytest backend/tests -c backend/pyproject.toml --basetemp=$learningTestDir -q
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe scripts/verify_learning_experience.py
.\.venv\Scripts\python.exe scripts/verify_learning_simplification.py --output data/evaluation/learning-experience-workflow-http-v1.json
.\.venv\Scripts\python.exe scripts/verify_learning_experience_deployment.py
```

HTTP和部分后端测试需要本机回环连接。浏览器夹具由 `scripts/prepare_learning_experience_browser.py` 创建，仅用于独立测试库，不能导入正式学习库或当作人工审核内容。
