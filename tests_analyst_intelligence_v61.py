import numpy as np
import pandas as pd
from analyst_intelligence import build_analyst_intelligence, _candle_state, _open_gap_above, _nearest_psychological_level


def base_frame(price=2230, support=2200, n=90):
    close=np.linspace(price*.88, price, n)
    df=pd.DataFrame({'Open':close-5,'High':close+10,'Low':close-10,'Close':close,'Volume':1_000_000})
    df['ATR14']=40.; df['MA20']=2180.; df['MA50']=2100.; df['MA200']=1800.; df['RSI14']=44.
    df['MACD']=2.; df['MACD_signal']=1.8; df['MACD_hist']=.2; df['Volume_ratio']=.85; df['VolumeFlow5']=.05
    df['close_location']=.58; df['PrevHigh20']=2400.; df['High20']=2450.; df['ADX14']=18.; df['StochRSI_K']=18.; df['StochRSI_D']=22.
    return df


def common(price,support,resistance,stop,tp1,tp2):
    technical={'trade_quality':78,'structure':{'label':'Bullish'},'phase':{'label':'Pullback in Uptrend'},'momentum':{'label':'Improving'},'action':'BUY CANDIDATE'}
    context={'score':70,'relative_strength':{'score':72},'combined_relative_strength':{'score':74},'sector':{'score':65},'volume_flow':{'label':'Balanced'}}
    levels=[{'center':support,'score':48,'touches':4,'high_touches':1},{'center':resistance,'score':46,'touches':4,'high_touches':4},{'center':tp2,'score':38,'touches':3,'high_touches':3}]
    trade={'support1':support,'support1_zone_low':support*.99,'resistance1':resistance,'breakout_trigger':resistance,'stop_loss':stop,'tp1':tp1,'tp2':tp2,'level_engine':{'all_levels':levels}}
    return technical,context,trade,{'nearest_supply':None,'nearest_demand':None},{'status':'WAIT RETEST','score':72}


def test_hrta_support_reversal_candidate():
    df=base_frame(2230,2200)
    # spinning-bottom-like last candle
    df.loc[df.index[-1],['Open','High','Low','Close']]=[2228,2250,2190,2230]
    technical,context,trade,entry,timing=common(2230,2200,2330,2170,2330,2430)
    ai=build_analyst_intelligence(df,technical,context,{'label':'None','score':50},trade,entry,timing,{'candidates':[]})
    assert any(c['setup']=='SUPPORT REVERSAL' for c in ai['candidates']), ai
    assert _candle_state(df)['label'] in {'SPINNING BOTTOM','NONE','HAMMER'}, _candle_state(df)


def test_pipa_base_formation_candidate():
    n=90; price=202.
    close=np.r_[np.linspace(160,198,n-15), np.array([200,202,201,203,202,204,203,202,201,202,203,202,201,202,202])]
    df=pd.DataFrame({'Open':close-1,'High':close+3,'Low':close-3,'Close':close,'Volume':800_000})
    df['ATR14']=5.; df['MA20']=196.; df['MA50']=185.; df['MA200']=160.; df['RSI14']=42.; df['MACD']=.5; df['MACD_signal']=.4; df['MACD_hist']=.1
    df['Volume_ratio']=.75; df['VolumeFlow5']=.02; df['close_location']=.55; df['PrevHigh20']=212.; df['High20']=212.; df['ADX14']=14.; df['StochRSI_K']=18.; df['StochRSI_D']=22.
    technical,context,trade,entry,timing=common(202,200,212,193,220,240)
    ai=build_analyst_intelligence(df,technical,context,{'label':'Flat Base','score':72},trade,entry,timing,{'candidates':[]})
    assert any(c['setup']=='BASE FORMATION' for c in ai['candidates']), ai
    assert _nearest_psychological_level(202)['level']==200


def test_gap_detector_finds_open_gap():
    n=30
    close=np.linspace(2000,2230,n)
    df=pd.DataFrame({'Open':close,'High':close+10,'Low':close-10,'Close':close})
    # create historical downside gap: previous low 2440, next high 2300; never fully filled
    df.loc[10,'Low']=2440; df.loc[10,'High']=2470; df.loc[10,'Close']=2450; df.loc[10,'Open']=2460
    df.loc[11,'High']=2300; df.loc[11,'Low']=2250; df.loc[11,'Close']=2280; df.loc[11,'Open']=2270
    df.loc[12:,'High']=np.minimum(df.loc[12:,'High'],2400)
    g=_open_gap_above(df)
    assert g['found'] and g['target']>=2440, g


if __name__=='__main__':
    tests=[test_hrta_support_reversal_candidate,test_pipa_base_formation_candidate,test_gap_detector_finds_open_gap]
    for t in tests:
        t(); print('PASS',t.__name__)
    print(f'{len(tests)}/{len(tests)} PASS')
