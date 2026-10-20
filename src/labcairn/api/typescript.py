"""The typed contract, and the TypeScript types generated from it.

``docs/plans/LC-P1-11-12-task-breakdown.md`` §2.7: *"the TypeScript side
therefore gets its types from **one** source, not from a hand-written mirror:
the API's response models are exported as a JSON Schema or an OpenAPI
document, and the TypeScript types are generated from it and checked in CI
against the Python models. A hand-written mirror is a second spelling of the
API's shape, and it is the same defect the catalogue's docstring warns
about."*

So the types are **generated**, and the check is a **comparison**, not a
promise. :func:`render_types` turns the OpenAPI document into TypeScript, the
file is checked in, and ``tests/test_api.py`` asserts that the checked-in file
is byte-for-byte what the Python models produce *now*. A model that changes
without the file being regenerated is a failing test, not a stale file
somebody notices in the browser.

The generator is deliberately small and mechanical. It reads JSON Schema and
writes TypeScript; it does not know what a task is, and it holds no list of
model names, so a model added to the application layer appears in the
TypeScript without anybody adding it to a list here.

Regenerating
------------

::

    uv run python -m labcairn.api.typescript web/src/api/generated.ts

and checking::

    uv run pytest -q tests/test_api.py
"""

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from labcairn.api.app import contract_app

#: The logger the generator reports through.
logger = logging.getLogger("labcairn.api")

#: Where the generated types are checked in, relative to the repository root.
GENERATED_TYPES_PATH = Path("web") / "src" / "api" / "generated.ts"

#: The header every generated file carries. It says where the file comes from
#: and what to do when it is wrong, because a generated file that nobody
#: regenerates is a file that lies.
HEADER = """\
// GENERATED FILE. Do not edit it by hand, and do not run prettier over it.
//
// It is generated from the API's OpenAPI document, which is generated from the
// application layer's response models:
//
//     uv run python -m labcairn.api.typescript web/src/api/generated.ts
//
// `tests/test_api.py` compares this file with the document the Python models
// produce now, so a model that changes without this file being regenerated is
// a failing test rather than a stale type. The generator writes the
// formatting too -- the repository's prettier settings, with no semicolons,
// single quotes and a hundred-column width -- so that a regeneration does
// not produce a file that prettier would then rewrite.
"""

#: A property name that TypeScript can use unquoted.
_IDENTIFIER = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")

#: The width a generated line is allowed to be, which is the repository's
#: prettier ``printWidth``. The generator breaks its own long lines rather
#: than leaving it to prettier, because prettier rewriting the file would
#: break the drift test that compares this file with the models.
PRINT_WIDTH = 100

#: The names TypeScript reserves.
_RESERVED = frozenset(
    {
        "break",
        "case",
        "catch",
        "class",
        "const",
        "continue",
        "debugger",
        "default",
        "delete",
        "do",
        "else",
        "enum",
        "export",
        "extends",
        "false",
        "finally",
        "for",
        "function",
        "if",
        "import",
        "in",
        "instanceof",
        "new",
        "null",
        "return",
        "super",
        "switch",
        "this",
        "throw",
        "true",
        "try",
        "typeof",
        "var",
        "void",
        "while",
        "with",
    }
)


def render_types(document: Mapping[str, Any]) -> str:
    """The TypeScript declarations for an OpenAPI document's schemas.

    Every schema in ``components.schemas`` becomes one exported type, named
    after the schema. The names are the Python class names, so the type the
    web app imports is named after the model it came from.
    """
    schemas = document.get("components", {}).get("schemas", {})
    if not isinstance(schemas, Mapping) or not schemas:
        msg = "the OpenAPI document carries no component schemas, so there is no contract"
        raise ValueError(msg)
    blocks = [HEADER]
    for name in sorted(schemas):
        blocks.append(_render_alias(name, schemas[name], schemas))
    return "\n".join(blocks)


