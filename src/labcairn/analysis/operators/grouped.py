"""Grouped aggregates: one vetted statistic, per group, over a selection.

One operator, and it does one thing: it computes a statistic **once per group**
of a selection and returns a **table**. Both halves of that are deliberate.

**The table is the point.** A grouped aggregate that returned one number would
have thrown away the very thing that makes it grouped: that there were three
groups and not one, that one of them held five values and another held one.
There is no "the grouped mean" of a table with three groups, and the operator
does not invent one.

**The statistic is composed, not reimplemented.** The ``aggregate`` argument
names a **registered** operator -- ``labcairn.analysis.mean@1.0.0`` -- and the
grouped operator runs *that* operator over each group rather than computing a
mean of means itself. There is exactly one implementation of "mean" in this
codebase, and it is the same one the scalar operator uses. The catalogue is
how the aggregate is looked up, and an aggregate that names no registered
operator is a **refusal**, not a guess: a run that quietly computed something
else would produce a number nobody asked for.

Five rules hold, and each of them is a way of not losing information.

**Group keys are compared as written, and the table is sorted.** The key is
the cell's text, with no case folding, no trimming and no attempt to read it
as a number, so ``a`` and ``A`` are two groups and ``10`` sorts before ``9``.
The table is sorted by key, so two runs over the same rows produce the same
table in the same order, and a manifest that hashes the result can be
compared with another manifest.

**The empty key is a group.** A cell that was recorded and holds no text gives
the key ``""``, and the table shows that group rather than dropping it: a
group the author left unnamed is still a group of the table, and dropping it
would change the shape of the answer without saying so.

**An empty group is not representable.** A group exists because a row put it
there, so a filter that removes every row of a group removes the group. There
is no way to ask for a group of nothing, and no way to get one.

**A group with no quantity has no statistic.** It is undefined, never ``0``.
The corpus's ``missing.csv`` holds the case: group ``B`` has an empty cell
and a word in it, so it has no statistic at all, while group ``A`` has one.
ADR-0004 A8 is about exactly this distinction -- an unknown is not a zero --
and a table that answered ``0`` would be answering a question nobody asked.

**Units are checked per group, not across the selection.** A group whose own
cells carry two unit tokens is refused, and the refusal names both tokens. A
selection that carries two tokens *across* its groups is not: each group is
its own measurement, and the corpus's ``units.csv`` is the case -- the whole
file is refused by the scalar operators because it holds ``kg`` and ``g``,
while every group on its own carries one token and is fine.

What the result discloses
-------------------------
A table of statistics is a claim about a set of rows, and the result says
which rows: the rows the selection named, the rows the selection's row filter
removed, the rows the missing-value policy removed because their value cell
yielded no quantity, and the rows that carried no group key at all. A named
row is counted exactly once, and the model's own validator refuses a result
whose counts and table disagree.

The missing-value policy governs the **value** column only. It is a policy
about quantities -- "what to do about a cell that yields no quantity" -- and
the group column holds names rather than numbers, so applying it there would
refuse every group that has a name.
"""

from __future__ import annotations

from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from labcairn.analysis.operators import (
    TABULAR_LOCATOR_KINDS,
    Operator,
    OperatorArgs,
    OperatorIdError,
    RegisteredOperator,
    parse_operator_reference,
)
from labcairn.analysis.operators.descriptive import DescriptiveArgs, StatisticResult
from labcairn.analysis.selection import RowSet, Selection, resolve_selection
from labcairn.analysis.values import CellAddress, CellOutcome, ValueSource, read_cell
from labcairn.sources.primitives import NonEmptyText

__all__ = [
    "AGGREGATE",
    "GroupAggregate",
    "GroupedArgs",
    "GroupedRefusedError",
    "GroupedResult",
    "aggregate",
]


class GroupedRefusedError(RuntimeError):
    """The grouped aggregate cannot be run as asked.

    A refusal, not a flag, and the same shape as the other refusals in the
    analysis layer: the caller asked for a table of statistics and the answer
    is that the table does not exist as asked, not a partial table beside a
    warning. Every message names what is wrong, because a refusal nobody can
    act on is a refusal nobody acts on.
    """


