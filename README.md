# SLL

基于 FastAPI 的聊天与长文生成服务，使用 PostgreSQL 保存记录，并提供独立的 Embedding 微调和评测工具。

## 目录

```text
backend/
  main.py                 # FastAPI 入口与请求日志中间件
  api/                    # 认证、聊天、长文和记录查询路由
    dependencies.py       # 当前用户认证依赖
  models.py               # 用户、生成记录和消息 ORM 模型
  database.py             # 数据库连接、会话及 Conversation 模型
  security.py             # JWT 签发与验证
  logging_config.py       # 日志配置
  services/               # 响应处理、长文模型配置与运行器
  SLL_longtext/           # 长文生成引擎及各生成模块
  tools/                  # 离线训练与评测命令
  examples/               # 历史实现与实验脚本，状态见目录内说明
  init.sql                # 现有数据库与向量检索初始化 SQL
  requirements*.txt       # 服务依赖与独立训练依赖
tests/                    # 单元测试及可选训练冒烟测试
docs/                     # 使用说明与设计记录
docker-compose.yml        # PostgreSQL、向量化 worker 与 Ollama
start.bat                 # Windows 后端启动入口
```

## 启动后端

以下命令均从仓库根目录运行。先建立虚拟环境，安装 `backend/requirements.txt`，将 `backend/.env.example` 复制为 `backend/.env`，填写数据库、JWT、DeepSeek 和 Bocha 配置。

现有服务依赖清单尚不完整：源码还使用 `jwt`、`passlib`、`dspy`、`dsp` 和 `langchain_text_splitters` 等模块，长文代码依赖旧版 DSPy 的 `dspy.OpenAI` 接口。本次结构整理没有升级或猜测这些依赖的兼容版本；需要沿用可运行的原服务环境。仅安装现有清单不代表服务环境已就绪。

```bash
docker compose up -d
python -m backend.main
# 或：
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Compose 启动基础设施；数据库、表及向量检索初始化仍需按实际部署准备，`backend/init.sql` 不会自动执行。后端默认访问地址为 `http://127.0.0.1:8000`，接口文档为 `/docs`。当前仓库不包含前端。

配置从 `backend/.env` 加载，进程已有环境变量优先。服务日志写入 `backend/logs/`，在线长文生成结果写入 `backend/results/`。

## 离线工具

离线工具与服务环境分离，不需要启动 API 或数据库。训练依赖及完整参数见 [Embedding 微调说明](docs/EMBEDDING_FINETUNING.md)，人工标注格式见 [长文事实评测说明](docs/LONGTEXT_FACT_EVAL.md)。

```bash
python -m backend.tools.finetune_embedding --help
python -m backend.tools.benchmark_embedding --help
python -m backend.tools.score_longtext_facts --help
```

结构整理后的入口对应关系：

| 原位置或命令 | 当前位置或命令 |
| --- | --- |
| `cd backend && python main.py` | 根目录运行 `python -m backend.main` |
| `backend/router.py` | `backend/api/`、`backend/models.py`、`backend/security.py` |
| `backend/*_response_processor.py` | `backend/services/` |
| `backend/finetune_embedding.py` | `python -m backend.tools.finetune_embedding` |
| `python -m backend.benchmark_embedding` | `python -m backend.tools.benchmark_embedding` |
| `python -m backend.score_longtext_facts` | `python -m backend.tools.score_longtext_facts` |
| `backend/test_*.py` | `tests/test_*.py` |
| `backend/SLL.py`、`backend/run_*.py` | `backend/examples/` |

API 路径和数据库表定义保留；项目内部 Python 导入路径随目录调整，仓库外调用者需要按新位置更新。

## 测试

```bash
python -m unittest discover -s tests -v
```

默认测试只用标准库，覆盖训练输入、评测统计、API 路径及工具入口。设置 `SLL_EMBEDDING_SMOKE=1` 后额外运行 6 项真实训练检查，需要独立训练环境。默认测试不替代 API、数据库和外部模型服务的集成验证。
