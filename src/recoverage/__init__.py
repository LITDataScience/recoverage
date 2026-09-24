"""Recoverage: project-agnostic coverage, gap analysis, and test drafts."""

from recoverage.pipeline import execute_generate, execute_report, execute_run
from recoverage.version import __version__
__all__ = ["__version__", "execute_generate", "execute_report", "execute_run"]