class GroupedArgs(OperatorArgs):
    """What the grouped aggregate takes: a selection, an aggregate, two columns.

    ``aggregate`` is an operator **reference** -- ``labcairn.analysis.mean@1.0.0``
    -- rather than a bare id, because the manifest quotes a reference and a
    run that computed ``mean@1.0.0`` must not be recorded as having computed
    some other version of it.

    ``aggregate_parameters`` carries the arguments the *aggregate* takes and
    the grouped operator does not: ``stdev`` needs to be told which population
    it is over, and that choice belongs to ``stdev``'s own argument model
    rather than to a second copy of it here. They are checked against the
    aggregate's own model when the run happens, so a parameter the aggregate
    does not take is a refusal rather than a silently ignored key.
    """

    #: The selection the groups and the values come from.
    selection: Selection
    #: The registered operator whose statistic is computed once per group.
    aggregate: NonEmptyText
    #: The column the groups are named by.
    by: NonEmptyText
    #: The column the statistic is computed over.
    of: NonEmptyText
    #: The aggregate's own extra parameters, in the shape its model defines.
    aggregate_parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _the_two_columns_are_columns_of_the_selection(self) -> GroupedArgs:
        if self.by == self.of:
            raise ValueError(
                f"the groups are named by {self.by!r} and the statistic is computed "
                f"over {self.of!r}, and they are the same column. A group cannot be "
                f"its own measurement."
            )
        for role, column in (("by", self.by), ("of", self.of)):
            if column not in self.selection.columns:
                raise ValueError(
                    f"the {role} column {column!r} is not one of the selection's "
                    f"columns {list(self.selection.columns)}. The grouped operator "
                    f"reads the column it groups by and the column it measures, and "
                    f"names neither by index."
                )
        if "selection" in self.aggregate_parameters:
            raise ValueError(
                "the aggregate's parameters may not include 'selection'. The "
                "grouped operator builds the selection each group is computed "
                "over, and a parameter that replaced it would measure something "
                "the caller did not ask for."
            )
        return self


class GroupAggregate(BaseModel):
    """One group, and what was computed over the rows that made it.

    ``value`` is ``None`` **exactly** when ``undefined_reason`` is set, and
    the model refuses the other two combinations -- the same rule the scalar
    statistic uses, and for the same reason: a value with no reason hides an
    unknown, and a reason with no value says nothing.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: The group key, as written in the cell that named it.
    key: str
    #: The physical rows that made this group.
    rows: tuple[int, ...]
    #: The rows whose value cell yielded a quantity.
    n_used: int
    #: The rows whose value cell was recorded and holds no text.
    n_empty: int
    #: The rows whose value cell was not recorded at all.
    n_absent: int
    #: The rows whose value cell holds text that is not a quantity.
    n_invalid: int
    #: The statistic, or ``None`` when it is undefined.
    value: float | None
    #: Why the statistic is undefined. Required when ``value`` is ``None``.
    undefined_reason: str | None = None
    #: The unit the group's used cells carry, when they carry one.
    unit: str | None = None

    @model_validator(mode="after")
    def _a_value_and_a_reason_come_together(self) -> GroupAggregate:
        if (self.value is None) != (self.undefined_reason is not None):
            raise ValueError(
                f"a group is either a value or undefined with a reason, and the "
                f"group {self.key!r} was given value={self.value!r} with "
                f"reason={self.undefined_reason!r}. A value with no reason hides "
                f"an unknown, and a reason with no value says nothing."
            )
        return self


class GroupedResult(BaseModel):
    """A table of statistics, and everything a reader needs to judge it.

    The table is sorted by group key, and the model refuses a result whose
    groups are not sorted and distinct -- so "the same rows produce the same
    table in the same order" is a property of the model rather than a promise
    the caller has to take on trust.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    operator_id: str
    operator_version: str
    #: The reference of the aggregate that was computed once per group.
    aggregate: str
    #: The column the groups were named by.
    by: str
    #: The column the statistic was computed over.
    of: str
    #: One row per group, sorted by key.
    groups: tuple[GroupAggregate, ...]
    #: The rows the selection named.
    n_rows_selected: int
    #: The rows the selection's row filter removed.
    n_rows_filtered: int
    #: The named rows the missing-value policy removed, because their value
    #: cell yielded no quantity.
    n_rows_excluded: int
    #: The named rows that carried no group key, and so belong to no group.
    n_rows_ungrouped: int
    #: The selection the table came from.
    selection: Selection

    @model_validator(mode="after")
    def _the_groups_are_sorted_and_distinct(self) -> GroupedResult:
        keys = [group.key for group in self.groups]
        if keys != sorted(set(keys)):
            raise ValueError(
                f"the groups are {keys}, which is neither sorted nor free of "
                f"repeats. Two runs over the same rows must produce the same "
                f"table in the same order, and a key that appears twice is one "
                f"group written down twice."
            )
        return self

    @model_validator(mode="after")
    def _the_counts_agree_with_the_table(self) -> GroupedResult:
        used = sum(group.n_used for group in self.groups)
        without_value = sum(
            group.n_empty + group.n_absent + group.n_invalid for group in self.groups
        )
        if self.n_rows_excluded != without_value:
            raise ValueError(
                f"the result says {self.n_rows_excluded} row(s) were excluded by "
                f"the missing-value policy, and its groups hold {without_value} "
                f"row(s) whose value cell yielded no quantity. The disclosure and "
                f"the table are the same fact and must agree."
            )
        if self.n_rows_selected != used + without_value + self.n_rows_ungrouped:
            raise ValueError(
                f"the result says {self.n_rows_selected} row(s) were selected, and "
                f"its groups account for {used} used and {without_value} without a "
                f"value, with {self.n_rows_ungrouped} ungrouped. Every named row is "
                f"counted exactly once."
            )
        return self


