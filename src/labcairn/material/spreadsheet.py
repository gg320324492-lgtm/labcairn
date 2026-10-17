"""Spreadsheets: one addressable unit per cell that holds a value.

``XlsxLocator`` is a sheet name and an A1 cell reference, so the address is
exact and the contract's ``XlsxCellRef`` pattern already refuses the spellings
that would make a ledger ambiguous. What this module has to get right is the
rest: which cells become units, and what happens to the ones that cannot be
read honestly.

Four decisions, each a place where the obvious implementation puts something
in the record that the workbook does not say.

**Empty cells produce no units.** A spreadsheet is mostly empty -- padding,
merged regions, a used range far larger than the data. Emitting them would
fill the table with rows carrying no evidence. This is the one place where
"keep every line" from the text adapter does *not* transfer, because a blank
line in prose is a line a reader counts, while a blank cell is not a
measurement.

**A formula with no cached value produces no unit and a disclosure.** openpyxl
does not compute, and ``data_only=True`` yields ``None`` for any formula whose
cached result the writer did not store -- which is every workbook written by
openpyxl or pandas, and many exported from tools that strip cached values.
Emitting an empty cell there would record a *measured blank* where the truth
is "we could not read this", and a later C3 numeric check would compare
against it. The workbook is therefore loaded twice: once with values, once
without, so a formula is recognisable rather than mistaken for a blank.

**Values are rendered deterministically, and never through a locale.** Dates
become ISO-8601 and floats use Python's own ``repr``, both of which are fixed
for a given value on every platform. A number formatted through a locale would
put a different string in the record depending on where it was extracted,
which makes the extracted-text hash depend on the machine.

**A workbook that cannot be opened is a disclosure, not an exception.** A
corrupt zip, an encrypted file and a file that is not a workbook at all are
all ordinary inputs to an inventory walk.
"""

from __future__ import annotations

import datetime as _dt
from types import ModuleType
from typing import Any

from labcairn.material.units import (
    ExtractedUnit,
    ExtractionProblem,
    ExtractionResult,
    register,
)
from labcairn.sources.locators import XlsxLocator
from labcairn.sources.source import SourceKind

__all__ = ["SpreadsheetAdapter", "render_cell"]

#: openpyxl raises a zoo of exception types on a malformed workbook, and the
#: set differs by version. Rather than enumerate types that will be added,
#: anything raised while *reading a file the user gave us* is caught; a bug in
#: this module is not, because the try blocks are around the library call.
_READ_FAILURE = Exception


def _openpyxl() -> Any:
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - the dependency is declared
        raise RuntimeError(
            "openpyxl is required to read spreadsheets; it is a declared dependency"
        ) from exc
    return openpyxl


def render_cell(value: Any) -> str:
    """A cell's value as the text the record will hold.

    Locale is never consulted. ``str(datetime)`` has no locale in it, but
    ``format(value, ",")`` would, and a value that renders differently on the
    machine that extracted it makes the excerpt hash machine-dependent.
    """
    if isinstance(value, bool):
        # Excel shows TRUE/FALSE, and `str(True)` would be "True".
        return "TRUE" if value else "FALSE"
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, (_dt.timedelta,)):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    return str(value)


@register
class SpreadsheetAdapter:
    """One unit per cell that holds a readable value."""

    kind = SourceKind.XLSX

    def extract(self, data: bytes) -> ExtractionResult:
        openpyxl = _openpyxl()
        problems: list[ExtractionProblem] = []

        try:
            values = _load(openpyxl, data, data_only=True)
            formulas = _load(openpyxl, data, data_only=False)
        except _READ_FAILURE as exc:
            return ExtractionResult(
                problems=(
                    ExtractionProblem(
                        code="xlsx_unreadable",
                        detail=(
                            f"the bytes are not a workbook this reader can open: "
                            f"{type(exc).__name__}: {exc}. It is inventoried and "
                            f"hashed; no cell is extracted, because a cell we could "
                            f"not read is not an empty cell."
                        ),
                    ),
                )
            )

        units: list[ExtractedUnit] = []
        for sheet_title in values.sheetnames:
            value_sheet = values[sheet_title]
            formula_sheet = formulas[sheet_title] if sheet_title in formulas.sheetnames else None
            filled = 0

            for row in value_sheet.iter_rows():
                for cell in row:
                    # The formula test comes **first**. openpyxl does not
                    # compute, so a formula with no cached result reads as
                    # None -- and an emptiness check placed before this one
                    # drops the cell silently, which is the failure this
                    # module exists to avoid: a cell we could not read is
                    # not an empty cell.
                    formula_cell = (
                        formula_sheet[cell.coordinate] if formula_sheet is not None else None
                    )
                    is_formula = formula_cell is not None and formula_cell.data_type == "f"
                    value = cell.value

                    if is_formula and formula_cell is not None:
                        if value is None:
                            problems.append(
                                ExtractionProblem(
                                    code="xlsx_formula_without_cached_value",
                                    detail=(
                                        f"{sheet_title}!{cell.coordinate} holds a "
                                        f"formula and the workbook stores no cached "
                                        f"result for it, which is normal for a file "
                                        f"written by a library rather than a "
                                        f"spreadsheet application. The formula is "
                                        f"recorded; no number is invented for it."
                                    ),
                                    location=f"{sheet_title}!{cell.coordinate}",
                                )
                            )
                            # openpyxl already includes the leading "=".
                            text = str(formula_cell.value)
                        else:
                            text = render_cell(value)
                    else:
                        if value is None or (isinstance(value, str) and not value.strip()):
                            continue
                        text = render_cell(value)

                    units.append(
                        ExtractedUnit(
                            locator=XlsxLocator(sheet_name=sheet_title, cell_ref=cell.coordinate),
                            text=text,
                        )
                    )
                    filled += 1

            if filled == 0:
                problems.append(
                    ExtractionProblem(
                        code="xlsx_sheet_empty",
                        detail=(
                            f"sheet {sheet_title!r} holds no readable cell. That is "
                            f"recorded as a fact about the sheet, not as an empty "
                            f"result for the whole workbook."
                        ),
                        location=sheet_title,
                    )
                )

        if not values.sheetnames:
            problems.append(
                ExtractionProblem(
                    code="xlsx_no_sheets",
                    detail="the workbook contains no sheets",
                )
            )

        return ExtractionResult(units=tuple(units), problems=tuple(problems))

    def libraries(self) -> dict[str, str]:
        """openpyxl's version belongs in the extraction version.

        It reads the zip container and the XML, so an upgrade can change
        what a cell yields exactly as a change to our own adapter can.
        """
        version = getattr(_openpyxl(), "__version__", None)
        return {"openpyxl": version} if isinstance(version, str) and version else {}

    def source_modules(self) -> tuple[ModuleType, ...]:
        import sys

        return (sys.modules[__name__],)


def _load(openpyxl: Any, data: bytes, *, data_only: bool) -> Any:
    import io

    return openpyxl.load_workbook(io.BytesIO(data), data_only=data_only, read_only=False)
