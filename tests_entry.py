import numpy as np
import pandas as pd

from indicators import add_indicators
from engine import run_engine
from market_context import build_market_context
from patterns import detect_patterns
from strategy import build_trade_plan
from entry_engine import build_entry_plan


def synthetic(n=280, seed=7):
    rng=np.random.default_rng(seed)
    close=[]; p=500.0
    for i in range(n):
        drift=0.0012
        if 205 <= i < 215: drift=-0.004
        if 215 <= i < 222: drift=-0.001
        if 222 <= i < 228: drift=0.018
        p=max(50,p*(1+drift+rng.normal(0,0.008)))
        close.append(p)
    c=np.array(close)
    o=c*(1+rng.normal(0,0.003,n)); h=np.maximum(o,c)*(1+rng.uniform(.003,.014,n)); l=np.minimum(o,c)*(1-rng.uniform(.003,.014,n))
    v=rng.integers(8_000_000,20_000_000,n).astype(float)
    v[223:229]*=2.0
    return pd.DataFrame({'Open':o,'High':h,'Low':l,'Close':c,'Volume':v},index=pd.date_range('2025-01-01',periods=n,freq='B'))

stock=add_indicators(synthetic()).dropna()
bench=add_indicators(synthetic(seed=19)).dropna()
tech=run_engine(stock)
ctx=build_market_context(stock,bench,benchmark_name='^JKSE',sector_df=None)
pat=detect_patterns(stock)
plan=build_trade_plan(stock,tech['phase']['label'])
entry=build_entry_plan(stock,tech,ctx,pat,plan)
assert entry['candidates'], 'no entry candidates'
b=entry['best']
assert b['entry_low'] <= b['entry'] <= b['entry_high']
assert b['stop'] < b['entry']
assert b['score'] >= 0 and b['score'] <= 100
for zname in ('nearest_demand','nearest_supply'):
    z=entry.get(zname)
    if z:
        assert z['zone_low_exec'] <= z['zone_high_exec']
print('ENTRY ENGINE PASS')
print(entry['status'], entry['confidence'], b['type'], b['entry_low'], b['entry'], b['entry_high'], b['score'])
