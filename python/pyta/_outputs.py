"""Output names: an indicator's declared names, cased to match the input's columns.

Each indicator declares its output names in lower case, in documented order
(`("macd", "macd_signal", "macd_hist")`), and which name parts are
abbreviations (`macd`). The casing of the input column names the call used
picks the form returned:

- lower case (`close`) gives `macd_signal`;
- upper case (`CLOSE`) gives `MACD_SIGNAL`;
- title case gives abbreviations upper and words title: `MACD_Signal`. A name
  is title case when it has a lower-case letter and every word is either a
  capital then no other capitals (`Close`, `Adj Close`, as yfinance) or all
  capitals (`SPY Close`, and PyTA's own `MACD_Signal`, so outputs chain);
- mixed casing, columns that disagree, or no name at all give lower case.

The separator is always `_`.
"""

import re
from collections.abc import Sequence
from typing import Literal

type Casing = Literal["lower", "upper", "title"]

_WORDS = re.compile(r"[^\W_]+")

#: Distinct input names remembered per indicator before the memo is cleared.
_MEMO_SIZE = 1024


def _title_word(word: str) -> bool:
    """A capital followed by no other capital (`Close`), or all capitals (`MACD`)."""
    if not word[0].isupper():
        return False

    rest = word[1:]
    return not any(c.isupper() for c in rest) or not any(c.islower() for c in rest)


def _name_casing(text: str) -> Casing | None:
    """The casing of one column name, or None when it is mixed."""
    if not any(char.isupper() for char in text):
        return "lower"
    if not any(char.islower() for char in text):
        return "upper"
    if all(_title_word(word) for word in _WORDS.findall(text)):
        return "title"

    return None


def casing(names: Sequence[object]) -> Casing:
    """The casing every name shares, or lower case when they disagree or there are none.

    A name's casing is that of its `str()`.
    """
    found: set[Casing | None] = {_name_casing(str(name)) for name in names}

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

    __slots__ = ("_memo", "indicator", "lower", "title", "upper")

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
        # Input names (as strings) to the cased outputs: the same columns come
        # back on every call. Keyed on strings, since `True == 1` would collide.
        self._memo: dict[str | tuple[str, ...], tuple[str, ...]] = {}

    def __len__(self) -> int:
        return len(self.lower)

    def __repr__(self) -> str:
        return f"OutputNames({self.indicator!r}, {list(self.lower)})"

    def cased(self, names: tuple[object, ...]) -> tuple[str, ...]:
        """The output names cased like the input column `names` (empty for unnamed input)."""
        if not names:
            return self.lower

        if len(names) == 1:
            name = names[0]
            key: str | tuple[str, ...] = name if type(name) is str else str(name)
        else:
            key = tuple(map(str, names))

        found = self._memo.get(key)
        return found if found is not None else self._remember(key, names)

    def cased_text(self, names: tuple[str, ...]) -> tuple[str, ...]:
        """`cased` for names that are already `str`, as a multi-column input's are.

        Skips converting each name, which a 100-row CCI call measured at ~0.15 µs.
        """
        if not names:
            return self.lower

        key: str | tuple[str, ...] = names[0] if len(names) == 1 else names
        found = self._memo.get(key)
        return found if found is not None else self._remember(key, names)

    def _remember(self, key: str | tuple[str, ...], names: tuple[object, ...]) -> tuple[str, ...]:
        """Works out and memoizes the outputs for input `names` not seen yet."""
        found = self._form(casing(names))
        if len(self._memo) >= _MEMO_SIZE:
            self._memo.clear()
        self._memo[key] = found
        return found

    def _form(self, casing: Casing) -> tuple[str, ...]:
        match casing:
            case "upper":
                return self.upper
            case "title":
                return self.title
            case "lower":
                return self.lower
