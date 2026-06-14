from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup


class OptionalBuildExt(build_ext):
    def run(self):
        try:
            super().run()
        except Exception as exc:
            self.warn(f"skipping optional native hitting-set extension: {exc}")

    def build_extension(self, ext):
        try:
            super().build_extension(ext)
        except Exception as exc:
            self.warn(f"skipping optional extension {ext.name}: {exc}")


ext_modules = [
    Pybind11Extension(
        "netnomos._hittingset_native",
        ["cpp/hittingset_native.cpp"],
    ),
]


setup(
    ext_modules=ext_modules,
    cmdclass={"build_ext": OptionalBuildExt},
)
