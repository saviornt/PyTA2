# Indicator spec template

Fill this in and present it to the user before writing any code. Keep it to one screen; link sources instead of pasting them.

TA-Lib source: `https://raw.githubusercontent.com/TA-Lib/ta-lib/main/src/ta_func/ta_<NAME>.c` (upper-case name, for example `ta_EMA.c`). If the path has moved, find the file in the `TA-Lib/ta-lib` repository. The `Lookback` function in that file gives the warm-up length; the `optInTimePeriod` comments give the default and range.

```markdown
## <NAME>: <Full name>

- **Category:** <trend | momentum | volatility | volume | ...> (crate `pyta-<category>`; new crate: yes/no)
- **TA-Lib function:** `TA_<NAME>` (<link to the source file>)

### Formula
<The calculation as TA-Lib does it, step by step, including seeding/initialization.>
<Difference from the original definition, if any, and which we follow (TA-Lib's).>

### Parameters
| Name | Type | Default | Range | Notes |
|---|---|---|---|---|
| period | int | <TA-Lib default, or required> | 1 to 2**31 - 1 | |

### Input and output
- **Input:** <one series; default column `close` | other role | several roles: slots, accepted roles, order for unnamed input>
- **Output:** <one series named `<name>` | several, bare names in documented order (`<name>`, `<name>_<part>`), which parts are abbreviations, and each one's warm-up>
- **Warm-up:** first <k> values are NaN (TA-Lib lookback = <k>); needs at least <k + 1> values.
- **Complexity:** O(n) | O(n · period) (affects the cost estimate)

### Edge cases
| Case | Result |
|---|---|
| flat series | <value> |
| <zero denominator, period = 1, period = length, ...> | <value or error> |

### Errors
| Condition | `PytaError` | Python |
|---|---|---|
| period = 0 | `InvalidPeriod` | ValueError (Pydantic rejects it first) |
| too little data | `InsufficientData { required: <k + 1>, length }` | ValueError |

### Reference values
<Source with full citation (book, page/table, or URL)>, stored as `tests/fixtures/<name>_<source>.<csv|json>`; <n> input rows, <m> checked outputs, precision <decimals>.

### Contract
<"Fits the current contract (one Series, one period, one output)." or the extension design from extending-contracts.md: what changes in pyta-core, pyta-engine, pyta-python and the Python layer, and why it is generic.>
```
