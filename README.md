# Travel Planner

一个基于 `LangGraph`、`FastAPI` 和 `Streamlit` 构建的多 Agent 智能旅行规划项目。

这个项目将旅行规划拆解为一个图工作流：

- `PreferenceAgent` 负责补全和整理用户偏好
- `DestinationAgent` 负责推荐目的地
- `FlightAgent`、`HotelAgent`、`ActivityAgent` 在 LangGraph 子图中并行执行
- `BudgetAgent` 负责预算校验和有限次调整循环

这个项目适合作为 AI 工程、后端工程、多 Agent 编排方向的作品集项目，重点展示：

- 使用 `LangGraph` 进行图式工作流编排
- 多 Agent 的任务拆分与协作
- 并行搜索子图设计
- `FastAPI` + `Streamlit` 的前后端分离
- 基于 `Pydantic` 的结构化状态管理

## 项目架构

```text
Streamlit 前端
   |
   v
FastAPI 后端
   |
   v
LangGraph 主图
   |
   +--> Preference Agent
   +--> Destination Agent
   +--> 并行搜索子图
   |      +--> Flight Agent
   |      +--> Hotel Agent
   |      +--> Activity Agent
   |
   +--> Budget Agent
   |
   +--> 最终旅行规划结果
```

## 技术栈

- Python 3.12+
- LangGraph
- FastAPI
- Streamlit
- Pydantic
- httpx
- python-dotenv
- loguru

## 目录结构

```text
agents/         Agent 实现
api/            FastAPI 后端服务
config/         运行配置与 Prompt 模板
models/         Pydantic 数据模型与工作流状态
orchestrator/   LangGraph 工作流编排
tools/          Mock 数据与搜索工具
ui/             Streamlit 前端
```

## 核心特性

- 端到端多 Agent 旅行规划
- 使用 LangGraph 替代零散异步控制流
- 航班、酒店、活动并行搜索
- 预算护栏与有限次调整机制
- 支持本地 Mock 模式快速演示
- API 驱动前端页面

## 本地运行

安装依赖：

```bash
pip install -r requirements.txt
```

启动后端：

```bash
python -m api.app
```

在另一个终端启动前端：

```bash
streamlit run ui/streamlit_app.py
```

## 环境变量

在本地创建 `.env` 文件，示例如下：

```env
LLM_PROVIDER=mock
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096
BUDGET_MAX_RETRIES=3
PARALLEL_TIMEOUT=120
API_HOST=0.0.0.0
API_PORT=8000
API_BASE_URL=http://localhost:8000
LOG_LEVEL=INFO
```

## API 接口

- `GET /api/health`
- `POST /api/plan`
- `POST /api/plan/full`

## 项目价值

这个仓库不是一个简单的接口调用 Demo，而是一个更接近工程化作品集的多 Agent 项目。它展示了图编排、状态流转、并行节点设计、预算控制逻辑，以及清晰的前后端分层方式，适合用于简历、面试和 GitHub 项目展示。
