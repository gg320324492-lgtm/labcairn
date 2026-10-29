"""Canonical rendering of a locator into the key the store indexes on.

ADR-0009 rests the whole key on ``locator_key``:

    UNIQUE (source_content_sha256, extraction_version, locator_key)

because SQLite treats NULLs as distinct inside a UNIQUE index, so a
constraint spanning the nullable typed locator columns would look present
and enforce nothing. Two properties are therefore not optional.

**Injective.** Two different locators must never produce the same key. The
naive rendering ``f"csv|{row}|{column}"`` is not injective: a column header
containing ``|`` collides with a row boundary, and ``"a|b"`` as a column
name is legal. Every value below is therefore *length-prefixed* —
``4:mean`` is four characters, then ``:``, then the value — so a reader can
always split it, and a value containing any separator cannot shift a
boundary. The length is the character count, matching Python's ``str``.

**Canonical.** One locator, one key. Review found four spellings of
``pdf:page=2`` coexisting as four rows — ``pdf:page=2``, ``pdf p2``,
``PDF|PAGE|2``, ``pdf:page=02`` — which is precisely the fork ADR-0009 says
the design must not have. Rendering it here, in one place, is the fix; a
caller that builds a key by hand can still fork it, which is why nothing in
``src/`` does.

Deliberately **derived, never the truth.** ADR-0004 rejects prose locators
precisely because they cannot be re-derived from anything; this one is
re-derived from typed columns, and :func:`render_locator_key` is the only
thing in the codebase allowed to produce one.
"""

from __future__ import annotations

from labcairn.sources.locators import (
    CsvLocator,
    DocxLocator,
    PdfLocator,
    SourceLocator,
    TextLocator,
    XlsxLocator,
)

__all__ = ["LocatorKeyError", "render_locator_key", "split_locator_key"]


class LocatorKeyError(ValueError):
    """A locator whose typed fields do not match its kind, or are unusable.

    Raised rather than rendered anyway: a key that does not describe the
    locator it claims to is worse than no key, because the UNIQUE would then
    protect the wrong thing.
    """


def _field(name: str, value: str) -> str:
    """One length-prefixed component. ``4:mean`` -- four characters, then mean."""
    return f"{name}={len(value)}:{value}"


def _page_fields(locator: PdfLocator) -> list[str]:
    fields = [_field("p", str(locator.page))]
    # The character range is optional: absent means the whole page, and the
    # key must distinguish "whole page" from "a span that happens to start at
    # 0". A zero-length span is refused by the contract, so there is no
    # collision with ``c=`` here, but the absence still has to be explicit.
    if locator.char_start is not None and locator.char_end is not None:
        fields.append(_field("c", f"{locator.char_start}-{locator.char_end}"))
    return fields


def _text_fields(locator: TextLocator) -> list[str]:
    fields = [_field("l", str(locator.line))]
    if locator.line_end is not None:
        fields.append(_field("le", str(locator.line_end)))
    if locator.section is not None:
        fields.append(_field("s", locator.section))
    return fields


def _csv_fields(locator: CsvLocator) -> list[str]:
    return [_field("r", str(locator.row)), _field("c", locator.column)]


def _xlsx_fields(locator: XlsxLocator) -> list[str]:
    return [_field("sh", locator.sheet_name), _field("c", locator.cell_ref)]


def _docx_fields(locator: DocxLocator) -> list[str]:
    """The DOCX fields, in the order they render.

    The **view** is a field and not an implicit default, because the same
    element in the accepted view and in the rejected view resolves to
    different text, and two addresses that resolve to different text must
    not share a key. The character range is optional: absent means the whole
    element, and the key has to say so -- a whole element and a range that
    happens to start at 0 are different addresses.
    """
    fields = [
        _field("p", locator.part),
        _field("e", locator.element_path),
        _field("v", locator.view),
    ]
    if locator.char_start is not None and locator.char_end is not None:
        fields.append(_field("c", f"{locator.char_start}-{locator.char_end}"))
    return fields


def _fields_for(locator: SourceLocator) -> list[str]:
    """Dispatch on the locator's concrete type.

    Written as an ``isinstance`` chain rather than a dict of per-kind
    functions so the type checker narrows: a dict lookup would need an
    ``ignore`` to call a ``PdfLocator`` renderer with a ``CsvLocator``, which
    is exactly the sort of thing an ``ignore`` stops anyone noticing.
    """
    if isinstance(locator, PdfLocator):
        return _page_fields(locator)
    if isinstance(locator, TextLocator):
        return _text_fields(locator)
    if isinstance(locator, CsvLocator):
        return _csv_fields(locator)
    if isinstance(locator, XlsxLocator):
        return _xlsx_fields(locator)
    if isinstance(locator, DocxLocator):
        return _docx_fields(locator)
    # LocatorKind.COMPUTATION, and anything a future kind adds before its
    # adapter exists.
    raise LocatorKeyError(
        f"{locator.locator_kind.value!r} has no extracted text and therefore no address "
        f"in source_texts; a derived number is addressed by the operator that produced "
        f"it, not by a place in a source file."
    )


def render_locator_key(locator: SourceLocator) -> str:
    """The canonical key for ``locator``.

    Raises :class:`LocatorKeyError` for a locator kind with no extracted
    text — ``COMPUTATION`` addresses a derived number by the operator that
    produced it and has nothing to extract, so no row of ``source_texts``
    should carry it.
    """
    fields = _fields_for(locator)
    # The kind is length-prefixed too, so the separator between the kind and
    # the first field cannot be moved by a value.
    return _field("k", locator.locator_kind.value) + "|" + "|".join(fields)


def split_locator_key(key: str) -> dict[str, str]:
    """Parse a key back into its components. The inverse of rendering.

    Exists so a key can be read without guessing the format, and so a test
    can assert :func:`render_locator_key` is genuinely invertible -- which is
    what makes the key *re-derivable* in ADR-0004's sense.

    Parsed by **reading the length prefixes**, not by splitting on ``|``.
    An earlier version split first and validated after, which is the same
    non-injective assumption the module exists to reject: a Markdown heading
    like ``# Task | Model`` produced a key that would not parse back, failing
    on 12.7% of real keys. The separators are read where the lengths say
    they are, so a value may contain any of them.
    """
    fields: dict[str, str] = {}
    position = 0
    while position < len(key):
        equals = key.find("=", position)
        if equals == -1:
            raise LocatorKeyError(f"component has no name at offset {position}: {key!r}")
        name = key[position:equals]
        colon = key.find(":", equals + 1)
        if colon == -1:
            raise LocatorKeyError(f"component {name!r} is not length-prefixed")
        length_text = key[equals + 1 : colon]
        if not length_text.isdigit():
            raise LocatorKeyError(f"component {name!r} has a non-numeric length")
        length = int(length_text)
        start = colon + 1
        end = start + length
        if end > len(key):
            raise LocatorKeyError(
                f"component {name!r} declares {length} characters and the key ends first"
            )
        fields[name] = key[start:end]
        position = end
        if position < len(key):
            if key[position] != "|":
                raise LocatorKeyError(
                    f"expected a separator after {name!r} at offset {position}, "
                    f"found {key[position]!r}"
                )
            position += 1
    if not fields:
        raise LocatorKeyError(f"key has no fields: {key!r}")
    return fields