def _render_alias(name: str, schema: Mapping[str, Any], schemas: Mapping[str, Any]) -> str:
    """One exported type.

    A union that does not fit on its line is broken across lines, the way the
    repository's prettier configuration would break it: first onto an
    indented line, and then — when even that does not fit — one member per
    line with a leading ``|``.
    """
    parts = _union_parts(schema, schemas)
    if parts is None:
        return f"export type {name} = {_render(schema, schemas)}\n"
    body = " | ".join(parts)
    if len(f"export type {name} = {body}") <= PRINT_WIDTH:
        return f"export type {name} = {body}\n"
    if len(f"  {body}") <= PRINT_WIDTH:
        return f"export type {name} =\n  {body}\n"
    return f"export type {name} =\n" + "\n".join(f"  | {part}" for part in parts) + "\n"


def _union_parts(schema: Mapping[str, Any], schemas: Mapping[str, Any]) -> list[str] | None:
    """The members of a union schema, or ``None`` if it is not one."""
    if "anyOf" in schema:
        return _union_members(schema["anyOf"], schemas)
    if "oneOf" in schema:
        return _union_members(schema["oneOf"], schemas)
    if "enum" in schema:
        return _enum_members(schema["enum"])
    return None


def _render(schema: Mapping[str, Any], schemas: Mapping[str, Any]) -> str:
    """The TypeScript spelling of one JSON Schema."""
    if "$ref" in schema:
        return _reference_name(str(schema["$ref"]))
    if "allOf" in schema:
        return _render_all_of(schema["allOf"], schemas)
    if "anyOf" in schema:
        return _render_union(schema["anyOf"], schemas)
    if "oneOf" in schema:
        return _render_union(schema["oneOf"], schemas)
    if "enum" in schema:
        return _render_enum(schema["enum"])
    if "const" in schema:
        return _literal(schema["const"])

    kind = schema.get("type")
    if kind == "object" or "properties" in schema:
        return _render_object(schema, schemas)
    if kind == "array":
        item = _render(schema.get("items", {}), schemas)
        return f"({item})[]" if " | " in item else f"{item}[]"
    if kind == "string":
        return "string"
    if kind in {"integer", "number"}:
        return "number"
    if kind == "boolean":
        return "boolean"
    if kind == "null":
        return "null"
    if kind is None:
        additional = _render_additional(schema, schemas)
        if additional is not None:
            return additional
        # A schema with no type says "anything". `unknown` is the TypeScript
        # spelling of that, and it is the spelling that does not require a
        # cast at every use; `any` would be the other, and `any` is a hole.
        return "unknown"
    msg = f"the schema {schema!r} has a shape this generator does not know"
    raise ValueError(msg)


def _render_additional(schema: Mapping[str, Any], schemas: Mapping[str, Any]) -> str | None:
    """The spelling of a schema's additional properties, or ``None``.

    Pydantic writes ``dict[str, Any]`` as an object with
    ``additionalProperties: true`` and ``extra="forbid"`` as one with
    ``additionalProperties: false``. The first is a map of anything and the
    second is a map of nothing, and they are not the same type.
    """
    additional = schema.get("additionalProperties")
    if additional is True:
        return "Record<string, unknown>"
    if isinstance(additional, Mapping):
        return f"Record<string, {_render(additional, schemas)}>"
    return None


def _render_all_of(parts: Any, schemas: Mapping[str, Any]) -> str:
    """An ``allOf``, which pydantic emits for a model that inherits one.

    Pydantic writes a subclass as its base plus the fields it adds, so the
    TypeScript is the base intersected with the fields. The base is kept as a
    name rather than being expanded, so the base's own type stays the one
    thing both surfaces agree on.
    """
    if not isinstance(parts, Sequence) or not parts:
        return "unknown"
    base = ""
    fields: dict[str, Any] = {}
    required: set[str] = set()
    for part in parts:
        resolved = _resolve(part, schemas)
        if "$ref" in part and not base:
            base = _reference_name(str(part["$ref"]))
            continue
        properties = resolved.get("properties", {})
        if isinstance(properties, Mapping):
            fields.update(properties)
        names = resolved.get("required", [])
        if isinstance(names, Sequence) and not isinstance(names, str):
            required.update(str(name) for name in names)
    if not fields and not base:
        return "unknown"
    rendered = _render_fields(fields, required, schemas)
    if base:
        return f"{base} & {rendered}"
    return rendered


def _render_union(parts: Any, schemas: Mapping[str, Any]) -> str:
    """A union of schemas, which pydantic emits for an optional field."""
    return " | ".join(_union_members(parts, schemas))


