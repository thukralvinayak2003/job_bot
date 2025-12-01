"""scrapers package initialization.

Expose scraper modules so callers can use the module attributes
(e.g. ``linkedin.search_jobs``) rather than binding the function
directly to the package name. This keeps the API consistent with
how ``main.py`` expects to access ``search_jobs``.
"""

from . import linkedin
from . import indeed
from . import naukri
from . import glassdoor

__all__ = [
    "linkedin",
    "indeed",
    "naukri",
    "glassdoor",
]
