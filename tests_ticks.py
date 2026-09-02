from idx_ticks import (
    tick_size, floor_to_tick, ceil_to_tick, nearest_to_tick,
    next_tick_above, previous_tick_below, conservative_floor_to_tick
)


def run():
    tests = []

    expected = {
        199: 1, 200: 2, 499: 2, 500: 5,
        1999: 5, 2000: 10, 4999: 10, 5000: 25,
    }
    for p, t in expected.items():
        assert tick_size(p) == t, (p, tick_size(p), t)
    tests.append("tick-size boundaries")

    # Normal in-band rounding.
    assert floor_to_tick(476.75) == 476      # Rp2 band
    assert ceil_to_tick(476.75) == 478
    assert floor_to_tick(540.49) == 540      # Rp5 band
    assert ceil_to_tick(540.49) == 545
    assert nearest_to_tick(540.49) == 540
    tests.append("in-band level-aware rounding")

    # Critical ERAA-style crossing: current/reference can be below 500,
    # but a forward trigger above 500 MUST use Rp5 level grid.
    assert tick_size(506) == 5
    assert floor_to_tick(506, 496) == 505
    assert ceil_to_tick(506, 496) == 510
    assert nearest_to_tick(506, 496) == 505
    assert ceil_to_tick(501, 498) == 505
    assert ceil_to_tick(499.1, 498) == 500
    tests.append("ERAA 500-boundary regression")

    # Other band crossings.
    assert floor_to_tick(2006) == 2000
    assert ceil_to_tick(2006) == 2010
    assert floor_to_tick(5013) == 5000
    assert ceil_to_tick(5013) == 5025
    tests.append("2000/5000 boundary regression")

    # Stop/target directional behavior.
    assert conservative_floor_to_tick(914.95) == 915
    assert conservative_floor_to_tick(913.10) == 910
    assert floor_to_tick(3216.33) == 3210
    assert ceil_to_tick(6820.47) == 6825
    tests.append("directional execution rounding")

    # Strict tick helpers.
    assert next_tick_above(500) == 505
    assert next_tick_above(1999) == 2000
    assert previous_tick_below(500) == 498
    assert previous_tick_below(2000) == 1995
    tests.append("strict cross-band tick helpers")

    print(f"PASS: {len(tests)}/{len(tests)}")
    for t in tests:
        print(" -", t)


if __name__ == "__main__":
    run()
