"""Output names: an indicator's declared names, cased to match the input's columns.

Each indicator declares its output names in lower case, in documented order
(`("macd", "macd_signal", "macd_hist")`), and which name parts are
abbreviations (`macd`). The casing of the input column names the call used
picks the form returned:

- lower case (`close`) gives `macd_signal`;
- upper case (`CLOSE`) gives `MACD_SIGNAL`;
- title case (`Close`, `Adj Close`, as yfinance) gives abbreviations upper and
  words title: `MACD_Signal`;
- mixed casing, columns that disagree, or no name at all give lower case.

The separator is always `_`.
"""

import functools
import re
from collections.abc import Sequence
from typing import Literal

type Casing = Literal["lower", "upper", "title"]

_WORDS = re.compile(r"[^\W_]+")


def _name_casing(name: object) -> Casing | None:
    """The casing of one column name, or None when it is mixed."""
    text = str(name)

    if not any(char.isupper() for char in text):
        return "lower"
    if not any(char.islower() for char in text):
        return "upper"

    words = _WORDS.findall(text)
    if all(word[0].isupper() and not any(c.isupper() for c in word[1:]) for word in words):
        return "title"

    return None


@functools.lru_cache(maxsize=1024)
def casing(names: tuple[object, ...]) -> Casing:
    """The casing every name shares, or lower case when they disagree or there are none.

    Cached: the same column names come back on every call.
    """
    found: set[Casing | None] = {_name_casing(name) for name in names}

    if len(found) == 1:
        only = found.pop()
        if only is not None:
            return only

    return "lower"


class OutputNames:
    """An indicator's output names in every casing, built once per indicator.

    `names` are lower case with `_` between parts, in documented order;
    `abbreviations` are the parts written upper case in title-case output.
    """

    __slots__ = ("indicator", "lower", "title", "upper")

    def __init__(self, indicator: str, names: Sequence[str], abbreviations: Sequence[str]) -> None:
        if not names or any(name != name.lower() for name in names):
            raise ValueError(f"{indicator}: output names must be lower case, got {list(names)}")

        short = frozenset(abbreviations)
        self.indicator = indicator
        self.lower = tuple(names)
        self.upper = tuple(name.upper() for name in names)
        self.title = tuple(
            "_".join(part.upper() if part in short else part.title() for part in name.split("_"))
            for name in names
        )

    def __len__(self) -> int:
        return len(self.lower)

    def __repr__(self) -> str:
        return f"OutputNames({self.indicator!r}, {list(self.lower)})"

    def cased(self, names: tuple[object, ...]) -> tuple[str, ...]:
        """The output names cased like the input column `names` (empty for unnamed input)."""
        if not names:
            return self.lower

        match casing(names):
            case "upper":
                return self.upper
            case "title":
                return self.title
            case "lower":
                return self.lower
