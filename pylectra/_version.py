"""Single source of truth for the package version.

Both ``pylectra/__init__.py`` (runtime ``pylectra.__version__``) and
``pyproject.toml`` (build-time wheel/sdist) read from here.
"""
__version__ = "0.1.0"
