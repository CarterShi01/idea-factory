"""漏斗(召回→粗排→精排→打散)核心逻辑单测。见 docs/design/idea-funnel.md。"""

from datetime import date

from idea_core.factors import founder_fit
from idea_core.models import IdeaCandidate, bucket_of
from idea_eval.evaluate import REVIEW, Evaluation, diversify_select
from idea_gen import ranks


def _cand(cid, source, title, target_user="用户", solution=""):
    return IdeaCandidate(
        id=cid, signal_id="s", source=source, title=title, pain="痛",
        solution=solution, target_user=target_user, observed_on="2026-07-01",
    )


def test_bucket_of_splits_en_zh():
    assert bucket_of("external_event") == "en"
    assert bucket_of("pain_persona") == "zh"
    assert bucket_of("brain_inbox") == "zh"


def test_founder_fit_rewards_monopoly_penalizes_antifit():
    mono = founder_fit(_cand("a", "pain_persona", "蒙语政企客服", "内蒙古蒙语政企", "母语 家人 内蒙古"))
    antifit = founder_fit(_cand("b", "external_event", "硬件自研平台", "工厂", "硬件自研 大团队 融资 投放"))
    generic = founder_fit(_cand("c", "external_event", "通用工具", "developer community", "paid ads"))
    assert mono > 0.5          # 语言区域独占 = 高分
    assert antifit < 0.15      # anti-fit 硬扣压低
    assert generic < 0.2       # 公开渠道通用货 = 低分
    assert mono > generic > antifit or mono > antifit  # 独占 >> 通用/anti-fit


def test_coarse_select_keeps_both_buckets():
    today = date(2026, 7, 1)
    cands = [_cand(f"en{i}", "external_event", f"英文工具{i}") for i in range(40)]
    cands += [_cand(f"zh{i}", "pain_persona", f"蒙语工具{i}", "内蒙古蒙语") for i in range(40)]
    scored = ranks.score(cands, today=today)
    ranked = ranks.rank(scored)
    coarse = ranks.coarse_select(ranked, k=50, en_frac=0.4)
    assert len(coarse) == 50
    buckets = {bucket_of(s.candidate.source) for s in coarse}
    assert buckets == {"en", "zh"}          # 两桶都保住,没被饿死
    en = sum(1 for s in coarse if bucket_of(s.candidate.source) == "en")
    assert 15 <= en <= 25                     # 英文桶 ~40% 配额


def test_coarse_select_returns_all_when_under_k():
    today = date(2026, 7, 1)
    cands = [_cand(f"x{i}", "pain_persona", f"工具{i}") for i in range(10)]
    ranked = ranks.rank(ranks.score(cands, today=today))
    assert len(ranks.coarse_select(ranked, k=50)) == 10


def _ev(iid, score):
    return Evaluation(idea_id=iid, title=iid, verdict=REVIEW, eval_score=score)


def test_diversify_enforces_zh_majority_quota():
    ideas, evs = {}, []
    edges = ["蒙语政企", "安全云采购", "海外硬件", "慢病随访", "蒙语教育"]
    for i in range(30):
        iid = f"zh{i}"
        ideas[iid] = {"id": iid, "source": "pain_persona", "title": f"{edges[i % 5]}{i}",
                      "pain": f"痛{i}", "target_user": edges[i % 5]}
        evs.append(_ev(iid, 90 - i * 0.1))
    for i in range(30):
        iid = f"en{i}"
        ideas[iid] = {"id": iid, "source": "external_event", "title": f"全球工具{i}",
                      "pain": f"p{i}", "target_user": "global dev"}
        evs.append(_ev(iid, 95 - i * 0.1))   # 英文分更高,但仍应被 en_max 顶住
    head = diversify_select(evs, ideas)[:20]
    en = sum(1 for e in head if ideas[e.idea_id]["source"] == "external_event")
    assert en <= 6                            # 英文硬顶 6
    assert 20 - en >= 14                       # 中文自然 ≥ 14
    # 单边上限:没有哪个创始人边超过 6
    from collections import Counter
    edge_counts = Counter(ideas[e.idea_id]["target_user"] for e in head)
    assert all(c <= 6 for c in edge_counts.values())
