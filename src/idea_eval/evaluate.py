"""idea_eval evaluation core -- screen idea candidates with a kill-gate.

This is the evaluation half's job, per the research: not "find the genius idea"
but "say no efficiently", like an investor screening deal flow.

Two mechanisms, both stage-0 rule-based and offline:

1. **Multiplicative-floor kill gate.** A fatal flaw on any *critical* dimension
   (no real pain, or not solo-buildable) kills the idea outright, no matter how
   well it scores elsewhere. This is the ``idea-validation-agents`` lesson: a
   single fatal short-board should collapse the score, not be averaged away.
2. **Weighted rubric score (0-100)** for the survivors, plus a templated
   "riskiest assumption" and a cheap (≤2 week / ≤\\$100) RAT experiment so the
   output is a *decision*, not just a number.

The factor *definitions* come from ``idea_core`` -- evl never recomputes them
differently from gen.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import json

from idea_core.factors import FACTORS

PURSUE = "pursue"
REVIEW = "review"
KILL = "kill"

# Critical dimensions: a fatal flaw here is disqualifying on its own.
CRITICAL = ("pain_intensity", "build_cost")
DEFAULT_FLOOR = 0.25

# Round 2(投资人复评严重度①):伪痛点 / 无证据痛点击杀门。
# 投资人证据:连续多条复用"独立开发者文档同步"这种编造痛点、"按语音语调判优先级"
# 纯臆想还能进前列。pain_intensity 因子已按证据强度打分;评估侧在此把『证据极弱的
# 痛点』判为致命缺陷——这是『高效说不』的价值中心,本轮允许加强。
# 低于此线视为伪痛点/无证据痛点,直接击杀(独立于通用 floor,门槛更低更"宽容",
# 只杀真正没有任何证据支撑的那一档)。
FAKE_PAIN_KILL_AT = 0.15
# synthetic(模拟人物)痛点要求更高的证据:没有付费/真实信号佐证时,门槛抬高。
SYNTHETIC_PAIN_KILL_AT = 0.30

# evl's own 5-dim rubric (judge LLM fills these; not the same as gen-side factors).
JUDGE_DIMS = ("pain_real", "solo_buildable", "reachable", "defensible", "timing")
# If top-level score and the avg of judge_scores * 100 disagree by more than this,
# the judge flagged itself as internally inconsistent.
SCORE_DISAGREEMENT_GAP = 25.0

# Verdict bands on the 0-100 rubric score (for ideas that pass the kill gate).
PURSUE_AT = 60.0
REVIEW_AT = 45.0

# evl's own rubric weights (same factor names as idea_core; evl owns its
# emphasis). Pain and solo-buildability carry the most weight.
# Round 2(投资人复评严重度④):纳入 payment_signal——真实付费意愿是评估侧最该奖励的
# 证据(round1:『有人正在花钱解决』=最强信号)。权重和保持 1.0。
RUBRIC_WEIGHTS = {
    "pain_intensity": 0.28,
    "payment_signal": 0.18,
    "build_cost": 0.18,
    "distribution_fit": 0.14,
    "market_freshness": 0.10,
    "competition_density": 0.06,
    "moat_signal": 0.06,
}

# 最危险假设 / 最小验证实验的中文文案模板。
_ASSUMPTION = {
    "pain_intensity": "假设这个痛点真实且尖锐——目前这是最弱的信号。",
    "build_cost": "假设一个人真的能把它做出来——但落地成本看起来偏高。",
    "distribution_fit": "假设你能触达这批用户——触达渠道是薄弱环节。",
    "market_freshness": "假设机会窗口还开着——这个方向可能已经不新鲜了。",
    "competition_density": "假设还有差异化空间——但赛道看起来已经拥挤。",
    "moat_signal": "假设你能建立护城河——但防御性尚不清晰。",
    "payment_signal": "假设真有人愿意为此付费——目前没有可信的付费证据。",
}
_EXPERIMENT = {
    "pain_intensity": "做 5 场问题访谈 + 在 3 个社群发帖描述痛点；看是否有人主动说“我愿意付费”。（1 周，0 元）",
    "build_cost": "用 2 天时间盒做最难技术点的预研；若一个人交付不了就放弃。（2 天，0 元）",
    "distribution_fit": "用你现有渠道触达 20 个目标用户；看回复率/意向率。（1 周，0 元）",
    "market_freshness": "查近 90 天搜索/HN/GitHub 趋势；确认是在上升而非已见顶。（半天，0 元）",
    "competition_density": "注册排名前 3 的竞品；记录你要切入的那个差距。（2 天，<100 元）",
    "moat_signal": "明确一个能锁住用户的工作流或数据资产；找 3 个用户验证。（3 天，0 元）",
    "payment_signal": "拿一个假落地页 + 价格,投 50 个目标用户,看有几个点『立即购买/预付』。（1 周，<100 元）",
}


@dataclass
class Evaluation:
    idea_id: str
    title: str
    verdict: str
    eval_score: float           # 0-100
    killed_by: list[str] = field(default_factory=list)
    riskiest_assumption: str = ""
    cheap_experiment: str = ""
    risk_flags: list[str] = field(default_factory=list)
    confidence: str = "real"
    factors: dict[str, float] = field(default_factory=dict)
    # B-step (LLM-as-judge) outputs
    killer_objection: str = ""
    judged_by: str = "rule"          # "rule" or "llm"
    judge_confidence: str = ""       # "high" / "medium" / "low" (LLM self-reported)
    confidence_demoted: bool = False  # True if low-confidence pursue/kill auto-demoted to review
    # B-step's own 5-dim rubric (not the gen-side factors — investor-style criteria
    # for the evaluation half: pain_real / solo_buildable / reachable / defensible / timing)
    judge_scores: dict[str, float] = field(default_factory=dict)
    # B-prep: devil's advocate critique (runs before the judge, separate prompt/call)
    critique: list[str] = field(default_factory=list)
    critique_killer: str = ""
    doomed_assumption: str = ""
    # B output: how the judge responded to the critique (anti-self-enhancement)
    judge_rebuttal: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _rubric_score(factors: dict[str, float]) -> float:
    total = sum(RUBRIC_WEIGHTS.get(name, 0.0) * factors.get(name, 0.0) for name in FACTORS)
    return round(total * 100, 1)


def _riskiest_dimension(factors: dict[str, float]) -> str:
    # Lowest-scoring factor among the ones we have; deterministic tie-break by name.
    known = {n: factors.get(n, 0.0) for n in FACTORS}
    return min(sorted(known), key=lambda n: known[n])


def _risk_flags(idea: dict, factors: dict[str, float]) -> list[str]:
    flags: list[str] = []
    if idea.get("confidence") == "synthetic":
        flags.append("基于模拟人物痛点——需要至少 1 条真实信号佐证。")
    # Round 2(严重度①):痛点证据偏弱(临界)——提醒人审核实痛点是否真实存在。
    if 0.15 <= factors.get("pain_intensity", 1.0) < 0.4:
        flags.append("痛点证据偏弱——疑似臆想或与信号关联不强,需核实真实性与付费意愿。")
    # Round 2(严重度④):无可信付费证据——警惕『买过课程≈愿付费』式的编造付费信号。
    if factors.get("payment_signal", 1.0) < 0.2:
        flags.append("无可信付费证据——没有人在为此真实付费/雇人,付费意愿待验证(警惕无关付费谬误)。")
    if factors.get("competition_density", 1.0) < 0.5:
        flags.append("赛道拥挤——差异化不清晰。")
    if factors.get("moat_signal", 1.0) <= 0.1:
        flags.append("没有明显护城河。")
    if factors.get("build_cost", 1.0) < 0.5:
        flags.append("对一人公司来说工程量偏重。")
    # ff1 founder-fit(投资人评审 ff1：流水线产通用货 2/10）：『通用货』降级旗。
    # 无独占渠道(distribution_fit 低=没有别人拿不到的获客)且无护城河(moat 低=周末能抄)
    # = 换成任何全栈程序员成功率不变。评估侧『高效说不』正是价值中心,把这类显式标出。
    if factors.get("distribution_fit", 1.0) < 0.3 and factors.get("moat_signal", 1.0) < 0.3:
        flags.append(
            "通用货——无创始人独占渠道(谁都能获客)且无护城河(周末能抄),"
            "换成任何全栈程序员成功率不变;不杠杆其语言/区域/人脉独占优势,建议降级。"
        )
    return flags


def _fake_pain_kill(idea: dict, factors: dict[str, float]) -> bool:
    """伪痛点 / 无证据痛点判定(Round 2 严重度①)。

    痛点强度极弱 = 痛点编造或与信号无关、没有真实证据支撑。synthetic(模拟人物)
    痛点用更高门槛,因为它本就需要 ≥1 条真实信号佐证才可信。
    """
    pain = factors.get("pain_intensity", 1.0)
    if idea.get("confidence") == "synthetic":
        return pain < SYNTHETIC_PAIN_KILL_AT
    return pain < FAKE_PAIN_KILL_AT


def evaluate_idea(idea: dict, floor: float = DEFAULT_FLOOR) -> Evaluation:
    """Evaluate one candidate dict (as produced by idea_gen's ideas.json)."""
    factors = idea.get("factors", {})
    killed_by = [dim for dim in CRITICAL if factors.get(dim, 1.0) < floor]
    # 伪痛点击杀:即便 pain_intensity 没掉到通用 floor 之下,只要证据极弱也算致命。
    if _fake_pain_kill(idea, factors) and "pain_intensity" not in killed_by:
        killed_by.append("pain_intensity")
    score = _rubric_score(factors)

    if killed_by:
        verdict = KILL
        score = round(score * 0.3, 1)        # fatal flaw collapses the score
    elif score >= PURSUE_AT:
        verdict = PURSUE
    elif score >= REVIEW_AT:
        verdict = REVIEW
    else:
        verdict = KILL

    dim = _riskiest_dimension(factors)
    return Evaluation(
        idea_id=idea.get("id", ""),
        title=idea.get("title", ""),
        verdict=verdict,
        eval_score=score,
        killed_by=killed_by,
        riskiest_assumption=_ASSUMPTION.get(dim, ""),
        cheap_experiment=_EXPERIMENT.get(dim, ""),
        risk_flags=_risk_flags(idea, factors),
        confidence=idea.get("confidence", "real"),
        factors=factors,
    )


_VERDICT_ORDER = {PURSUE: 0, REVIEW: 1, KILL: 2}


def _sort(evaluations: list[Evaluation]) -> list[Evaluation]:
    # pursue first, then review, then kill; within a band by score desc.
    evaluations.sort(key=lambda e: (_VERDICT_ORDER[e.verdict], -e.eval_score, e.idea_id))
    return evaluations


def evaluate_all(ideas: list[dict], floor: float = DEFAULT_FLOOR) -> list[Evaluation]:
    return _sort([evaluate_idea(i, floor=floor) for i in ideas])


# --- B-prep: devil's advocate critique -----------------------------------


def _survivor_fields(e: Evaluation, idea: dict) -> dict:
    return {
        "title": e.title,
        "pain": idea.get("pain", ""),
        "solution": idea.get("solution", ""),
        "target_user": idea.get("target_user", ""),
        "factors": json.dumps(e.factors, ensure_ascii=False),
        "confidence": e.confidence,
        # ff1 founder-fit: surface the generator's monopoly claims so the critic/judge
        # can attack them directly ("你说只有你能做,但这条用不上蒙语/没有那条引荐").
        # render_template ignores unused placeholders, so existing prompts are unaffected.
        "why_only_me": idea.get("why_only_me", ""),
        "first_10_customers": idea.get("first_10_customers", ""),
        "copy_fails_because": idea.get("copy_fails_because", ""),
    }


def critique_survivors(
    evaluations: list[Evaluation],
    ideas_by_id: dict[str, dict],
    llm,
    config: dict,
) -> list[Evaluation]:
    """Run an adversarial 'devil's advocate' pass over the rule-gate survivors.

    Pure attack: lists 3-5 concrete objections + a killer_objection + a
    doomed_assumption, with no scoring or final verdict. Output is then fed into
    ``judge_survivors`` so the judge has to engage with the strongest objections
    rather than rubber-stamp the generator's output (anti-self-enhancement).

    Mutates ``evaluations`` in place (no re-sort — verdicts unchanged here).
    May raise ``idea_core.llm.PendingHandoff`` (CC-handoff mode); let it propagate.
    """
    from idea_core.llm import build_request, render_template

    survivors = [e for e in evaluations if e.verdict in (PURSUE, REVIEW)]
    if not survivors:
        return evaluations

    template = config.get("user_template", "")
    requests = []
    for e in survivors:
        idea = ideas_by_id.get(e.idea_id, {})
        user = render_template(template, _survivor_fields(e, idea))
        requests.append(build_request(e.idea_id, user, config))

    responses = {r.id: r for r in llm.complete(requests)}
    for e in survivors:
        r = responses.get(e.idea_id)
        if not (r and r.ok and r.data):
            continue
        d = r.data
        objs = d.get("objections")
        if isinstance(objs, list):
            e.critique = [str(o) for o in objs if o]
        e.critique_killer = d.get("killer_objection", "") or e.critique_killer
        e.doomed_assumption = d.get("doomed_assumption", "") or e.doomed_assumption

    return evaluations


# --- B: LLM-as-judge -----------------------------------------------------


def _critique_block(e: Evaluation) -> str:
    if not e.critique and not e.critique_killer:
        return "（无对抗式批判 — 直接评估）"
    lines = [f"- {o}" for o in e.critique]
    if e.critique_killer:
        lines.append(f"最致命：{e.critique_killer}")
    if e.doomed_assumption:
        lines.append(f"若被证伪即垮的假设：{e.doomed_assumption}")
    return "\n".join(lines)


def judge_survivors(
    evaluations: list[Evaluation],
    ideas_by_id: dict[str, dict],
    llm,
    config: dict,
) -> list[Evaluation]:
    """Run the LLM judge (B) over the rule-gate survivors only (Top-K, token-thrifty).

    The cheap rule kill-gate has already removed the obvious losers; the LLM only
    sees pursue/review candidates, where adversarial judgment actually pays off.
    It may downgrade a survivor to ``kill``. Mutates and re-sorts ``evaluations``.

    If ``critique_survivors`` ran first and populated ``e.critique``, the judge
    user prompt injects it via the ``{critique}`` placeholder and the judge must
    fill ``respond_to_critique`` — forcing engagement with the strongest objection.

    May raise ``idea_core.llm.PendingHandoff`` (CC-handoff mode); let it propagate.
    """
    from idea_core.llm import build_request, render_template

    survivors = [e for e in evaluations if e.verdict in (PURSUE, REVIEW)]
    if not survivors:
        return evaluations

    template = config.get("user_template", "")
    requests = []
    for e in survivors:
        idea = ideas_by_id.get(e.idea_id, {})
        fields = _survivor_fields(e, idea)
        fields["critique"] = _critique_block(e)
        requests.append(build_request(e.idea_id, render_template(template, fields), config))

    responses = {r.id: r for r in llm.complete(requests)}
    for e in survivors:
        r = responses.get(e.idea_id)
        if not (r and r.ok and r.data):
            continue
        d = r.data
        e.judged_by = "llm"
        if d.get("verdict") in (PURSUE, REVIEW, KILL):
            e.verdict = d["verdict"]
        if isinstance(d.get("score"), (int, float)):
            e.eval_score = round(float(d["score"]), 1)
        e.killer_objection = d.get("killer_objection", "") or e.killer_objection
        e.riskiest_assumption = d.get("riskiest_assumption", "") or e.riskiest_assumption
        e.cheap_experiment = d.get("cheap_experiment", "") or e.cheap_experiment
        e.judge_rebuttal = d.get("respond_to_critique", "") or e.judge_rebuttal
        conf = d.get("confidence", "")
        if conf in ("high", "medium", "low"):
            e.judge_confidence = conf
            # Anti-overconfidence: low-confidence pursue/kill is forced to review
            # so a borderline call always falls into the human-audit lane.
            if conf == "low" and e.verdict in (PURSUE, KILL):
                e.verdict = REVIEW
                e.confidence_demoted = True
        sub = d.get("scores")
        if isinstance(sub, dict):
            e.judge_scores = {
                name: round(float(sub[name]), 3)
                for name in JUDGE_DIMS
                if isinstance(sub.get(name), (int, float))
            }
            # Self-consistency: top-level score vs avg of 5 sub-dims should agree.
            if len(e.judge_scores) == len(JUDGE_DIMS):
                avg100 = sum(e.judge_scores.values()) / len(JUDGE_DIMS) * 100
                if abs(avg100 - e.eval_score) > SCORE_DISAGREEMENT_GAP:
                    e.risk_flags.append(
                        f"评委自相矛盾：顶层 {e.eval_score:.0f} 分与五维平均 "
                        f"{avg100:.0f} 分差距过大。"
                    )

    return _sort(evaluations)
