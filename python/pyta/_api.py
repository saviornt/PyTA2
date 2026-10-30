"""Shared execution boundary between the public API and the native module.

Every runner takes the indicator's `OutputNames` and its validated parameters,
which are passed to the native function positionally after the input (ints or
floats; an empty tuple for a parameterless indicator such as OBV). A native
function returns one float64 array for a single-output indicator, or a list of
arrays in documented output order for a multi-output one; each output is
re-padded for a skipped leading NaN run and named in the input's casing.

`output=None` (the default) restores the input's own container through
`Prepared.restore`; any other `output` is resolved by `_export.exporter` before
any work and converts the result to that target instead.
"""

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

import numpy as np

from ._columns import (
    NONNEGATIVE_ROLES,
    ORDERED_ROLES,
    normalize_columns,
    reject_negative,
    validate_columns,
)
from ._export import Export, exporter
from ._native import MAX_ABS_INPUT
from ._outputs import OutputNames
from ._types import Float64Array, Prepared, PreparedColumns
from ._validation import VOLUME, Slot, normalize, role_of

_log = logging.getLogger("pyta.api")

#: An indicator's validated parameters in its native function's order; `()`
#: for a parameterless indicator (OBV), whose native function takes only the input.
type Params = tuple[int | float, ...]

#: One float64 array, or one per output in documented order.
type NativeResult = Float64Array | Sequence[Float64Array]

#: `native(values, *params)`: one series and the indicator's parameters.
type NativeIndicator = Callable[..., NativeResult]
#: `native(datasets, *params)`: each entry a result or the dataset's exception.
type NativeBatchIndicator = Callable[..., Sequence[NativeResult | Exception]]
#: `native(columns, *params)`: one array per slot.
type NativeColumnsIndicator = Callable[..., NativeResult]
#: `native(datasets, *params)`: one list of slot arrays per dataset.
type NativeColumnsBatchIndicator = Callable[..., Sequence[NativeResult | Exception]]


def run(
    native: NativeIndicator,
    outputs: OutputNames,
    data: object,
    params: Params,
    column: object,
    default_column: str,
    columns: object = None,
    output: object = None,
) -> Any:
    """Runs one single-series indicator on validated `params` and restores the container.

    `default_column` is the column role the indicator calculates on; it is used
    when the caller passes no `column` and the input has more than one.
    `columns` must be None: it is the multi-column override. `output` names
    the container to return (`_export.TARGETS`), or is None for the input's own.
    """
    export = None if output is None else exporter(output)

    if columns is not None:
        _reject_columns(outputs.indicator, columns)

    if column is not None and not isinstance(column, str):
        raise TypeError(f"column must be a str or None, got {type(column).__name__}")

    prepared = normalize(data, column, default_column)
    first, valid = _trim(prepared.values)
    # A column matched to the volume role must not be negative (`NONNEGATIVE_ROLES`),
    # as for multi-column input; Rust accepts any finite value. The inline lookup
    # spares a name known not to be volume (SMA on close) any function call.
    if prepared.names and _VOLUME_NAMES.get(prepared.names[0]) is not False:
        _reject_negative_volume(prepared.names[0], valid, first)
    results = _pad_all(native(valid, *params), first, prepared.values.shape[0])

    if export is None:
        return prepared.restore(outputs.cased(prepared.names), results)
    return export(outputs.cased(prepared.names), results, prepared.index)


#: Single-column names seen so far: whether each is matched to the volume role.
_VOLUME_NAMES: dict[object, bool] = {}
#: Bound on `_VOLUME_NAMES`, so arbitrary column names cannot grow it without end.
_VOLUME_NAMES_MAX = 4096


def _reject_negative_volume(name: object, valid: Float64Array, first: int) -> None:
    """Rejects a negative value when the single column used, `name`, is the volume role.

    The role lookup is remembered per name; callers skip this function for a
    name already known not to be volume, so SMA on close pays one dict lookup.
    """
    volume = _VOLUME_NAMES.get(name)
    if volume is None:
        volume = role_of(name) == VOLUME
        if len(_VOLUME_NAMES) < _VOLUME_NAMES_MAX:
            _VOLUME_NAMES[name] = volume
    if volume:
        reject_negative(VOLUME, str(name), valid, first)


