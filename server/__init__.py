# -*- coding: utf-8 -*-
"""server — netnomos-forge FastAPI 编排服务（二波）.

模块布局：
- store.py    内存任务/规则集/数据源存储（纯标准库，线程安全）
- pipeline.py 编排核心：run_finance_pipeline / run_network_pipeline
              （纯 Python 可测试，emit(WorkflowEvent) 回调推事件）
- app.py      create_app() 工厂：FastAPI 全懒加载，沙箱 import 本包不报错

宿主机启动（见 scripts/host/run_server.ps1 与 docs/SERVER.md）::

    uv sync
    uv run uvicorn server.app:create_app --factory --port 8000 --reload
"""
