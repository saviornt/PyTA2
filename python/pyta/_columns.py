"""Input normalization for multi-column indicators.

Every supported container is reduced to one 1-D, C-contiguous float64 array
per slot of the indicator, in slot order, together with a function that
rebuilds the caller's container from the indicator's named results. Named
containers are matched by role; unnamed ones (2-D arrays, tuples of arrays) use
the slot order, and give a tuple of outputs for a multi-output indicator.
"""

import functools
import json
import logging
import sys
from collections.abc import Mapping, Sequence
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from ._types import Float64Array, Prepared, PreparedColumns, Restore
from ._validation import (
    RESTORE_ARRAY,
    RESTORE_TUPLE,
    Slot,
    from_column,
    from_pandas_series,
    json_dump,
    restore_columns,
    restore_frame,
    restore_json_object,
    restore_records,
    role_aliases,
    role_names,
    role_of,
    squash,
    to_float64,
)

_log = logging.getLogger("pyta.validation")

#: Pairs of roles (upper, lower) that must hold row by row when an indicator
#: uses both: a high below its low is a data error, not a market move.
ORDERED_ROLES: tuple[tuple[str, str], ...] = (("high", "low"),)


def validate_columns(columns: object) -> list[str] | None:
    """Returns `columns` as a list of names, or None.

    Raises:
        TypeError: `columns` is not a list or tuple of str.
    """
    if columns is None:
        return None

    if isinstance(columns, list | tuple):
        names = cast(Sequence[object], columns)

        if all(isinstance(name, str) for name in names):
            return [cast(str, name) for name in names]

    raise TypeError(
        f"columns must be a list of column names, got {type(columns).__name__}"
        if not isinstance(columns, list | tuple)
        else "columns must contain only str column names"
    )


def needs(label: str, slots: Sequence[Slot]) -> str:
    """What an indicator needs, for error messages: "cci needs high, low and close"."""
    described = [slot.describe() for slot in slots]
    listed = ", ".join(described[:-1]) + f" and {described[-1]}" if len(slots) > 1 else described[0]
    return f"{label} needs the columns {listed}"


def normalize_columns(
    data: object, columns: list[str] | None, label: str, slots: Sequence[Slot]
) -> PreparedColumns:
    """Converts any supported container to one float64 series per slot.

    `columns` is the caller's explicit choice of names, in any order; when it
    is None, each slot takes the first column that has one of its roles.
    """
    if isinstance(data, str | bytes | bytearray):
        return _from_json(data, columns, label, slots)
    if isinstance(data, np.ndarray):
        return _from_array(cast(NDArray[Any], data), columns, label, slots)
    if isinstance(data, tuple):
        return _from_tuple(cast(tuple[object, ...], data), columns, label, slots)
    if isinstance(data, list):
        raise _one_column(label, slots, "a list")
    if isinstance(data, Mapping):
        return _from_mapping(cast(Mapping[object, object], data), columns, label, slots)

    # pandas is only inspected if the caller has already imported it.
    pd = sys.modules.get("pandas")
    if pd is not None:
        if isinstance(data, pd.DataFrame):
            return _from_pandas_frame(pd, data, columns, label, slots)
        if isinstance(data, pd.Series):
            raise _one_column(label, slots, "a pandas Series")

    raise TypeError(
        f"unsupported input type {type(data).__name__}; expected a pandas DataFrame, dict of "
        "columns, JSON string, 2-D NumPy array or tuple of arrays"
    )


def _column(value: object, key: object) -> Prepared:
    """`from_column`, with no work for a column that is already a float64 array."""
    if (
        type(value) is np.ndarray
        and value.dtype == np.float64
        and value.ndim == 1
        and value.flags.c_contiguous
    ):
        return Prepared(cast(Float64Array, value), RESTORE_ARRAY)

    return from_column(value, key)


def _one_column(label: str, slots: Sequence[Slot], kind: str) -> TypeError:
    return TypeError(
        f"{needs(label, slots)}, but {kind} holds one series; pass a DataFrame, dict of "
        "columns, JSON, a 2-D array of shape (rows, columns) or a tuple of arrays"
    )


# --- matching names to slots ----------------------------------------------------------------


def _match(
    keys: Sequence[object], columns: list[str] | None, label: str, slots: Sequence[Slot]
) -> tuple[tuple[object, str], ...]:
    """Chooses one key per slot, in slot order, with the role it was matched as."""
    chosen = _matched(tuple(keys), None if columns is None else tuple(columns), label, tuple(slots))
    _log.debug("%s: using columns %r", label, [key for key, _ in chosen])
    return chosen


