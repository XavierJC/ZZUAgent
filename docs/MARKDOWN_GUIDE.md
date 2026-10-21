# v0.5.0 Phase 1：统一 Markdown 与公式显示

Phase3B补充：工作台答案/原文快照复用本组件，新增可选citationIds，仅将服务端已验证ID转换为本地引用链接并发出组件事件；代码、公式和其他文本不获得工具能力，仍经过同一净化器。没有增加第二个HTML入口。当前318/87项及阶段验证见[工作台指南](WORKBENCH_GUIDE.md)，下文为Phase1历史。

后续状态：Phase3A已完成本地笔记分块/检索，详见 [个人检索指南](PERSONAL_RAG_GUIDE.md)。浏览器仍使用本安全渲染组件；后端分块不执行Markdown、HTML、公式或模型指令。本页结果为Phase1历史记录。

日期：2026-10-20。状态：**展示组件、接入、自动测试与构建已完成；浏览器视觉、键盘和窄屏人工验收待完成。** 当前版本清单仍为 0.4.1，不据单一阶段宣称整个 v0.5.0 已发布。后续已完成 [Phase 2 笔记管理](NOTES_GUIDE.md) 并复用本组件，个人 RAG 和自评未实现；本文测试及无迁移记录保留为 Phase 1 当时结果。

## 已实现

[MarkdownRenderer.vue](../frontend/src/components/MarkdownRenderer.vue) 统一显示标题、段落、列表、引用、表格、行内代码、代码块、`$...$` 行内公式和 `$$...$$` 块级公式，支持常用分数、矩阵、上下标与根式。它已用于题干、选项、即时解析、历史解析、助教回答、引用原文和课程检索结果；Phase 2 笔记预览也已复用。

原始文字仍由后端提供，前端只做显示。没有修改正式/候选题库、课程资料、BKT 参数、评分或推进规则，没有迁移现用数据库。已有资料中未使用数学分隔符的普通公式文字保持普通文字，不猜测改写。

组件示例：

```vue
<MarkdownRenderer :source="reply.answer" />
<MarkdownRenderer :source="optionText" inline />
```

block 模式使用 div，inline 模式只生成行内内容。题干使用合法容器并通过 aria-labelledby 标注 fieldset，避免在 legend 中嵌入任意块元素。选项仍由原有 radio/change 事件控制，解析仍仅使用服务器返回结果。

## 渲染与安全边界

[markdown.js](../frontend/src/rendering/markdown.js) 先解析 Markdown，再生成数学/高亮标记，最后统一 DOMPurify 清理。只有 MarkdownRenderer 包含 `v-html`；其他组件不自行拼接 HTML。

- 原始 HTML 关闭，脚本/HTML 文本转义显示；不执行代码，不加载 Markdown 图片、iframe 或包含文件。
- 只允许 http、https 和当前文档锚点，屏蔽危险及相对协议；外链设置 noopener/noreferrer 和 no-referrer。
- KaTeX trust=false，maxExpand=1000，maxSize=20；每次文档有独立宏环境。无效公式显示原文和提示，不输出解析异常到控制台。
- 最终清理保留公式所需 MathML、有限 SVG 与库生成布局，禁用用户 HTML、危险元素和事件属性；显式保留 MathML semantics/annotation 以保持公式可访问信息。
- 公式、表格和代码提供容器内横向滚动；表格滚动区域可键盘聚焦。保持现有浅色界面，代码块使用局部深色主题，不增加全站主题开关。
- 未超出 64 KiB UTF-8 的文档可排版；超限则完整显示转义纯文本。单公式超过 2000 字符、公式超过 128 个时保留对应原文。代码块超过 8192 字符或语言不支持时显示纯文本。

解析数学分隔符使用 `@mdit/plugin-tex`，与原候选 KaTeX 包装插件使用同一解析模块；KaTeX 渲染由本模块直接捕获异常。原因是包装插件在启用异常时会输出含原文的控制台错误，而关闭异常又可能仅将未知命令变成红字，无法稳定提供项目要求的回退提示。这是局部实现选择，未自行编写数学正则解析器。

