# 智学郑大 EduAgent

面向高校《机器学习》课程的个性化学习辅助系统，采用BKT知识追踪和受控Agent，服务于郑州大学AI智能体创新应用大赛A2任务。

**建立学习笔记本 → 添加资料 → 提问并查看出处 → 练习与记录理解。**

## 当前状态

已交付人性化学习流程简化，并保留此前UI与正式题准入。[唯一当前状态](docs/CURRENT_STATUS.md) · [简化流程指南](docs/HUMAN_WORKFLOW_GUIDE.md) · [本轮验收与截图](docs/HUMAN_WORKFLOW_REPORT.md) · [题目准入与验收](docs/FORMAL_ADMISSION_REPORT.md) · [设计系统](docs/FRONTEND_DESIGN_SYSTEM.md) · [笔记本指南与API](docs/NOTEBOOK_REBUILD_GUIDE.md)。

主导航为学习、练习、进度。点击开始即可使用默认昵称，新主题可以不填名称；成功上传资料直接加入当前主题，习题整理后可直接开始自由练习。选择“测一下”后明确开始即可进入诊断，正常学习无需先管理或发布课程。低频设置默认收起，手机菜单与旧链接保留全部能力。五个项目的参考与代码归属见[开源参考](docs/OPEN_SOURCE_UI_REFERENCES.md)。

上传资料包括解析失败的文件，均可在主题资料窗口右侧直接删除；本行确认后移出可用资料，历史和原件保留。见[删除入口修复](docs/SOURCE_DELETE_REPORT.md)。

最新测试、浏览器检查及数据摘要结果见CURRENT_STATUS。本轮流程简化只改前端、文档及核验脚本，后端、schema和依赖不变，真实模型调用0；复用现有AI能力，禁用模型时本地降级。此前题目准入及Notebook交付证据保留于原报告；AI检查、内容人工审核与真实教学效果分别报告。

现有能力包括来源受控RAG、Markdown/LaTeX笔记、资料解析与页码引用、原题整理和普通练习、正式BKT闭环、自评与学习指南。最新已按用户授权扩充原5知识点的正式诊断题库，共享题与个人题范围见[当前状态](docs/CURRENT_STATUS.md)和[准入指南](docs/FORMAL_ADMISSION_GUIDE.md)。AI检查与人工确认分开记录；普通练习不更新BKT。仅本机演示，学习标识不是身份认证。

## 启动

在项目根目录打开PowerShell：

```powershell
.\.venv\Scripts\python.exe -m uvicorn eduagent.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

打开[学习笔记本](http://127.0.0.1:8000/#/notebooks)，新建或恢复学习标识，再创建学习主题。已有资料可从“添加或管理资料”选择，不需重复上传。服务终端需保持运行；若连接被拒绝，先检查服务是否仍在运行。

修改前端后重新构建：

```powershell
Set-Location frontend
npm.cmd run build
Set-Location ..
```

## 新环境与测试

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e './backend[api,dev,agent,documents]'
Set-Location frontend
npm.cmd ci
npm.cmd test
npm.cmd run build
Set-Location ..
.\.venv\Scripts\python.exe -m pytest backend/tests -c backend/pyproject.toml -q
```

前端使用Node22.12及以上受支持版本，具体范围见package.json。模型密钥只配置于本机忽略的.env，参考.env.example；不在源码或报告中保存密钥。没有密钥仍可本地解析、检索和执行规则指南。本轮重构不进行真实付费模型调用。

默认数据库为data/local/eduagent.sqlite3。当前schema与数据验证见CURRENT_STATUS，不重复执行旧迁移；不得让不兼容旧程序连接新库。

## 代码结构

- frontend/src/app：课程布局、路由、模块生命周期与导航协调。
- frontend/src/features：notebooks、materials、chat、practice、notes、learning、authoring。
- frontend/src/shared：通用请求能力；现有Markdown与基础组件继续复用。
- backend/src/eduagent：API、domain、services、storage、documents、retrieval、agent。
- docs/CURRENT_STATUS.md：当前实际能力；docs/history：旧阶段原件和报告索引。

技术栈：Vue3/Vite、Python/FastAPI、SQLite、LangGraph单一Agent、BKT、TF-IDF/FAISS、DeepSeek。当前本地检索是词项基线，不宣称已升级语义检索。

## 数据与使用边界

AI整理不等于人工核验；无法提取的页面和公式明确提示。普通练习、自评和笔记不改变客观掌握度，BKT先验不当作诊断。

所选来源由后端再次校验；空选择不查全库。个人笔记和上传/教师资料的模型外发逐轮同意，和视觉识别、指南分别管理。历史引用保留当时快照，软删除不等于物理清除。

## 文档入口

[项目上下文](docs/PROJECT_CONTEXT.md) · [开发计划](docs/DEVELOPMENT_PLAN.md) · [历史索引](docs/history/README.md) · [API基础](docs/API_GUIDE.md) · [工作台](docs/WORKBENCH_GUIDE.md) · [笔记](docs/NOTES_GUIDE.md) · [个人RAG](docs/PERSONAL_RAG_GUIDE.md)。

旧阶段的schema、测试数字和“当前”记录属于历史。真实内容审核和教学效果与工程测试分别记录。
