import numpy as np
import pandas as pd
from supply_demand import discover_supply_demand
from entry_engine import build_entry_plan

n=120
idx=pd.date_range('2026-01-01',periods=n,freq='B')
close=np.linspace(430,500,n)
# create a compact base then strong rally near the end
close[82:86]=[500,502,501,503]
close[86:92]=[515,530,545,555,560,565]
close[92:]=np.linspace(562,590,n-92)
open_=close.copy()
high=close+5
low=close-5
# tighter base zone
open_[82:86]=[501,501,502,502]
high[82:86]=[505,504,505,506]
low[82:86]=[496,497,498,499]
vol=np.full(n,10_000_000.0)
vol[86:92]=20_000_000

df=pd.DataFrame({'Open':open_,'High':high,'Low':low,'Close':close,'Volume':vol},index=idx)
df['ATR14']=8.0
df['Volume_ratio']=df['Volume']/10_000_000.0
df['EMA20']=df['Close'].ewm(span=20,adjust=False).mean()
df['EMA50']=df['Close'].ewm(span=50,adjust=False).mean()
df['MA20']=df['Close'].rolling(20,min_periods=1).mean()
df['MA50']=df['Close'].rolling(50,min_periods=1).mean()
df['MA200']=df['Close'].expanding().mean()

sd=discover_supply_demand(df)
assert sd['demand'], 'Expected demand zone'

tp={
 'price':590,'tp2':650,'aggressive_entry_low':575,'aggressive_entry_high':585,
 'stop_loss':555,'conservative_entry_low':605,'conservative_entry_high':610,
 'breakout_trigger':605,
}
technical={'trade_quality':84,'structure':{'label':'Bullish'},'momentum':{'label':'Healthy'},'phase':{'label':'Pullback in Uptrend'}}
context={'score':78,'relative_strength':{'score':91,'label':'Outperforming'}}
pattern={'score':88,'label':'Flat Base','pivot':605}
e=build_entry_plan(df,technical,context,pattern,tp)
assert e['best'] is not None
assert e['best']['entry_low'] <= e['best']['entry'] <= e['best']['entry_high']
assert e['best']['stop'] < e['best']['entry']
assert e['best']['score'] <= 100
print('SUPPLY_DEMAND_ENTRY_PASS')
print('Demand:',sd['nearest_demand']['zone_low_exec'],sd['nearest_demand']['zone_high_exec'],sd['nearest_demand']['score'])
print('Best:',e['best'])
