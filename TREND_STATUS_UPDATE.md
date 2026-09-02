# Trend status UI update

The Trend card and scanner now use plain-language status values:

- `UPTREND` when the internal bullish trend template passes.
- `NO TREND` when it does not pass.

The numerical Trend Score is preserved for context. The underlying `trend_template` calculation is unchanged.

The screener preset previously labeled `Trend Pass` is now `Uptrend`.