def aggregate(args: GroupedArgs, source: ValueSource) -> GroupedResult:
    """One statistic per group, over the rows the selection names.

    The aggregate is a registered operator and it is **run**, once per group,
    over a selection of that group's rows. Nothing about the arithmetic is
    reimplemented here, so the grouped mean and the scalar mean cannot drift
    apart: they are the same function, applied to different sets of rows.
    """
    registered = _registered_aggregate(args.aggregate)
    selection = args.selection

    # The values, under the missing-value policy. Only the value column is
    # resolved under it, because the policy is about quantities and the group
    # column holds names.
    resolved = resolve_selection(_over(selection, args.of), source)
    named = {cell.address.row for cell in resolved.cells}
    named_rows = tuple(sorted(named))

    grouped: dict[str, list[int]] = {}
    ungrouped = 0
    for row in named_rows:
        key = _group_key(source, row, args.by)
        if key is None:
            ungrouped += 1
            continue
        grouped.setdefault(key, []).append(row)

    # The aggregate's own arguments, checked once so that a parameter the
    # aggregate does not take is refused even when the table has no groups.
    _aggregate_arguments(registered, args, resolved.selection)

    groups: list[GroupAggregate] = []
    for key in sorted(grouped):
        rows = tuple(sorted(grouped[key]))
        statistic = _run_aggregate(registered, args, rows, selection, source)
        groups.append(_group(key, rows, statistic))

    excluded = sum(group.n_empty + group.n_absent + group.n_invalid for group in groups)
    return GroupedResult(
        operator_id=_AGGREGATE_OPERATOR.operator_id,
        operator_version=_AGGREGATE_OPERATOR.operator_version,
        aggregate=args.aggregate,
        by=args.by,
        of=args.of,
        groups=tuple(groups),
        n_rows_selected=len(named_rows),
        n_rows_filtered=sum(1 for row in source.rows() if row not in named),
        n_rows_excluded=excluded,
        n_rows_ungrouped=ungrouped,
        selection=selection,
    )


def _registered_aggregate(reference: str) -> RegisteredOperator[Any, Any]:
    """The registered operator a reference names, or a refusal.

    The lookup goes through the catalogue, which is built from the operator
    modules' own constants, so an aggregate that names an operator this build
    does not implement cannot be run -- and cannot be quietly replaced by
    something else that it can.

    The import is inside the function rather than at module level: the
    catalogue holds this operator among the ones it registers, so a top-level
    import would make the package import itself before it had finished
    defining the operators it registers.
    """
    from labcairn.analysis import catalog

    try:
        identifier, version = parse_operator_reference(reference)
    except OperatorIdError as error:
        raise GroupedRefusedError(
            f"{reference!r} is not an operator reference. The form is "
            f"'<operator id>@<version>', for example "
            f"'labcairn.analysis.mean@1.0.0'."
        ) from error

    registered = catalog.operator_for(identifier)
    if registered is None:
        raise GroupedRefusedError(
            f"{reference!r} names no operator this build implements. The aggregate "
            f"must be one of the registered operators, and the catalogue is what "
            f"says which those are."
        )
    if registered.operator.operator_version != version:
        raise GroupedRefusedError(
            f"{reference!r} names version {version!r}, and the catalogue holds "
            f"{registered.operator.operator_version!r} for {identifier!r}. A "
            f"reference that names a version this build does not have is refused "
            f"rather than run against the version it does."
        )
    if not issubclass(registered.operator.args_model, DescriptiveArgs):
        raise GroupedRefusedError(
            f"{identifier!r} is not an operator over a selection, so it cannot be "
            f"computed over one group of a selection."
        )
    return registered


