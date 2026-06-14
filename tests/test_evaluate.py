from datetime import date

from idea_eval.evaluate import KILL, PURSUE, evaluate_all, evaluate_idea
from idea_eval.pipeline import run_evaluation
from idea_gen.pipeline import run_pipeline

REF_DATE = date(2026, 6, 13)


def _idea(**factors):
    base = {
        "market_freshness": 1.0,
        "pain_intensity": 1.0,
        "build_cost": 1.0,
        "moat_signal": 1.0,
        "competition_density": 1.0,
        "distribution_fit": 1.0,
    }
    base.update(factors)
    return {"id": "i1", "title": "demo", "confidence": "real", "factors": base}


def test_strong_idea_is_pursued():
    e = evaluate_idea(_idea())
    assert e.verdict == PURSUE
    assert e.eval_score >= 60


def test_fatal_flaw_kills_regardless_of_other_factors():
    # No real pain at all -> killed by the gate even though everything else is perfect.
    e = evaluate_idea(_idea(pain_intensity=0.0))
    assert e.verdict == KILL
    assert "pain_intensity" in e.killed_by


def test_score_in_range_and_has_memo_fields():
    e = evaluate_idea(_idea(moat_signal=0.1))
    assert 0 <= e.eval_score <= 100
    assert e.riskiest_assumption
    assert e.cheap_experiment


def test_evaluate_all_orders_pursue_before_kill():
    ideas = [_idea(pain_intensity=0.0), _idea()]  # first is a kill, second a pursue
    out = evaluate_all(ideas)
    verdicts = [e.verdict for e in out]
    assert verdicts.index(PURSUE) < verdicts.index(KILL)


def test_fake_pain_killed_even_above_floor():
    # Round 2(严重度①):证据极弱的伪痛点应被击杀,即便没掉到通用 floor 之下。
    e = evaluate_idea(_idea(pain_intensity=0.1))
    assert e.verdict == KILL
    assert "pain_intensity" in e.killed_by


def test_synthetic_pain_held_to_higher_evidence_bar():
    # pain=0.28 介于通用 floor(0.25)与 synthetic 门槛(0.30)之间:
    # real 不被痛点门击杀,synthetic 无佐证 -> 击杀。
    real = dict(_idea(pain_intensity=0.28), confidence="real")
    synth = dict(_idea(pain_intensity=0.28), id="i2", confidence="synthetic")
    assert "pain_intensity" not in evaluate_idea(real).killed_by
    e_synth = evaluate_idea(synth)
    assert e_synth.verdict == KILL
    assert "pain_intensity" in e_synth.killed_by


def test_weak_pain_evidence_raises_risk_flag():
    e = evaluate_idea(_idea(pain_intensity=0.3))
    assert any("痛点证据偏弱" in f for f in e.risk_flags)


def test_end_to_end_gen_then_eval(tmp_path):
    # gen produces ideas.json, eval consumes it -> the two halves connect on disk.
    gen = run_pipeline(data_dir="data", output_dir=tmp_path, today=REF_DATE)
    result = run_evaluation(
        input_path=gen.json_path, output_dir=tmp_path, today=REF_DATE
    )
    assert result.evaluated == len(gen.scored)
    assert result.pursue + result.review + result.killed == result.evaluated
    assert result.json_path.exists()
    assert result.memos_path.exists()
