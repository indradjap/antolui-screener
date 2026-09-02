from datetime import datetime, timezone

from news_narrative import classify_item, summarize_narrative, dedupe_items

NOW = datetime(2026, 9, 1, 4, 0, tzinfo=timezone.utc)


def assert_true(name, cond):
    if not cond:
        raise AssertionError(name)
    print('PASS:', name)


def main():
    # 1) Explicit rumor must stay unconfirmed and low reliability.
    rumor = classify_item(
        'Rumor beredar: ABCD dikabarkan akan diakuisisi investor strategis',
        source='Some Market Blog', published_at='Tue, 01 Sep 2026 03:30:00 GMT', now=NOW,
    )
    assert_true('rumor classified unconfirmed', rumor.item_type == 'UNCONFIRMED RUMOR')
    assert_true('rumor reliability capped', rumor.reliability_score <= 0.38)

    # 2) Established-media positive report should be reported news and bullish.
    good = classify_item(
        'ABCD Raih Kontrak Proyek Baru, Order Book Naik',
        source='CNBC Indonesia', published_at='Tue, 01 Sep 2026 03:00:00 GMT', now=NOW,
    )
    assert_true('established media classification', good.item_type == 'REPORTED NEWS')
    assert_true('positive bias', good.bias == 'Bullish')

    # 3) Confirmed bullish news can create a small positive overlay.
    items = [
        classify_item('ABCD Raih Kontrak Proyek Baru, Order Book Naik', 'CNBC Indonesia', 'Tue, 01 Sep 2026 03:00:00 GMT', now=NOW),
        classify_item('Kontrak Baru ABCD Dongkrak Order Book Perseroan', 'Kontan', 'Tue, 01 Sep 2026 02:00:00 GMT', now=NOW),
        classify_item('ABCD Catat Laba Naik dan Guidance Membaik', 'Reuters', 'Mon, 31 Aug 2026 23:00:00 GMT', now=NOW),
    ]
    summ = summarize_narrative(items)
    assert_true('bullish summary', summ['bias'] == 'Bullish')
    assert_true('verified count positive', summ['verified_count'] >= 2)
    assert_true('confirmed overlay positive but capped', 0 < summ['ranking_overlay'] <= 5)

    # 4) Rumor-only bundle must never boost ranking.
    rum_only = summarize_narrative([
        rumor,
        classify_item('Isu ABCD akan merger kembali beredar di pasar', 'Blog Pasar', 'Tue, 01 Sep 2026 03:20:00 GMT', now=NOW),
    ])
    assert_true('rumor only no overlay', rum_only['ranking_overlay'] == 0)
    assert_true('rumor risk not low', rum_only['rumor_risk'] in {'Medium','High'})

    # 5) Negative credible catalyst produces negative overlay.
    bad = summarize_narrative([
        classify_item('ABCD Catat Rugi dan Pangkas Guidance', 'Reuters', 'Tue, 01 Sep 2026 03:00:00 GMT', now=NOW),
        classify_item('Laba ABCD Turun Tajam, Penjualan Melemah', 'Bisnis.com', 'Tue, 01 Sep 2026 02:30:00 GMT', now=NOW),
    ])
    assert_true('bearish summary', bad['bias'] == 'Bearish')
    assert_true('negative overlay', bad['ranking_overlay'] < 0)

    # 6) Dedupe similar headlines.
    dupes = dedupe_items([
        classify_item('ABCD Raih Kontrak Baru Rp1 Triliun', 'CNBC Indonesia', 'Tue, 01 Sep 2026 03:00:00 GMT', now=NOW),
        classify_item('ABCD Raih Kontrak Baru Rp1 Triliun', 'Kontan', 'Tue, 01 Sep 2026 02:50:00 GMT', now=NOW),
    ])
    assert_true('dedupe exact/similar', len(dupes) == 1)

    print('NEWS ENGINE: 6/6 PASS')


if __name__ == '__main__':
    main()