清理与公式资源限制参考 [KaTeX 安全说明](https://katex.org/docs/security)、[DOMPurify 配置](https://github.com/cure53/DOMPurify)；行为仍以本项目的实际测试为准。结构检查不等同于所有浏览器漏洞验证。

## 固定依赖与运行

| 新增直接依赖 | 固定版本 | 用途/许可 |
| --- | --- | --- |
| markdown-it | 15.0.3 | Markdown，MIT |
| @mdit/plugin-tex | 1.1.2 | 数学分隔符，MIT |
| katex | 0.19.0 | 数学排版，MIT |
| highlight.js | 11.12.0 | Python/C++/JavaScript/JSON/Bash 高亮，BSD-3-Clause |
| dompurify | 3.4.17 | HTML 清理，MPL-2.0 或 Apache-2.0 |

官方 npm 元数据与本机安装时核验了 engines、依赖和许可；Node 22.14.0 下使用 `--engine-strict --ignore-scripts` 安装成功，锁文件固定具体传递版本。安装最初发现 KaTeX 0.18.11 被维护者标为误发布，已移除；最终使用 0.19.0 与独立 tex 解析插件，不残留旧包装插件或重复 KaTeX。最终安装报告为 0 项已知漏洞，该报告不证明所有输入安全。

从 frontend 目录运行：

```powershell
npm.cmd ci
npm.cmd run test
npm.cmd run build
```

已构建资源由原后端继续提供；刷新 [学习页面](http://127.0.0.1:8000/) 加载。所有公式字体本地打包，不使用 CDN，不需要模型密钥。单纯显示已保存讲解或课程结果不调用模型。

## 实际验证

| 检查 | 结果 |
| --- | --- |
| 固定样例 | [markdown-fixtures.json](../data/evaluation/markdown-fixtures.json)，16 个自建样例：结构、公式、矩阵、SVG 根式、代码、转义、恶意 HTML/链接/公式等 |
| 前端完整测试 | `npm.cmd run test`：4 files / **47 tests passed**，2.61s；原 18 项继续通过，新增 29 项 |
| 覆盖重点 | 错误回退、宏隔离/循环、尺寸/数量限制、大文档、链接安全、组件更新、字段标签、各实际接入位置；没有额外答题或生成请求 |
| 后端完整回归 | `.\.venv\Scripts\python.exe -m pytest backend/tests -c backend/pyproject.toml -q`：**225 passed in 7.98s** |
| 生产构建 | `npm.cmd run build` 退出 0；JS 530.90 kB，gzip 186.09 kB；CSS 60.29 kB，gzip 15.61 kB |
| 资源检查 | 构建引用文件均存在，CSS 中 59 个本地字体引用可解析；依赖清单/锁文件一致，原题库联合指纹不变，唯一 HTML 出口检查通过 |
| 服务 | 健康检查仍为 0.4.1、10 道待审题、Agent 与检索可用；未重启服务或迁移数据库 |
| 模型请求 | 0，本阶段未付费重测模型 |

初测曾有四项失败：未知命令没有按预期回退，以及尺寸断言误把 MathML 中保存的公式原文当作布局属性。修正异常处理及属性断言后，再增加集成检查；一项预选 radio 的测试起始状态也已修正，最终完整 47 项通过。没有隐藏失败样例或缩减安全要求。

构建给出主包超过默认 500 kB 的提示，主要增加来自数学与语法高亮。当前本地演示可构建运行，后续如首次加载影响体验，再评估按需加载；本轮没有调高阈值隐藏提示。自动测试运行在 jsdom，不能测量真实排版宽度或证明屏幕阅读器体验。

## 待人工验收

- [ ] 浏览器确认分数、矩阵、根式、长公式与代码显示。
- [ ] 640px 附近及更窄屏幕，内容仅在内部横向滚动，不撑开工作台。
- [ ] 键盘选择答案、提交、展开来源与聚焦表格区域正常。
- [ ] 真实模型生成的 Markdown 与原引用仍清晰对应；本阶段未新增实调。

此前浏览器自动化被 URL 安全策略拒绝，本阶段没有使用其他浏览器或抓取页面方式绕过；上述项目保留为人工验收。原有题库/资料/先修审阅、检索课程外误检与独立评估同样未被标为完成。
