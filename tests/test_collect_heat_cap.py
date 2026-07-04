from idea_gen.collect import _cap_english_by_heat


def _en(i):
    return {"source_name": "hn", "title": f"en{i}", "points": i}


def test_caps_english_to_top_n_by_points():
    recs = [_en(i) for i in range(30)] + [
        {"source_name": "persona", "title": "中文人群"},
        {"source_name": "brain", "title": "灵感"},
    ]
    out = _cap_english_by_heat(recs, 20)
    hn = [r for r in out if r["source_name"] == "hn"]
    assert len(hn) == 20
    assert min(r["points"] for r in hn) == 10  # 只留 points 10..29
    # 非英文源一条不少
    assert len([r for r in out if r["source_name"] != "hn"]) == 2


def test_no_cap_when_under_limit_or_disabled():
    recs = [_en(i) for i in range(5)]
    assert len(_cap_english_by_heat(recs, 20)) == 5   # 少于上限不动
    assert len(_cap_english_by_heat([_en(i) for i in range(30)], 0)) == 30  # 0=不截断
