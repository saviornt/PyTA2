"""Internal types shared by the Python API layer."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

type Float64Array = NDArray[np.float64]

#: Rebuilds the caller's container from an indicator's output names and results,
#: two equal-length sequences in its documented output order.
type Restore = Callable[[Sequence[str], Sequence[Float64Array]], Any]

# `Prepared` and `PreparedColumns` are built on every call and never changed
# afterwards, but are not frozen: a frozen dataclass sets each field through
# `object.__setattr__`, which measured ~80 ns per field per instance (a dict of
# arrays builds two `Prepared`), against ~25 ns for a plain slot.


@dataclass(slots=True)
class Prepared:
    """One normalized series plus the means of returning the caller's container.

    `names` holds the input column name the series came from (the picked column
    of a DataFrame, dict or JSON, or a named Series), or is empty for unnamed
    input; output names take their casing from it. `index` is the input's
    pandas index (of a Series, a DataFrame, or a dict's Series column), or None
    when it has none; only `output=` targets with names use it (`_export`).
    """

    values: Float64Array
    restore: Restore
    names: tuple[object, ...] = ()
    index: Any = None


@dataclass(slots=True)
class PreparedColumns:
    """A multi-column indicator's input, one series per slot in slot order.

    `labels` name each series as error messages should: the caller's column
    name, or its position for unnamed input. `roles` are the roles the series
    were matched to. `names` are the caller's column names as `str` (the
    same tuple as `labels`), or empty for unnamed input (2-D arrays, tuples
    of arrays); output names take their casing from them. `index` is the
    input's pandas index (a DataFrame's, the shared one of a list of Series, or
    a dict's first column when it is a Series), or None when it has none.
    """

    values: tuple[Float64Array, ...]
    labels: tuple[str, ...]
    roles: tuple[str, ...]
    restore: Restore
    names: tuple[str, ...] = ()
    index: Any = None
