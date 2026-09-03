import numpy as np
import pandas as pd

from analyst_intelligence import build_analyst_intelligence, _trendline_support
from quick_pick import build_quick_pick


def base_frame(price=454, atr=9, ma20=440, ma50=420, n=90, vol_ratio=1.8, recent_peak=None):
    close = np.linspace(price * 0.82, price, n)
    high = close + atr * 0.42
    low = close - atr * 0.42
    if recent_peak is not None:
        high[-6] = recent_peak
        close[-6] = min(close[-6], recent_peak - atr * 0.3)
    df = pd.DataFrame({
        'Open': close - atr * .08,
        'High': high,
        'Low': low,
        'Close': close,
        'Volume': 1_000_000,
        'ATR14': atr,
        'MA20': ma20,
        'MA50': ma50,
        'MA200': ma50 * .82,
        'RSI14': 58.0,
        'MACD': 2.0,
        'MACD_signal': 1.0,
        'MACD_hist': 1.0,
        'Volume_ratio': 1.0,
        'VolumeFlow5': 0.25,
        'close_location': .72,
        'PrevHigh20': price * 1.03,
        'High20': price * 1.08,
        'StochRSI_K': 55.0,
        'StochRSI_D': 50.0,
    })
    df.loc[n-2, 'MACD'] = .8
    df.loc[n-2, 'MACD_signal'] = 1.0
    df.loc[n-2, 'MACD_hist'] = -.2
    df.loc[n-2, 'StochRSI_K'] = 38
    df.loc[n-2, 'StochRSI_D'] = 44
    df.loc[n-1, 'Close'] = price
    df.loc[n-1, 'Open'] = price - atr * .15
    df.loc[n-1, 'High'] = price + atr * .25
    df.loc[n-1, 'Low'] = price - atr * .45
    df.loc[n-1, 'Volume_ratio'] = vol_ratio
    return df


def common(price, support, trigger, stop, tp1, tp2, levels, phase='Pullback in Uptrend'):
    technical = {
        'trade_quality': 82,
        'structure': {'label': 'Bullish'},
        'phase': {'label': phase},
        'momentum': {'label': 'Improving'},
        'action': 'BUY CANDIDATE',
    }
    context = {
        'score': 78,
        'relative_strength': {'score': 84, 'label': 'Outperforming'},
        'combined_relative_strength': {'score': 87, 'label': 'Outperforming'},
        'sector': {'score': 72, 'label': 'Supportive'},
        'volume_flow': {'label': 'Accumulation'},
    }
    trade = {
        'support1': support,
        'support1_zone_low': support * .99,
        'resistance1': trigger,
        'breakout_trigger': trigger,
        'stop_loss': stop,
        'tp1': tp1,
        'tp2': tp2,
        'level_engine': {'all_levels': levels},
    }
    entry = {'nearest_supply': None, 'nearest_demand': None}
    timing = {'status': 'WAIT RETEST', 'score': 76}
    return technical, context, trade, entry, timing


def test_dewa_breakout_prefers_breakout_logic():
    df = base_frame(price=454, atr=9, ma20=438, ma50=420, vol_ratio=1.95)
    df['PrevHigh20'] = 456
    levels = [
        {'center':456,'score':48,'touches':4,'high_touches':4},
        {'center':480,'score':32,'touches':3,'high_touches':3},
        {'center':490,'score':50,'touches':4,'high_touches':4},
        {'center':500,'score':36,'touches':3,'high_touches':3},
        {'center':520,'score':40,'touches':3,'high_touches':3},
    ]
    technical,context,trade,entry,timing = common(454, 440, 456, 440, 480, 500, levels, phase='Pre-Breakout')
    pattern = {'label':'Darvas Box','score':88,'pivot':456}
    q = build_quick_pick(df,technical,context,pattern,trade,entry,timing)
    ai = build_analyst_intelligence(df,technical,context,pattern,trade,entry,timing,q)
    assert ai['setup'] == 'PIVOT BREAKOUT', ai
    assert ai['major_confirmation'] in {480, 490}, ai
    assert ai['analyst_score'] >= 65, ai
    assert ai['conviction'] >= 60, ai


def test_ammn_support_hold_logic():
    df = base_frame(price=4360, atr=95, ma20=4100, ma50=3950, vol_ratio=.95)
    df['High20'] = 4750
    # Positive MACD but not necessarily a fresh cross.
    df.loc[df.index[-2], ['MACD','MACD_signal']] = [3.2, 2.8]
    df.loc[df.index[-1], ['MACD','MACD_signal']] = [3.4, 3.0]
    levels = [
        {'center':4300,'score':48,'touches':4,'high_touches':1},
        {'center':4520,'score':46,'touches':4,'high_touches':4},
        {'center':4700,'score':35,'touches':3,'high_touches':3},
        {'center':5000,'score':40,'touches':3,'high_touches':3},
    ]
    technical,context,trade,entry,timing = common(4360,4300,4520,4200,4700,5000,levels)
    pattern={'label':'None','score':52,'pivot':None}
    q={'candidates':[], 'setup':'NONE'}
    ai=build_analyst_intelligence(df,technical,context,pattern,trade,entry,timing,q)
    assert ai['setup'] == 'SUPPORT HOLD REBOUND', ai
    assert ai['entry_style'] == 'EARLY', ai
    assert ai['major_confirmation'] == 4520, ai
    assert ai['macd']['positive'], ai