@functools.lru_cache(maxsize=256)
def _matched(
    keys: tuple[object, ...], columns: tuple[str, ...] | None, label: str, slots: tuple[Slot, ...]
) -> tuple[tuple[object, str], ...]:
    """`_match`, cached: the same column names come back on every call."""
    lookup: dict[str, object] = {}

    for key in keys:
        squashed = squash(key)

        # Only a name some role uses can be ambiguous; other columns are ignored.
        if squashed in lookup and role_of(key) is not None:
            raise ValueError(
                f"column names {lookup[squashed]!r} and {key!r} are the same "
                "after ignoring case, whitespace and the separators . _ -"
            )

        lookup.setdefault(squashed, key)

    available = _Available(keys)

    def find(role: str, wanted: str | None = None) -> object | None:
        candidates = role_aliases(role)
        if wanted is not None:
            candidates = (wanted, *candidates)
        return next((lookup[name] for name in candidates if name in lookup), None)

    if columns is None:
        chosen: list[tuple[object, str]] = []
        missing: list[Slot] = []

        for slot in slots:
            found = next(
                ((key, role) for role in slot.roles if (key := find(role)) is not None), None
            )
            if found is None:
                missing.append(slot)
            else:
                chosen.append(found)

        if missing:
            raise ValueError(
                f"{needs(label, slots)}; missing: {', '.join(s.describe() for s in missing)}. "
                f"Available columns: {available}. Rename the input's columns, or pass "
                "columns=[...] to choose them"
            )

        return tuple(chosen)

    return _match_explicit(columns, label, slots, find, available)


class _Available:
    """The input's column names for an error message, joined only when one is raised."""

    def __init__(self, keys: Sequence[object]) -> None:
        self.keys = keys

    def __str__(self) -> str:
        return ", ".join(repr(key) for key in self.keys) or "none"


def _match_explicit(
    columns: Sequence[str],
    label: str,
    slots: Sequence[Slot],
    find: Any,
    available: _Available,
) -> tuple[tuple[object, str], ...]:
    """Assigns each explicitly named column to the slot for its role."""
    filled: dict[str, tuple[str, object, str]] = {}  # slot name -> (name, key, role)

    for name in columns:
        role = role_of(name)

        if role is None:
            raise ValueError(
                f"column {name!r} is not a recognized column name; use one of "
                f"{', '.join(role_names())} (or an alias such as 'adjusted close'). "
                f"{needs(label, slots)}"
            )

        slot = next((slot for slot in slots if role in slot.roles), None)

        if slot is None:
            raise ValueError(
                f"column {name!r} ({role}) is not an input of {label}; {needs(label, slots)}"
            )

        if slot.name in filled:
            raise ValueError(
                f"columns {filled[slot.name][0]!r} and {name!r} both fill {label}'s "
                f"{slot.describe()} input; {needs(label, slots)}"
            )

        key = find(role, squash(name))

        if key is None:
            raise ValueError(f"column {name!r} not found; available columns: {available}")

        filled[slot.name] = (name, key, role)

    empty = [slot.describe() for slot in slots if slot.name not in filled]

    if empty:
        raise ValueError(f"{needs(label, slots)}; columns= leaves out: {', '.join(empty)}")

    return tuple((filled[slot.name][1], filled[slot.name][2]) for slot in slots)


def _prepared(
    values: Sequence[Float64Array],
    labels: Sequence[object],
    roles: Sequence[str],
    restore: Restore,
    named: bool = True,
) -> PreparedColumns:
    """Checks the columns' lengths; `named` is False when `labels` are positions."""
    lengths = {array.shape[0] for array in values}

    if len(lengths) > 1:
        sizes = ", ".join(
            f"{label!r}: {array.shape[0]}" for label, array in zip(labels, values, strict=True)
        )
        raise ValueError(f"columns have different lengths ({sizes})")

    return PreparedColumns(
        tuple(values),
        tuple(str(label) for label in labels),
        tuple(roles),
        restore,
        tuple(labels) if named else (),
    )


# --- containers -----------------------------------------------------------------------------


def _reject_columns(columns: list[str] | None, kind: str, slots: Sequence[Slot]) -> None:
    if columns is not None:
        order = ", ".join(slot.name for slot in slots)
        raise ValueError(
            f"columns= is not valid for {kind}, which has no column names; "
            f"its columns are taken in the order {order}"
        )


