"""Shared execution boundary between the public API and the native module.

Every runner takes the indicator's `OutputNames` and its validated parameters,
which are passed to the native function positionally after the input. A native
function returns one float64 array for a single-output indicator, or a list of
arrays in documented output order for a multi-output one; each output is
re-padded for a skipped leading NaN run and named in the input's casing.
"""

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

import numpy as np

from ._columns import ORDERED_ROLES, normalize_columns, validate_columns
from ._native import MAX_ABS_INPUT
from ._outputs import OutputNames
from ._types import Float64Array, Outputs, Prepared, PreparedColumns, Restore
from ._validation import Slot, normalize

_log = logging.getLogger("pyta.api")

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
    params: tuple[int, ...],
    column: object,
    default_column: str,
    columns: object = None,
) -> Any:
    """Runs one single-series indicator on validated `params` and restores the container.

    `default_column` is the column role the indicator calculates on; it is used
    when the caller passes no `column` and the input has more than one.
    `columns` must be None: it is the multi-column override.
    """
    if columns is not None:
        _reject_columns(outputs.indicator, columns)

    if column is not None and not isinstance(column, str):
        raise TypeError(f"column must be a str or None, got {type(column).__name__}")

    prepared = normalize(data, column, default_column)
    first, valid = _trim(prepared.values)
    results = _pad_all(native(valid, *params), first, prepared.values.shape[0])

    return _restore(prepared.restore, outputs.cased(prepared.names), results)


def _pad_all(result: NativeResult, first: int, length: int) -> list[Float64Array]:
    """`_pad` applied to every output of a native result."""
    if isinstance(result, np.ndarray):
        return [_pad(result, first, length)]

    return [_pad(values, first, length) for values in result]


def _restore(restore: Restore, names: tuple[str, ...], results: list[Float64Array]) -> Any:
    """Pairs each output with its name and rebuilds the caller's container."""
    named: Outputs = tuple(zip(names, results, strict=True))
    return restore(named)


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
    params: tuple[int, ...],
    column: object,
    default_column: str,
    columns: object = None,
) -> Any:
    """Runs one indicator over many datasets and returns results in the same shape.

    `params` and `column` are shared by every dataset, so an invalid one raises
    (the indicator validates `params` before calling). A dataset that is
    malformed or fails to calculate is not raised: its exception is returned in
    its place so the other datasets still complete.
    """
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
            outcomes[position] = _restore(prepared.restore, outputs.cased(prepared.names), padded)

    if failed:
        _log_failures(label, outcomes, keys, failed)

    return outcomes if keys is None else dict(zip(keys, outcomes, strict=True))


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
    params: tuple[int, ...],
    columns: object,
    slots: Sequence[Slot],
    column: object = None,
) -> Any:
    """Runs one multi-column indicator on validated `params` and restores the container.

    `slots` are the indicator's inputs in the order the native function takes
    them. `column` must be None: it is the single-column override.
    """
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
    return _restore(prepared.restore, outputs.cased(prepared.names), results)


def run_columns_batch(
    native: NativeColumnsBatchIndicator,
    outputs: OutputNames,
    datasets: object,
    params: tuple[int, ...],
    columns: object,
    slots: Sequence[Slot],
    column: object = None,
) -> Any:
    """`run_batch` for a multi-column indicator; `columns` is shared by every dataset."""
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
            outcomes[position] = _restore(prepared.restore, outputs.cased(prepared.names), padded)

    if failed:
        _log_failures(label, outcomes, keys, failed)

    return outcomes if keys is None else dict(zip(keys, outcomes, strict=True))


def _trim_columns(prepared: PreparedColumns) -> tuple[int, list[Float64Array]]:
    """Skips the longest leading NaN run across the columns, and checks row order.

    Every column is cut at the same row, so chained outputs (each with its own
    warm-up) stay aligned. Rows are then checked against `ORDERED_ROLES` (high
    not below low), naming the columns and the row in the caller's data. Values
    themselves are left to Rust, which rejects any non-finite or too-large one;
    `_value_error` then explains that error by column.
    """
    first = max(_leading_nan_count(values) for values in prepared.values)
    rows = prepared.values[0].shape[0]

    if first == rows:
        raise ValueError("input contains no complete row; every row has a NaN or missing value")

    valid = [values[first:] for values in prepared.values] if first else list(prepared.values)

    for upper, lower in ORDERED_ROLES:
        if upper in prepared.roles and lower in prepared.roles:
            high = valid[prepared.roles.index(upper)]
            low = valid[prepared.roles.index(lower)]

            # NaN compares false, so it is left for the value check.
            if (high < low).any():
                row = int(np.flatnonzero(high < low)[0])
                raise ValueError(
                    f"column {prepared.labels[prepared.roles.index(upper)]!r} ({upper}) is below "
                    f"column {prepared.labels[prepared.roles.index(lower)]!r} ({lower}) at index "
                    f"{first + row} ({float(high[row])} < {float(low[row])}); "
                    f"{upper} must be at least {lower} on every row"
                )

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