def _pad_all(result: NativeResult, first: int, length: int) -> Sequence[Float64Array]:
    """`_pad` applied to every output of a native result, in output order."""
    if isinstance(result, np.ndarray):
        return (result if first == 0 else _pad(result, first, length),)

    return [_pad(values, first, length) for values in result]


def _leading_nan_count(values: Float64Array) -> int:
    """Number of NaN values before the first non-NaN value."""
    # The common case (no leading gap) is decided in O(1).
    if values.shape[0] == 0 or not np.isnan(values[0]):
        return 0

    valid = ~np.isnan(values)

    if not valid.any():
        return values.shape[0]

    return int(valid.argmax())


def _trim(values: Float64Array) -> tuple[int, Float64Array]:
    """Splits off a leading NaN run, returning its length and the remaining values.

    Leading NaNs (for example the warm-up of another indicator) are skipped so
    indicators can be chained. NaN after the first valid value is rejected.
    """
    first = _leading_nan_count(values)

    if first == 0:
        return 0, values

    if first == values.shape[0]:
        raise ValueError("input contains no valid values; every value is NaN or missing")

    valid = values[first:]
    # Same test as Rust's validation; false for NaN and infinity too.
    bad = np.flatnonzero(~(np.abs(valid) <= MAX_ABS_INPUT))

    if bad.size:
        # Rust would report an index relative to the trimmed slice.
        index = first + int(bad[0])

        if np.isfinite(values[index]):
            limit = f"{MAX_ABS_INPUT:.0e}".replace("e+", "e")
            raise ValueError(
                f"value at index {index} is too large in magnitude; "
                f"values must be between -{limit} and {limit}"
            )

        raise ValueError(
            f"non-finite value (NaN or infinity) at index {index}; "
            "only leading NaN values are skipped"
        )

    return first, valid


def _pad(result: Float64Array, first: int, length: int) -> Float64Array:
    """Restores a skipped leading NaN run in front of a result."""
    if first == 0:
        return result

    padded = np.empty(length, dtype=np.float64)
    padded[:first] = np.nan
    padded[first:] = result

    return padded


def run_batch(
    native: NativeBatchIndicator,
    outputs: OutputNames,
    datasets: object,
    params: Params,
    column: object,
    default_column: str,
    columns: object = None,
    output: object = None,
) -> Any:
    """Runs one indicator over many datasets and returns results in the same shape.

    `params`, `column` and `output` are shared by every dataset, so an invalid
    one raises (the indicator validates `params` before calling). A dataset that
    is malformed or fails to calculate or convert is not raised: its exception
    is returned in its place so the other datasets still complete.
    """
    export = None if output is None else exporter(output)
    label = outputs.indicator
    _reject_columns(label, columns)

    if column is not None and not isinstance(column, str):
        raise TypeError(f"column must be a str or None, got {type(column).__name__}")

    keys, items = _datasets(datasets)

    outcomes: list[Any] = [None] * len(items)
    failed = 0
    pending: list[tuple[int, Prepared, int]] = []
    arrays: list[Float64Array] = []

    # Python cleans and validates each dataset; a malformed one fails alone.
    for position, item in enumerate(items):
        try:
            prepared = normalize(item, column, default_column)
            first, valid = _trim(prepared.values)
            if prepared.names and _VOLUME_NAMES.get(prepared.names[0]) is not False:
                _reject_negative_volume(prepared.names[0], valid, first)
        except (TypeError, ValueError) as error:
            outcomes[position] = error
            failed += 1
            continue

        pending.append((position, prepared, first))
        arrays.append(valid)

    results: Sequence[NativeResult | Exception] = native(arrays, *params) if arrays else ()

    for (position, prepared, first), result in zip(pending, results, strict=True):
        if isinstance(result, BaseException):
            outcomes[position] = result
            failed += 1
        else:
            padded = _pad_all(result, first, prepared.values.shape[0])
            cased = outputs.cased(prepared.names)

            if export is None:
                outcomes[position] = prepared.restore(cased, padded)
            elif not _export_into(outcomes, position, export, cased, padded, prepared.index):
                failed += 1

    if failed:
        _log_failures(label, outcomes, keys, failed)

    return outcomes if keys is None else dict(zip(keys, outcomes, strict=True))


