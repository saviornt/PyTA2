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


@dataclass(frozen=True, slots=True)
class Prepared:
    """One normalized series plus the means of returning the caller's container.

    `names` holds the input column name the series came from (the picked column
    of a DataFrame, dict or JSON, or a named Series), or is empty for unnamed
    input; output names take their casing from it.
    """

    values: Float64Array
    restore: Restore
    names: tuple[object, ...] = ()


@dataclass(frozen=True, slots=True)
class PreparedColumns:
    """A multi-column indicator's input, one series per slot in slot order.

    `labels` name each series as error messages should: the caller's column
    name, or its position for unnamed input. `roles` are the roles the series
    were matched to. `names` are the caller's column names as `str` (the
    same tuple as `labels`), or empty for unnamed input (2-D arrays, tuples
    of arrays); output names take their casing from them.
    """

    values: tuple[Float64Array, ...]
    labels: tuple[str, ...]
    roles: tuple[str, ...]
    restore: Restore
    names: tuple[str, ...] = ()
