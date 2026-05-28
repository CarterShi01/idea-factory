"""Tests for keyword matching between collected signals and existing ideas."""

from __future__ import annotations

from idea_factory.match import find_related_ideas, format_suggestion, item_keywords


def _idea() -> dict:
    return {
        "id": "idea1",
        "pitch": "A deep work timer for remote engineers",
        "category": "productivity",
        "target_audience": "engineers",
        "pain_point": "context switching",
        "source_product_name": "FocusForge",
    }


def _unrelated_idea() -> dict:
    return {
        "id": "idea2",
        "pitch": "Crowdsourced hiking conditions",
        "category": "outdoors",
        "target_audience": "hikers",
        "pain_point": "stale trail info",
        "source_product_name": "TrailMix",
    }


def _item() -> dict:
    return {
        "id": "hn-9",
        "name": "A productivity timer for engineers",
        "source": "hackernews",
        "description": "boosts deep work",
    }


def test_find_related_matches_on_shared_keywords() -> None:
    matches = find_related_ideas([_item()], [_idea(), _unrelated_idea()])
    assert matches, "expected at least one match"
    top = matches[0]
    assert top["idea_id"] == "idea1"
    assert top["item_id"] == "hn-9"
    assert "engineers" in top["shared_keywords"]
    assert top["score"] == len(top["shared_keywords"])


def test_find_related_excludes_unrelated_idea() -> None:
    matches = find_related_ideas([_item()], [_unrelated_idea()])
    assert matches == []


def test_min_overlap_threshold_filters_weak_matches() -> None:
    weak = find_related_ideas([_item()], [_idea()], min_overlap=99)
    assert weak == []


def test_results_sorted_by_score_descending() -> None:
    strong_item = _item()
    weak_item = {"id": "hn-1", "name": "engineers meetup", "source": "hackernews"}
    matches = find_related_ideas([weak_item, strong_item], [_idea()])
    scores = [m["score"] for m in matches]
    assert scores == sorted(scores, reverse=True)


def test_item_keywords_drops_stopwords_and_short_tokens() -> None:
    kw = item_keywords({"name": "AI app for the new tool", "description": "go go"})
    assert "ai" not in kw and "the" not in kw and "app" not in kw
    assert "go" not in kw  # too short


def test_format_suggestion_mentions_idea_and_prompt() -> None:
    match = find_related_ideas([_item()], [_idea()])[0]
    line = format_suggestion(match)
    assert "这条可能和你某个 idea 相关" in line
    assert "idea1" in line
