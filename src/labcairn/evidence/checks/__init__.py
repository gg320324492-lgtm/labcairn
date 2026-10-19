"""The four cite-support checks, one file each.

ADR-0004 fixes them as four independent callables, and independence is the
point: a locator that resolves proves nothing about the quote at it, and a
quote that matches proves nothing about the inference drawn from it. Separate
files make that separation hard to collapse by accident.

The names callers import live in :mod:`labcairn.evidence.cite_support`, which
owns the types every check returns. These modules own the decisions.
"""

from __future__ import annotations

from labcairn.evidence.checks.c1 import check_source_exists
from labcairn.evidence.checks.c2 import check_quotation_support, quotation_match
from labcairn.evidence.checks.c3 import check_numeric_consistency, read_number

__all__ = [
    "check_numeric_consistency",
    "check_quotation_support",
    "check_source_exists",
    "quotation_match",
    "read_number",
]
