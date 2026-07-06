"""⑥diligence 的便宜前闸:规则 kill-gate(乘法下限)+ 加权 rubric(零 token)。

"高效说不"的第一道闸,在任何 LLM 评审之前跑:任一关键维度存在致命短板(没有真实
痛点、或一人公司做不了)即直接淘汰,不许被其他高分平均掉(idea-validation-agents
的教训)。幸存者得到 0-100 rubric 分 + 最危险假设 + ≤2 周/≤100 元的最小验证实验,
产出是**决策**不是数字。因子定义来自 idea_factory.factors(单一真相源)。
"""

from __future__ import annotations

from idea_factory.contract.models import (
    KILL,
    PURSUE,
    REVIEW,
    Evaluation,
    sort_evaluations,
)
from idea_factory.factors import FACTORS

# Critical dimensions: a fatal flaw here is disqualifying on its own.
CRITICAL = ("pain_intensity", "build_cost")
DEFAULT_FLOOR = 0.25

# Round 2(投资人复评严重度①):伪痛点 / 无证据痛点击杀门。
# 低于此线视为伪痛点/无证据痛点,直接击杀(独立于通用 floor,门槛更低更"宽容",
# 只杀真正没有任何证据支撑的那一档)。
FAKE_PAIN_KILL_AT = 0.15
# synthetic(模拟人物)痛点要求更高的证据:没有付费/真实信号佐证时,门槛抬高。
SYNTHETIC_PAIN_KILL_AT = 0.30

# Verdict bands on the 0-100 rubric score (for ideas that pass the kill gate).
PURSUE_AT = 60.0
REVIEW_AT = 45.0

# 本段自己的 rubric 权重(同名因子,评审侧自有侧重)。
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
    "founder_fit": "假设这条真的适合你做——但它没杠杆你的独占优势(蒙语/安全云/人脉),换个人成功率不变。",
}
_EXPERIMENT = {
    "pain_intensity": "做 5 场问题访谈 + 在 3 个社群发帖描述痛点；看是否有人主动说“我愿意付费”。（1 周，0 元）",
    "build_cost": "用 2 天时间盒做最难技术点的预研；若一个人交付不了就放弃。（2 天，0 元）",
    "distribution_fit": "用你现有渠道触达 20 个目标用户；看回复率/意向率。（1 周，0 元）",
    "market_freshness": "查近 90 天搜索/HN/GitHub 趋势；确认是在上升而非已见顶。（半天，0 元）",
    "competition_density": "注册排名前 3 的竞品；记录你要切入的那个差距。（2 天，<100 元）",
    "moat_signal": "明确一个能锁住用户的工作流或数据资产；找 3 个用户验证。（3 天，0 元）",
    "payment_signal": "拿一个假落地页 + 价格,投 50 个目标用户,看有几个点『立即购买/预付』。（1 周，<100 元）",
    "founder_fit": "写清这条具体杠杆你哪项独占资源(蒙语/内蒙信任/安全云引荐);找 1 个只有你能拿到的资源验证。（2 天，0 元）",
}


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
    # ff1 founder-fit:『通用货』降级旗——无独占渠道且无护城河 = 换任何全栈程序员成功率不变。
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
    """Evaluate one candidate dict (an ideas.json item)."""
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


def evaluate_all(ideas: list[dict], floor: float = DEFAULT_FLOOR) -> list[Evaluation]:
    return sort_evaluations([evaluate_idea(i, floor=floor) for i in ideas])