def _aggregate_arguments(
    registered: RegisteredOperator[Any, Any], args: GroupedArgs, selection: Selection
) -> Any:
    """The aggregate's own arguments, for one group, or a refusal.

    The aggregate's argument model is the only place its parameters are
    defined, so they are checked against it rather than against a second copy
    of its shape here. A parameter the aggregate does not take is refused, and
    so is a missing one: ``stdev`` divides by ``n-1``, and a run that did not
    say which population it meant would be making that choice silently.
    """
    payload = {**args.aggregate_parameters, "selection": selection}
    try:
        return registered.operator.args_model.model_validate(payload)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors()
        )
        raise GroupedRefusedError(
            f"the aggregate {args.aggregate!r} does not take the arguments it was "
            f"given ({problems})."
        ) from error


def _run_aggregate(
    registered: RegisteredOperator[Any, Any],
    args: GroupedArgs,
    rows: tuple[int, ...],
    selection: Selection,
    source: ValueSource,
) -> StatisticResult:
    """Run the aggregate over one group's rows."""
    group_selection = Selection(
        source_id=selection.source_id,
        content_sha256=selection.content_sha256,
        columns=(args.of,),
        rows=RowSet(rows),
        missing=selection.missing,
    )
    statistic = registered.run(_aggregate_arguments(registered, args, group_selection), source)
    if not isinstance(statistic, StatisticResult):
        raise GroupedRefusedError(
            f"the aggregate {args.aggregate!r} returned {type(statistic).__name__} "
            f"rather than a statistic, so its result cannot be read as one. The "
            f"catalogue is code, and this is what an entry in it that does not do "
            f"what it says looks like."
        )
    return statistic


def _group(key: str, rows: tuple[int, ...], statistic: StatisticResult) -> GroupAggregate:
    """One row of the table."""
    reason = statistic.undefined_reason
    if reason is not None and statistic.n_used == 0:
        # The aggregate's own reason says "the selection holds no value", and in
        # a table of groups "the selection" is the wrong thing to blame: it is
        # this group that holds no value, and the other groups may hold plenty.
        reason = f"the group {key!r} holds no value, so the aggregate is undefined over it"
    return GroupAggregate(
        key=key,
        rows=rows,
        n_used=statistic.n_used,
        n_empty=statistic.n_empty,
        n_absent=statistic.n_absent,
        n_invalid=statistic.n_invalid,
        value=statistic.value,
        undefined_reason=reason,
        unit=statistic.unit,
    )


def _group_key(source: ValueSource, row: int, column: str) -> str | None:
    """The key a row's group cell names, or ``None`` when it names none.

    The key is the cell's text **as written**, which includes the empty
    string: a cell that was recorded and holds no text names the empty group,
    and a group the author left unnamed is still a group of the table.

    ``None`` means the cell was not recorded at all, which is a different
    fact: a spreadsheet does not extract a blank cell, so for a spreadsheet an
    unnamed group and an absent one are the same observation, and inventing a
    key for it would be inventing a group.
    """
    cell = read_cell(source, CellAddress(row=row, column=column))
    if cell.outcome is CellOutcome.ABSENT:
        return None
    return cell.text


def _over(selection: Selection, column: str) -> Selection:
    """The same selection, narrowed to one column."""
    return Selection(
        source_id=selection.source_id,
        content_sha256=selection.content_sha256,
        columns=(column,),
        rows=selection.rows,
        missing=selection.missing,
    )


#: The operator's id. It is one constant so that the spelling has exactly one
#: home, and the catalogue quotes it rather than writing it out.
_AGGREGATE_ID: Final[str] = "labcairn.analysis.grouped_aggregate"

_AGGREGATE_OPERATOR: Final[Operator[GroupedArgs, GroupedResult]] = Operator(
    operator_id=_AGGREGATE_ID,
    operator_version="1.0.0",
    args_model=GroupedArgs,
    result_model=GroupedResult,
    accepted_locator_kinds=TABULAR_LOCATOR_KINDS,
    summary="a vetted statistic computed once per group of a selection",
)

#: The registered grouped aggregate.
AGGREGATE: Final[RegisteredOperator[GroupedArgs, GroupedResult]] = RegisteredOperator(
    operator=_AGGREGATE_OPERATOR, run=aggregate
)