def _unnamed(
    arrays: Sequence[Float64Array], label: str, slots: Sequence[Slot], kind: str
) -> tuple[list[str], list[str]]:
    """Labels and roles for unnamed columns, which follow the slot order."""
    if len(arrays) != len(slots):
        order = ", ".join(slot.name for slot in slots)
        raise ValueError(
            f"{label} takes {len(slots)} columns in the order {order}; {kind} has {len(arrays)}"
        )

    return [f"column {i} ({slot.name})" for i, slot in enumerate(slots)], [
        slot.roles[0] for slot in slots
    ]


def _from_array(
    data: NDArray[Any], columns: list[str] | None, label: str, slots: Sequence[Slot]
) -> PreparedColumns:
    if data.ndim == 1:
        raise _one_column(label, slots, "a 1-D array")
    if data.ndim != 2:
        raise ValueError(f"expected a 2-D array of shape (rows, columns), got shape {data.shape}")

    _reject_columns(columns, "a 2-D array", slots)

    if isinstance(data, np.ma.MaskedArray):
        data = np.ma.filled(data.astype(np.float64), np.nan)

    arrays = [to_float64(data[:, i]) for i in range(data.shape[1])]
    labels, roles = _unnamed(arrays, label, slots, "the array")

    return _prepared(arrays, labels, roles, RESTORE_ARRAY, named=False)


def _from_tuple(
    data: tuple[object, ...], columns: list[str] | None, label: str, slots: Sequence[Slot]
) -> PreparedColumns:
    if not data or not all(isinstance(item, list | tuple | np.ndarray) for item in data):
        raise _one_column(label, slots, "a tuple of numbers")

    _reject_columns(columns, "a tuple of arrays", slots)

    arrays = [_column(item, i).values for i, item in enumerate(data)]
    labels, roles = _unnamed(arrays, label, slots, "the tuple")

    return _prepared(arrays, labels, roles, RESTORE_TUPLE, named=False)


def _from_pandas_frame(
    pd: Any, data: Any, columns: list[str] | None, label: str, slots: Sequence[Slot]
) -> PreparedColumns:
    if data.columns.nlevels > 1:
        raise TypeError("DataFrames with MultiIndex columns are not supported; select the columns")

    chosen = _match(list(data.columns), columns, label, slots)
    arrays = [from_pandas_series(pd, data[key], None).values for key, _ in chosen]

    return _prepared(
        arrays,
        [key for key, _ in chosen],
        [role for _, role in chosen],
        restore_frame(pd, data.index),
    )


def _from_mapping(
    data: Mapping[object, object], columns: list[str] | None, label: str, slots: Sequence[Slot]
) -> PreparedColumns:
    chosen = _match(list(data), columns, label, slots)
    prepared = [_column(data[key], key) for key, _ in chosen]
    # Each output keeps the container type of the first input column.
    inner = prepared[0].restore

    return _prepared(
        [column.values for column in prepared],
        [key for key, _ in chosen],
        [role for _, role in chosen],
        restore_columns(lambda out, name: inner(((name, out),))),
    )


def _from_json(
    data: str | bytes | bytearray, columns: list[str] | None, label: str, slots: Sequence[Slot]
) -> PreparedColumns:
    """Accepts a JSON array of records or an object of arrays.

    `null` is a gap (NaN). The result is returned as JSON of the same shape
    and the same type (str or bytes), with NaN written as `null`.
    """
    try:
        parsed = json.loads(data)
    except ValueError as error:  # JSONDecodeError and UnicodeDecodeError
        raise ValueError(f"invalid JSON input: {error}") from error

    dump = json_dump(not isinstance(data, str))

    if isinstance(parsed, list):
        rows = cast(list[Any], parsed)
        records = [cast(dict[str, Any], row) for row in rows if isinstance(row, dict)]

        if not records:
            raise _one_column(label, slots, "a JSON array of numbers")
        if len(records) < len(rows):
            raise TypeError("JSON array mixes records and numbers; use one or the other")

        chosen = _match(list(records[0]), columns, label, slots)
        arrays = [
            from_column([row.get(cast(str, key)) for row in records], key).values
            for key, _ in chosen
        ]

        return _prepared(
            arrays,
            [key for key, _ in chosen],
            [role for _, role in chosen],
            restore_records(dump),
        )

    if isinstance(parsed, dict):
        table = cast(dict[str, Any], parsed)
        chosen = _match(list(table), columns, label, slots)
        arrays: list[Float64Array] = []

        for key, _ in chosen:
            if not isinstance(table[cast(str, key)], list):
                raise TypeError(f"JSON column {key!r} must be an array of numbers")
            arrays.append(from_column(table[cast(str, key)], key).values)

        return _prepared(
            arrays,
            [key for key, _ in chosen],
            [role for _, role in chosen],
            restore_json_object(dump),
        )

    raise TypeError("JSON input must be an array of records or an object of arrays")
