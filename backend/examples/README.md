# 历史实现与实验脚本

此目录保留旧代码供参考，不被后端服务导入，也不作为当前启动入口。

- `SLL.py`：较早的独立知识生成实现，使用阿里云模型接口。
- `run_SLL.py`：旧命令行示例，传入的 `max_conv_turns`、`max_perspectives` 等参数与当前 `SLLRunnerArguments` 不匹配，不能直接使用。恢复该入口需要重新对齐引擎配置和方法签名。
- `run_storm_wiki_deepseek.py`：上游 `knowledge_storm` 实验入口，需额外准备该项目及其依赖。

当前可维护的服务入口为仓库根目录下的 `python -m backend.main`。
