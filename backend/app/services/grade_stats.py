"""成绩统计计算（统计分析与 AI 报告共用）。"""


def compute_grade_stats(scores: list[dict]) -> dict:
    """根据成绩明细计算统计指标。

    scores: [{"score": float, "full_score": float, "name"?: str}, ...]
    返回：total/avg_score/max_score/min_score/pass_rate/excellent_rate/score_distribution
    """
    values = [s["score"] for s in scores]
    if not values:
        return {
            "total": 0, "avg_score": 0, "max_score": 0, "min_score": 0,
            "pass_rate": 0, "excellent_rate": 0,
            "score_distribution": {"[90,100]": 0, "[80,90]": 0, "[70,80]": 0, "[60,70]": 0, "[0,60]": 0},
        }

    full = scores[0].get("full_score") or 100
    pass_line = full * 0.6
    excellent_line = full * 0.85

    distribution: dict[str, int] = {}
    for lo, hi in [(90, 100), (80, 90), (70, 80), (60, 70), (0, 60)]:
        key = f"[{lo},{hi}]"
        distribution[key] = sum(
            1 for s in values
            if lo <= (s / full * 100) < hi or (hi == 100 and s / full * 100 == 100)
        )

    return {
        "total": len(values),
        "avg_score": round(sum(values) / len(values), 2),
        "max_score": max(values),
        "min_score": min(values),
        "pass_rate": round(sum(1 for s in values if s >= pass_line) / len(values), 4),
        "excellent_rate": round(sum(1 for s in values if s >= excellent_line) / len(values), 4),
        "score_distribution": distribution,
    }
