import pandas as pd
import numpy as np

from quick_pick import build_quick_pick


def frame(price=454, ma20=445, prev_close=450, prev_ma20=444, atr=10, vol=1.8, prevhigh=456, high_peak=None):
    n=40
    close=np.linspace(price*0.94, price, n)
    high=close+atr*0.4
    low=close-atr*0.4
    if high_peak is not None:
        high[-10]=high_peak
    df=pd.DataFrame({
        'Open': close-1, 'High': high, 'Low': low, 'Close': close, 'Volume': 1_000_000,
        'ATR14': atr, 'MA20': ma20, 'MA50': ma20*0.96, 'MA200': ma20*0.82,
        'RSI14': 58.0, 'MACD': 2.0, 'MACD_signal': 1.0,
        'Volume_ratio': 1.0, 'close_location': 0.72,
        'PrevHigh20': prevhigh, 'StochRSI_K': 55.0, 'StochRSI_D': 50.0,
    })
    df.loc[n-2,'Close']=prev_close
    df.loc[n-2,'MA20']=prev_ma20
    df.loc[n-2,'StochRSI_K']=42.0
    df.loc[n-2,'StochRSI_D']=46.0
    df.loc[n-1,'Close']=price
    df.loc[n-1,'High']=price+4
    df.loc[n-1,'Low']=price-4
    df.loc[n-1,'MA20']=ma20
    df.loc[n-1,'Volume_ratio']=vol
    return df


def common(price, trigger, stop, tp1, tp2, levels):
    technical={
        'trade_quality': 84, 'action':'BUY CANDIDATE',
        'structure':{'label':'Bullish'}, 'phase':{'label':'Pre-Breakout'},
        'momentum':{'label':'Improving'},
    }
    context={
        'score':82, 'label':'Supportive',
        'relative_strength':{'score':88,'label':'Outperforming'},
        'combined_relative_strength':{'score':90,'label':'Outperforming'},
        'volume_flow':{'label':'Accumulation'},
    }
    trade={
        'breakout_trigger':trigger, 'stop_loss':stop, 'tp1':tp1, 'tp2':tp2,
        'level_engine':{'all_levels':levels},
    }
    entry={'nearest_supply':None,'nearest_demand':None}
    timing={'status':'WAIT BREAKOUT'}
    return technical,context,trade,entry,timing


def test_pivot_breakout_dewa_style():
    df=frame(price=454, ma20=440, prev_close=450, prev_ma20=439, atr=9, vol=1.9, prevhigh=456)
    levels=[
        {'center':456,'score':45,'touches':4,'high_touches':4},
        {'center':480,'score':34,'touches':3,'high_touches':3},
        {'center':490,'score':48,'touches':4,'high_touches':4},
        {'center':500,'score':36,'touches':3,'high_touches':3},
        {'center':520,'score':40,'touches':3,'high_touches':3},
    ]
    technical,context,trade,entry,timing=common(454,456,440,480,500,levels)
    pattern={'label':'Darvas Box','score':86,'pivot':456}
    q=build_quick_pick(df,technical,context,pattern,trade,entry,timing)
    assert q['setup']=='PIVOT BREAKOUT', q
    assert q['entry_low'] <= 454 <= q['entry_high']
    assert q['trigger']==456
    assert q['major_confirmation']==490
    assert q['tp3']>=520
    assert q['rr_tp2']>=2.0
    assert q['status'] in {'READY','NEAR ENTRY'}


def test_ma20_reclaim_cdia_style():
    df=frame(price=685, ma20=680, prev_close=675, prev_ma20=678, atr=15, vol=1.45, prevhigh=735)
    levels=[
        {'center':735,'score':40,'touches':3,'high_touches':3},
        {'center':760,'score':42,'touches':3,'high_touches':3},
        {'center':800,'score':35,'touches':3,'high_touches':3},
    ]
    technical,context,trade,entry,timing=common(685,735,665,735,760,levels)
    pattern={'label':'None','score':55,'pivot':None}
    q=build_quick_pick(df,technical,context,pattern,trade,entry,timing)
    assert q['setup']=='MA20 RECLAIM', q
    assert q['entry_low'] <= 680 <= q['entry_high']
    assert q['stoch_rsi'] in {'BULLISH CROSS','BULLISH'}
    assert q['stop'] < q['entry_low']
    assert q['status'] in {'READY','NEAR ENTRY','WAIT RETEST'}


def test_base_retest_ptro_style():
    df=frame(price=5210, ma20=5150, prev_close=5250, prev_ma20=5145, atr=110, vol=1.1, prevhigh=5500, high_peak=5600)
    levels=[
        {'center':5200,'score':50,'touches':4,'high_touches':3},
        {'center':5500,'score':40,'touches':3,'high_touches':3},
        {'center':5800,'score':42,'touches':3,'high_touches':3},
        {'center':6000,'score':45,'touches':3,'high_touches':3},
    ]
    technical,context,trade,entry,timing=common(5210,5200,5000,5500,5800,levels)
    technical['phase']={'label':'Pullback in Uptrend'}
    pattern={'label':'Bull Flag','score':88,'pivot':5200}
    q=build_quick_pick(df,technical,context,pattern,trade,entry,timing)
    assert q['setup']=='BASE RETEST', q
    assert q['entry_low'] <= 5210 <= q['entry_high']
    assert q['stop'] <= 5000
    assert q['tp1']==5500 and q['tp2']==5800
    assert q['tp3']>=6000


def test_overextended_not_eligible():
    df=frame(price=540, ma20=470, prev_close=530, prev_ma20=468, atr=10, vol=2.0, prevhigh=500)
    technical,context,trade,entry,timing=common(540,500,475,560,600,[])
    technical['phase']={'label':'Overextended'}
    pattern={'label':'Darvas Box','score':90,'pivot':500}
    q=build_quick_pick(df,technical,context,pattern,trade,entry,timing)
    assert q['status'] in {'TOO EXTENDED','NO SETUP'}
    assert not q['eligible']


def test_quick_pick_idx_cross_band_rounding():
    df=frame(price=505, ma20=490, prev_close=500, prev_ma20=488, atr=10, vol=1.7, prevhigh=506)
    levels=[
        {'center':506,'score':45,'touches':4,'high_touches':4},
        {'center':540,'score':40,'touches':3,'high_touches':3},
        {'center':560,'score':42,'touches':3,'high_touches':3},
    ]
    technical,context,trade,entry,timing=common(505,510,480,540,560,levels)
    pattern={'label':'Flat Base','score':84,'pivot':506}
    q=build_quick_pick(df,technical,context,pattern,trade,entry,timing)
    assert q['setup']=='PIVOT BREAKOUT', q
    assert q['trigger']==510, q
    assert q['entry_high']==505, q  # anticipatory entry stays on a valid Rp5 tick below the trigger
    assert q['entry_low'] % 5 == 0 and q['entry_high'] % 5 == 0 and q['stop'] % 2 == 0, q


if __name__=='__main__':
    tests=[test_pivot_breakout_dewa_style,test_ma20_reclaim_cdia_style,test_base_retest_ptro_style,test_overextended_not_eligible,test_quick_pick_idx_cross_band_rounding]
    for t in tests:
        t(); print('PASS',t.__name__)
    print(f'{len(tests)}/{len(tests)} PASS')
