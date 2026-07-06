from datetime import date

from idea_factory import pipeline
from idea_factory.contract import artifacts
from idea_factory.contract.models import ScoredCandidate

REPO_DATA = "data"
REF_DATE = date(2026, 6, 13)


def _run_gen(tmp_path, **kw):
    """跑便宜半场(recall→rank),返回 (RunResult, 粗排池 ScoredCandidate 列表)。"""
    res = pipeline.run(data_dir=REPO_DATA, output_dir=tmp_path, today=REF_DATE, to_stage="rank", **kw)
    scored = [ScoredCandidate.from_dict(d) for d in artifacts.load_items(tmp_path, "rank")]
    return res, scored


def test_pipeline_end_to_end(tmp_path):
    res, scored = _run_gen(tmp_path, top_n=15)
    assert res.stage("recall").entered > 0
    assert res.stage("generate").survived > 0
    assert scored, "expected ranked candidates"
    assert artifacts.artifact_path(tmp_path, "rank").exists()
    assert (tmp_path / "ideas.md").exists()
    # alphas must be sorted-ish: the MMR head should still be a strong score.
    alphas = [s.alpha for s in scored]
    assert alphas[0] == max(alphas)


def test_pipeline_is_deterministic(tmp_path):
    _, a = _run_gen(tmp_path / "a", top_n=15)
    _, b = _run_gen(tmp_path / "b", top_n=15)
    assert [s.candidate.id for s in a] == [s.candidate.id for s in b]
    assert [s.alpha for s in a] == [s.alpha for s in b]


def test_time_decay_lowers_old_signals(tmp_path):
    _, scored = _run_gen(tmp_path)
    # The April voice-coding signal is ~2 months old; its decay must be < 1.
    decays = {s.candidate.observed_on: s.decay for s in scored}
    assert any(d < 1.0 for d in decays.values())


def test_source_filtering(tmp_path):
    _, scored = _run_gen(tmp_path, sources=["brain_inbox"])
    assert scored
    assert all(s.candidate.source == "brain_inbox" for s in scored)


def test_single_stage_rerun(tmp_path):
    """工件化的核心红利:任一段可以只重跑自己,输入从盘上来。"""
    _run_gen(tmp_path)
    before = artifacts.load(tmp_path, "rank")
    res = pipeline.run(data_dir=REPO_DATA, output_dir=tmp_path, today=REF_DATE, only="rank")
    after = artifacts.load(tmp_path, "rank")
    assert res.stages[0].stage == "rank"
    assert [i["id"] for i in after["items"]] == [i["id"] for i in before["items"]]
    # 续跑继承同一条 run 线(run_id 从上一段工件继承)。
    assert after["run_id"] == before["run_id"]
