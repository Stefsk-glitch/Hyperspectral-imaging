from setuptools import setup, Extension
# For this to work, you might need to remove noexec option from /tmp on linux systems
import numpy

setup(
  setup_requires = ["setuptools>=40.8", "wheel", "numpy>=1.21"],
  python_requires = ">=3.7, <3.11",
  ext_modules = [
    Extension(
      "gvsp",
      sources = ["./gvsp.c"],
      include_dirs = [numpy.get_include()]
    )
  ]
)
