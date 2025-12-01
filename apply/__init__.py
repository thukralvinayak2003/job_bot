# apply/__init__.py
"""
Apply handlers package.

Provides automated job application handlers for each platform.
"""

from .apply_linkedin import attempt_apply as apply_linkedin
from .apply_indeed import attempt_apply as apply_indeed


__all__ = [
    "apply_linkedin",
    "apply_indeed",
]