def _export_into(
    outcomes: list[Any],
    position: int,
    export: Export,
    names: Sequence[str],
    results: Sequence[Float64Array],
    index: Any,
) -> bool:
    """Stores one dataset's exported result, or its conversion error, at `position`.

    False when the conversion failed (an index that JSON or CSV cannot hold).
    """
    try:
        outcomes[position] = export(names, results, index)
    except (TypeError, ValueError) as error:
        outcomes[position] = error
        return False
    return True


def _datasets(datasets: object) -> tuple[list[Any] | None, list[Any]]:
    """The keys (None for a list) and the datasets of a batch."""
    if isinstance(datasets, Mapping):
        mapping = cast(Mapping[Any, Any], datasets)
        return list(mapping), list(mapping.values())
    if isinstance(datasets, list):
        return None, cast(list[Any], datasets)

    raise TypeError(
        f"datasets must be a list or a mapping of datasets, got {type(datasets).__name__}"
    )


def _reject_columns(label: str, columns: object) -> None:
    if columns is not None:
        raise ValueError(
            f"columns= is for multi-column indicators; {label} uses one column, "
            "so pass column= instead"
        )


def _reject_column(label: str, column: object) -> None:
    if column is not None:
        raise ValueError(
            f"column= is for single-column indicators; {label} uses several columns, "
            "so pass columns=[...] instead"
        )


# --- multi-column indicators ----------------------------------------------------------------


def run_columns(
    native: NativeColumnsIndicator,
    outputs: OutputNames,
    data: object,
    params: Params,
    columns: object,
    slots: Sequence[Slot],
    column: object = None,
    output: object = None,
) -> Any:
    """Runs one multi-column indicator on validated `params` and restores the container.

    `slots` are the indicator's inputs in the order the native function takes
    them. `column` must be None: it is the single-column override. `output` is
    as for `run`.
    """
    export = None if output is None else exporter(output)
    label = outputs.indicator
    _reject_column(label, column)
    names = validate_columns(columns)

    prepared = normalize_columns(data, names, label, slots)
    first, valid = _trim_columns(prepared)

    try:
        result = native(valid, *params)
    except ValueError:
        explained = _value_error(prepared, first, valid)
        if explained is None:
            raise
        raise explained from None

    results = _pad_all(result, first, prepared.values[0].shape[0])

    if export is None:
        return prepared.restore(outputs.cased_text(prepared.names), results)
    return export(outputs.cased_text(prepared.names), results, prepared.index)


def run_columns_batch(
    native: NativeColumnsBatchIndicator,
    outputs: OutputNames,
    datasets: object,
    params: Params,
    columns: object,
    slots: Sequence[Slot],
    column: object = None,
    output: object = None,
) -> Any:
    """`run_batch` for a multi-column indicator; `columns` and `output` are shared."""
    export = None if output is None else exporter(output)
    label = outputs.indicator
    _reject_column(label, column)
    names = validate_columns(columns)
    keys, items = _datasets(datasets)

    outcomes: list[Any] = [None] * len(items)
    failed = 0
    pending: list[tuple[int, PreparedColumns, int]] = []
    inputs: list[list[Float64Array]] = []

    for position, item in enumerate(items):
        try:
            prepared = normalize_columns(item, names, label, slots)
            first, valid = _trim_columns(prepared)
        except (TypeError, ValueError) as error:
            outcomes[position] = error
            failed += 1
            continue

        pending.append((position, prepared, first))
        inputs.append(valid)

    results: Sequence[NativeResult | Exception] = native(inputs, *params) if inputs else ()

    for (position, prepared, first), valid, result in zip(pending, inputs, results, strict=True):
        if isinstance(result, BaseException):
            explained = (
                _value_error(prepared, first, valid) if isinstance(result, ValueError) else None
            )
            outcomes[position] = explained or result
            failed += 1
        else:
            padded = _pad_all(result, first, prepared.values[0].shape[0])
            cased = outputs.cased_text(prepared.names)

            if export is None:
                outcomes[position] = prepared.restore(cased, padded)
            elif not _export_into(outcomes, position, export, cased, padded, prepared.index):
                failed += 1

    if failed:
        _log_failures(label, outcomes, keys, failed)

    return outcomes if keys is None else dict(zip(keys, outcomes, strict=True))


