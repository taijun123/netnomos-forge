"""构建 pybind11 原生扩展的 setuptools 入口。"""

from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup


ext_modules = [
    # 原生 hitting-set 枚举器，提升大规模规则搜索性能。
    Pybind11Extension(
        "netnomos._hittingset_native",
        ["cpp/hittingset_native.cpp"],
    ),
]


setup(
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
)
