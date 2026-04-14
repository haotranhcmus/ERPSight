"""
backend/adapters/mapper_utils.py

Shared helper functions for all Odoo data mappers.

These utilities handle the three most common Odoo data quirks:
  - Many2one fields return [id, display_name] or False
  - Datetime fields arrive as ISO strings or False
  - Optional int/name extraction from those tuples
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional


def m2o_id(value: Any) -> Optional[int]:
    """Extract integer id from an Odoo many2one field value.

    Odoo returns many2one as [id, "display name"] or False.
    Returns None when the field is False/empty.
    """
    if isinstance(value, (list, tuple)) and len(value) >= 1 and value[0]:
        return int(value[0])
    return None


def m2o_name(value: Any) -> str:
    """Extract display name from an Odoo many2one field value.

    Returns empty string when the field is False/empty.
    """
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return str(value[1])
    return ""


def parse_dt(value: Any) -> Optional[datetime]:
    """Parse an Odoo datetime string into a Python datetime.

    Odoo returns datetimes as ISO-format strings (e.g. "2026-04-01 08:30:00")
    or False when the field is empty.  Returns None for falsy inputs.
    """
    if not value or value is False:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None
