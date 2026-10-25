import pyta

prices = [10.0, 11.0, 12.0, 13.0, 12.0, 14.0]

sma = pyta.sma(prices, period=3)
rsi = pyta.rsi(prices, period=3)

assert len(sma) == len(prices), "SMA output length mismatch"
assert len(rsi) == len(prices), "RSI output length mismatch"

assert sma[:2] == [None, None], "SMA warm-up alignment is incorrect"
assert rsi[:3] == [None, None, None], "RSI warm-up alignment is incorrect"

assert all(value is None or isinstance(value, float) for value in sma)
assert all(value is None or isinstance(value, float) for value in rsi)

print(f"SMA: {sma}")
print(f"RSI: {rsi}")

try:
    pyta.sma(prices, period=0)
except ValueError:
    print("Invalid-period validation: passed")
else:
    raise AssertionError("SMA should reject period=0")

print("Python API smoke tests passed.")