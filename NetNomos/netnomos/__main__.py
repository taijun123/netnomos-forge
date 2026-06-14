"""允许通过 `python -m netnomos` 直接启动 CLI。

Python 在执行 `python -m package_name` 时会寻找该包下的 `__main__.py`。
这里把入口转发给 `netnomos.cli.main()`，让以下两种启动方式等价：
- `netnomos ...`
- `python -m netnomos ...`
"""

from netnomos.cli import main


if __name__ == "__main__":
    # main() 返回进程退出码；SystemExit 会把它交给 Python 解释器作为 CLI 退出状态。
    raise SystemExit(main())
