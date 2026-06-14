"""日志工具。

项目只维护一个根 logger `netn`，子模块通过 `get_logger("xxx")`
派生出层级 logger，例如：
- `netn.dataset`
- `netn.api`
- `netn.hittingset`

这样做的好处是：
- 日志格式、级别、输出流集中配置；
- 子模块仍能在日志名里显示来源；
- CLI 长任务中可以快速定位是哪一层输出的信息。

这里额外使用 flush handler，保证长时间运行时进度和日志尽快刷到终端，
避免缓冲延迟。
"""

from __future__ import annotations

import logging
import sys


LOGGER_NAME = "netn"
"""项目根 logger 名称。"""

DEFAULT_FORMAT = "[%(name)s @ %(asctime)s] %(levelname)-7s | %(message)s"
"""统一日志格式：显示 logger 名、时间、级别和消息。"""

DEFAULT_DATEFMT = "%H:%M:%S"
"""日志时间只显示时分秒，适合 CLI 输出。"""


class FlushStreamHandler(logging.StreamHandler):
    """每次 emit 后立即 flush，适合 CLI 和长任务场景。

    默认 StreamHandler 可能受缓冲影响，长时间任务中日志显示会滞后。
    这里在每次 emit 后强制 flush，让用户及时看到进度和警告。
    """

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """配置并返回项目根 logger。

    这个函数是幂等的：
    - 第一次调用时创建 handler；
    - 后续调用只更新级别，不重复添加 handler。

    否则多次调用 `get_logger()` 会导致同一条日志重复输出多遍。
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    # 不向 Python root logger 继续传播，避免用户环境里的全局 logging 配置重复打印。
    logger.propagate = False
    if not logger.handlers:
        handler = FlushStreamHandler(stream=sys.stderr)
        handler.setFormatter(logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATEFMT))
        logger.addHandler(handler)
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """获取根 logger 或指定名称的子 logger。

    `get_logger("dataset")` 会返回 `netn.dataset`。
    如果传入的 name 已经以 `netn` 开头，则直接使用，避免生成 `netn.netn.xxx`。
    """
    root = configure_logging()
    if not name:
        return root
    child_name = name if name.startswith(LOGGER_NAME) else f"{LOGGER_NAME}.{name}"
    child = logging.getLogger(child_name)
    child.setLevel(root.level)
    return child
