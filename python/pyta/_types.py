"""Internal types shared by the Python API layer."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

type Float64Array = NDArray[np.float64]

#: An indicator's results as (name, values) pairs in its documented output order.
type Outputs = tuple[tuple[str, Float64Array], ...]

#: Rebuilds the caller's container from an indicator's named results.
type Restore = Callable[[Outputs], Any]


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
    were matched to. `names` are the caller's column names, or empty for
    unnamed input (2-D arrays, tuples of arrays); output names take their
    casing from them.
    """

    values: tuple[Float64Array, ...]
    labels: tuple[str, ...]
    roles: tuple[str, ...]
    restore: Restore
    names: tuple[object, ...] = ()