def _union_members(parts: Any, schemas: Mapping[str, Any]) -> list[str]:
    """The members of a union, each rendered."""
    if not isinstance(parts, Sequence) or not parts:
        return ["unknown"]
    rendered = [_render(part, schemas) for part in parts]
    return list(dict.fromkeys(rendered))


def _render_enum(values: Any) -> str:
    """An enumeration, as a union of literals."""
    return " | ".join(_enum_members(values))


def _enum_members(values: Any) -> list[str]:
    """The literals of an enumeration."""
    if not isinstance(values, Sequence) or not values:
        return ["string"]
    return [_literal(value) for value in values]


def _render_object(schema: Mapping[str, Any], schemas: Mapping[str, Any]) -> str:
    """An object, as an object type."""
    properties = schema.get("properties", {})
    if not isinstance(properties, Mapping) or not properties:
        additional = _render_additional(schema, schemas)
        if additional is not None:
            return additional
        return "Record<string, never>"
    names = schema.get("required", [])
    required: set[str] = set()
    if isinstance(names, Sequence) and not isinstance(names, str):
        required = {str(name) for name in names}
    return _render_fields(properties, required, schemas)


def _render_fields(
    properties: Mapping[str, Any], required: set[str], schemas: Mapping[str, Any]
) -> str:
    """The body of an object type: one line per property.

    The members are separated by nothing but the newline, and there is no
    trailing comma, because that is what the repository's prettier
    configuration produces for a type literal.
    """
    lines: list[str] = []
    for name in properties:
        rendered = _render(properties[name], schemas)
        optional = "" if name in required else "?"
        lines.append(f"  {_property_name(name)}{optional}: {rendered}")
    if not lines:
        return "Record<string, never>"
    return "{\n" + "\n".join(lines) + "\n}"


def _resolve(part: Any, schemas: Mapping[str, Any]) -> Mapping[str, Any]:
    """The schema a part names, following a reference if it is one."""
    if not isinstance(part, Mapping):
        return {}
    if "$ref" not in part:
        return part
    name = _reference_name(str(part["$ref"]))
    resolved = schemas.get(name)
    return resolved if isinstance(resolved, Mapping) else {}


def _reference_name(reference: str) -> str:
    """The schema name a ``$ref`` points at."""
    return reference.rsplit("/", 1)[-1]


def _property_name(name: str) -> str:
    """A property name TypeScript will accept."""
    if _IDENTIFIER.match(name) and name not in _RESERVED:
        return name
    return _quote(name)


def _literal(value: Any) -> str:
    """A literal value, as TypeScript spells it.

    Strings are single-quoted, because the repository's prettier
    configuration says so and the file is checked against it.
    """
    if isinstance(value, str):
        return _quote(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return json.dumps(value)
    return "unknown"


def _quote(value: str) -> str:
    """A string literal, in the quoting style the repository uses.

    Single quotes, unless the value contains a single quote and no double
    quote — which is the same rule prettier applies, and the same reason.
    """
    if "'" in value and '"' not in value:
        return json.dumps(value)
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def write_types(path: Path, document: Mapping[str, Any]) -> Path:
    """Write the generated types to *path*, and return it.

    The bytes are written with LF endings whatever the platform's default
    is: the repository's ``.gitattributes`` says the checkout is LF on every
    platform, and a file that changed its line endings between two machines
    would make the drift test fail for a reason that has nothing to do with
    the contract.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render_types(document).encode("utf-8"))
    return path


def main(argv: Sequence[str] | None = None) -> int:
    """Regenerate the TypeScript types from the API's contract.

    The path is the first argument and defaults to
    ``web/src/api/generated.ts`` relative to the working directory.
    """
    arguments = list(sys.argv[1:] if argv is None else argv)
    target = Path(arguments[0]) if arguments else GENERATED_TYPES_PATH
    document = contract_app().openapi()
    written = write_types(target, document)
    # Product code logs, it does not print: the rule is in the project's ruff
    # configuration, and it holds for the entry point as much as for the rest.
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    logger.info("wrote %s", written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["GENERATED_TYPES_PATH", "render_types", "write_types"]