def test_buva_pullback_pivot_hold_logic():
    df = base_frame(price=752, atr=18, ma20=730, ma50=690, vol_ratio=.85, recent_peak=805)
    df['High20'] = 805
    levels = [
        {'center':750,'score':52,'touches':5,'high_touches':2},
        {'center':800,'score':50,'touches':4,'high_touches':4},
        {'center':840,'score':38,'touches':3,'high_touches':3},
    ]
    technical,context,trade,entry,timing = common(752,750,800,720,795,840,levels)
    pattern={'label':'None','score':55,'pivot':None}
    q={'candidates':[], 'setup':'NONE'}
    ai=build_analyst_intelligence(df,technical,context,pattern,trade,entry,timing,q)
    assert ai['setup'] in {'PULLBACK PIVOT HOLD','SUPPORT HOLD REBOUND'}, ai
    # If both are valid, pivot-hold should usually win due to recent resistance test.
    assert any(c['setup']=='PULLBACK PIVOT HOLD' for c in ai['candidates']), ai
    assert ai['macd']['label'] in {'GOLDEN CROSS','POSITIVE + BULLISH','POSITIVE AREA'}, ai


def test_trendline_detector_and_mbma_candidate():
    n=90
    base=np.linspace(430,525,n)
    wave=10*np.sin(np.linspace(0,8*np.pi,n))
    close=base+wave
    high=close+7
    low=close-7
    df=pd.DataFrame({'Open':close-2,'High':high,'Low':low,'Close':close,'Volume':1_000_000})
    df['ATR14']=12.0; df['MA20']=500.0; df['MA50']=475.0; df['MA200']=420.0
    df['RSI14']=44.0; df['MACD']=2.5; df['MACD_signal']=2.0; df['MACD_hist']=.5
    df['Volume_ratio']=.8; df['VolumeFlow5']=.05; df['close_location']=.65
    df['PrevHigh20']=560; df['High20']=570; df['StochRSI_K']=18.; df['StochRSI_D']=22.
    df.loc[n-2,'MACD_hist']=.35
    # Put last close just above the fitted rising support region.
    tl0=_trendline_support(df)
    if tl0.get('support'):
        px=float(tl0['support'])*1.01
        df.loc[n-1,'Close']=px; df.loc[n-1,'Open']=px-2; df.loc[n-1,'High']=px+6; df.loc[n-1,'Low']=px-5
    tl=_trendline_support(df)
    assert tl['score'] >= 45, tl
    levels=[
        {'center':560,'score':40,'touches':3,'high_touches':3},
        {'center':585,'score':40,'touches':3,'high_touches':3},
        {'center':615,'score':40,'touches':3,'high_touches':3},
    ]
    price=float(df.iloc[-1]['Close'])
    technical,context,trade,entry,timing=common(price,470,560,510,560,585,levels)
    pattern={'label':'None','score':50,'pivot':None}
    q={'candidates':[], 'setup':'NONE'}
    ai=build_analyst_intelligence(df,technical,context,pattern,trade,entry,timing,q)
    if tl.get('valid'):
        assert any(c['setup']=='TRENDLINE SUPPORT REBOUND' for c in ai['candidates']), ai


def test_edge_layer_can_cap_bad_rr():
    df=base_frame(price=1000,atr=25,ma20=960,ma50=900,vol_ratio=1.6)
    levels=[{'center':1010,'score':45,'touches':4,'high_touches':4},{'center':1020,'score':35,'touches':3,'high_touches':3}]
    technical,context,trade,entry,timing=common(1000,970,1010,900,1015,1020,levels,phase='Pre-Breakout')
    pattern={'label':'Flat Base','score':90,'pivot':1010}
    q=build_quick_pick(df,technical,context,pattern,trade,entry,timing)
    ai=build_analyst_intelligence(df,technical,context,pattern,trade,entry,timing,q)
    # Poor RR should not be allowed to masquerade as high-conviction just because setup score is high.
    if ai['rr_tp2'] < 1.5:
        assert ai['conviction'] <= 58.0, ai
        assert not ai['eligible'], ai


if __name__ == '__main__':
    tests=[
        test_dewa_breakout_prefers_breakout_logic,
        test_ammn_support_hold_logic,
        test_buva_pullback_pivot_hold_logic,
        test_trendline_detector_and_mbma_candidate,
        test_edge_layer_can_cap_bad_rr,
    ]
    for t in tests:
        t(); print('PASS', t.__name__)
    print(f'{len(tests)}/{len(tests)} PASS')