def _trim_columns(prepared: PreparedColumns) -> tuple[int, list[Float64Array]]:
    """Skips the longest leading NaN run across the columns, and checks row order.

    Every column is cut at the same row, so chained outputs (each with its own
    warm-up) stay aligned. Rows are then checked against `ORDERED_ROLES` (high
    not below low) and `NONNEGATIVE_ROLES` (volume not negative), naming the
    column and the row in the caller's data. Values themselves are left to Rust,
    which rejects any non-finite or too-large one; `_value_error` then explains
    that error by column.
    """
    first = max(_leading_nan_count(values) for values in prepared.values)
    rows = prepared.values[0].shape[0]

    if first == rows:
        raise ValueError("input contains no complete row; every row has a NaN or missing value")

    valid = [values[first:] for values in prepared.values] if first else list(prepared.values)

    roles = prepared.roles

    for upper, lower in ORDERED_ROLES:
        if upper in roles and lower in roles:
            high = valid[roles.index(upper)]
            low = valid[roles.index(lower)]

            # NaN compares false, so it is left for the value check.
            if (high < low).any():
                row = int(np.flatnonzero(high < low)[0])
                raise ValueError(
                    f"column {prepared.labels[roles.index(upper)]!r} ({upper}) is below "
                    f"column {prepared.labels[roles.index(lower)]!r} ({lower}) at index "
                    f"{first + row} ({float(high[row])} < {float(low[row])}); "
                    f"{upper} must be at least {lower} on every row"
                )

    # Inline rather than one shared call: an indicator without a volume slot
    # pays only this membership test (a shared check function measured ~0.2 us more on
    # a 100-row CCI call).
    for role in NONNEGATIVE_ROLES:
        if role in roles:
            position = roles.index(role)
            reject_negative(role, prepared.labels[position], valid[position], first)

    return first, valid


def _value_error(
    prepared: PreparedColumns, first: int, valid: list[Float64Array]
) -> ValueError | None:
    """The first non-finite or too-large value after the leading run, by column and row.

    Called only after Rust has rejected an input, so the scan costs nothing on
    success. None when every value is valid (Rust failed for another reason).
    """
    for label, values in zip(prepared.labels, valid, strict=True):
        # Same test as Rust's validation; false for NaN and infinity too.
        bad = np.flatnonzero(~(np.abs(values) <= MAX_ABS_INPUT))

        if bad.size:
            index = first + int(bad[0])

            if np.isfinite(values[bad[0]]):
                limit = f"{MAX_ABS_INPUT:.0e}".replace("e+", "e")
                return ValueError(
                    f"column {label!r}: value at index {index} is too large in magnitude; "
                    f"values must be between -{limit} and {limit}"
                )

            return ValueError(
                f"column {label!r}: non-finite value (NaN or infinity) at index {index}; "
                "only leading NaN values are skipped"
            )

    return None


def _log_failures(label: str, outcomes: list[Any], keys: list[Any] | None, failed: int) -> None:
    """Logs each failed dataset at DEBUG and one WARNING summary for the batch."""
    if _log.isEnabledFor(logging.DEBUG):
        for position, outcome in enumerate(outcomes):
            if isinstance(outcome, BaseException):
                name = position if keys is None else repr(keys[position])
                _log.debug("%s: dataset %s failed: %s", label, name, outcome)

    _log.warning(
        "%s: %d of %d datasets failed; each failure is returned in its place",
        label,
        failed,
        len(outcomes),
    )
