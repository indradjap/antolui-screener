import tempfile
from pathlib import Path
import pandas as pd

from analyst_learning import setup_calibration, research_summary


def test_frequency_does_not_create_fake_edge():
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'h.csv'
        pd.DataFrame([{'setup_family':'PIVOT BREAKOUT','tp1_before_sl':'','sl_before_tp1':''} for _ in range(25)]).to_csv(p,index=False)
        c=setup_calibration('PIVOT BREAKOUT',p)
        assert c['n']==0 and c['score_adjustment']==0 and not c['active'], c


def test_calibration_activates_only_on_resolved_outcomes():
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'h.csv'
        rows=[]
        for i in range(12):
            win=i<9
            rows.append({'setup_family':'MA20 RECLAIM','tp1_before_sl':win,'tp2_before_sl':i<6,'sl_before_tp1':not win})
        pd.DataFrame(rows).to_csv(p,index=False)
        c=setup_calibration('MA20 RECLAIM',p)
        assert c['active'] and c['n']==12 and c['score_adjustment']>0, c
        s=research_summary(p)
        assert s['examples']==12 and s['resolved']==12, s


if __name__=='__main__':
    tests=[test_frequency_does_not_create_fake_edge,test_calibration_activates_only_on_resolved_outcomes]
    for t in tests:
        t(); print('PASS',t.__name__)
    print(f'{len(tests)}/{len(tests)} PASS')
