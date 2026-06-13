from datetime import date

from idea_gen.pipeline import run_pipeline

REPO_DATA = "data"
REF_DATE = date(2026, 6, 13)


def test_pipeline_end_to_end(tmp_path):
    result = run_pipeline(
        data_dir=REPO_DATA,
        output_dir=tmp_path,
        today=REF_DATE,
        top_n=15,
    )
    assert result.raw_count > 0
    assert result.candidate_count > 0
    assert result.scored, "expected ranked candidates"
    assert result.json_path.exists()
    assert result.markdown_path.exists()
    # alphas must be sorted-ish: the MMR head should still be a strong score.
    alphas = [s.alpha for s in result.scored]
    assert alphas[0] == max(alphas)


def test_pipeline_is_deterministic(tmp_path):
    kw = dict(data_dir=REPO_DATA, output_dir=tmp_path, today=REF_DATE, top_n=15)
    a = run_pipeline(**kw)
    b = run_pipeline(**kw)
    assert [s.candidate.id for s in a.scored] == [s.candidate.id for s in b.scored]
    assert [s.alpha for s in a.scored] == [s.alpha for s in b.scored]


def test_time_decay_lowers_old_signals():
    fresh = run_pipeline(data_dir=REPO_DATA, output_dir="data/processed", today=REF_DATE)
    # The April voice-coding signal is ~2 months old; its decay must be < 1.
    decays = {s.candidate.observed_on: s.decay for s in fresh.scored}
    assert any(d < 1.0 for d in decays.values())


def test_source_filtering(tmp_path):
    result = run_pipeline(
        data_dir=REPO_DATA,
        output_dir=tmp_path,
        today=REF_DATE,
        sources=["brain_inbox"],
    )
    assert result.scored
    assert all(s.candidate.source == "brain_inbox" for s in result.scored)
