"""Unit tests for pure evaluation metrics on hand-made inputs."""

from __future__ import annotations

from evals.metrics import (
    false_refusal_rate,
    hit_rate,
    key_fact_coverage,
    latency_summary,
    mrr,
    not_found_accuracy,
    precision_at_k,
    recall_at_1,
    recall_at_4,
    recall_at_k,
    refusal_precision,
    refusal_recall,
    cache_hit_rate,
)


def test_recall_and_mrr():
    ranks = [3, 7]
    assert recall_at_1(ranks) == 0.0
    assert recall_at_4(ranks) == 1.0
    assert recall_at_k(ranks, 2) == 0.0
    assert mrr(ranks) == 1.0 / 3.0
    assert precision_at_k(ranks, 4) == 0.25


def test_empty_relevant():
    assert recall_at_4([]) == 0.0
    assert mrr([]) == 0.0
    assert precision_at_k([], 4) == 0.0


def test_refusal_metrics():
    # gold: T=unanswerable; pred: T=refused
    pred = [True, True, False, False]
    gold = [True, False, False, True]
    assert not_found_accuracy(pred, gold) == 0.5
    assert refusal_precision(pred, gold) == 0.5  # 1 of 2 refusals correct
    assert refusal_recall(pred, gold) == 0.5  # 1 of 2 unanswerable refused
    assert false_refusal_rate(pred, gold) == 0.5  # 1 of 2 answerable refused


def test_hit_rate_and_cache():
    assert hit_rate([True, False, True]) == 2 / 3
    assert cache_hit_rate(1, 3) == 0.25
    assert cache_hit_rate(0, 0) is None


def test_key_fact_coverage():
    ans = "Ada Lovelace worked on the Analytical Engine in 1843."
    cov = key_fact_coverage(ans, ["Ada Lovelace", "1843", "missing fact"])
    assert cov == 2 / 3
    assert key_fact_coverage(ans, []) is None


def test_latency_summary():
    s = latency_summary([10.0, 20.0, 30.0, 40.0])
    assert s["count"] == 4
    assert s["p50_ms"] is not None
    assert s["p95_ms"] is not None
