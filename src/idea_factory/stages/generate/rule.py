"""③generate 的离线规则路径(零 token,CI/夹具用;真 ideation 在 .llm)。

Round 1(投资人评审严重度①⑤)：删掉了写死的『一个 LLM 智能体，持续监控并自动处理:[痛点]』
换皮模板——它正是 mode collapse 的源头。改成几个**不同切入角度**的脚手架，并强制
每条带上 mechanism/why_now/mvp_week1 三要素的具体占位(虽弱于 LLM，但不再是换皮)。
每个角度给出 (angle 名, 切入说明, 第1周MVP 形态) —— 角度互不相同以保留多样性。
"""

from __future__ import annotations

from typing import Callable

from idea_factory.contract.models import IdeaCandidate, Signal

_RULE_ANGLES: list[tuple[str, str, str]] = [
    (
        "工作流嵌入",
        "把处理动作直接嵌进用户已有的工作流(IDE/邮箱/工单系统)，在痛点发生的那一刻就地给出可一键应用的结果，而不是另开一个新工具",
        "一个挂在现有工具上的插件/钩子，对单一高频场景给出可一键采纳的具体产出",
    ),
    (
        "数据/对账侧",
        "抓取并比对该场景两侧的结构化数据(如系统记录 vs 实际状态)，把人工核对变成可解释的差异清单",
        "一个读两份数据源、输出带证据的差异报告的脚本",
    ),
    (
        "决策辅助",
        "不替用户做，而是把分散信息聚成一页可对比的决策视图，缩短『我该怎么办』的判断时间",
        "一个汇总输入、产出一页对比/建议视图的只读看板",
    ),
]

_DEFAULT_USER = "软件开发者与独立创业者"


def _target_user(signal: Signal) -> str:
    # 源③人群等自带的目标用户优先(蒙语中老年 / 英语学习者……),别被 dev 默认值覆盖。
    if getattr(signal, "target_user", "").strip():
        return signal.target_user.strip()
    cat = (signal.category or "").lower()
    if "dev" in cat or "ai" in cat or "software" in cat:
        return "开发者与技术型创始人"
    if "invest" in cat or "finance" in cat:
        return "管理 deal flow 的独立投资人"
    if "market" in cat or "content" in cat:
        return "独立营销人与创作者"
    return _DEFAULT_USER


def _rule_based_backend(signal: Signal) -> list[IdeaCandidate]:
    pain = signal.pain_statement or signal.title
    if not pain:
        return []
    user = _target_user(signal)
    candidates: list[IdeaCandidate] = []
    for idx, (angle, mechanism, mvp) in enumerate(_RULE_ANGLES):
        candidates.append(
            IdeaCandidate(
                id=f"{signal.id}-{idx}",
                signal_id=signal.id,
                source=signal.source,
                title=f"面向「{signal.title}」的{angle}方案"[:120],
                pain=pain,
                # No more 换皮模板：solution 体现该角度的具体机制，而非套『AI 智能体处理痛点』。
                solution=f"针对「{pain}」，采用「{angle}」路径：{mechanism}。",
                target_user=user,
                observed_on=signal.observed_on,
                confidence=signal.confidence,
                category=signal.category,
                trend_status=signal.trend_status,
                growth_speed=signal.growth_speed,
                mechanism=mechanism,
                why_now="离线规则路径未做竞品核查；请在精排(或 LLM 生成)阶段验证现有方案为何不足。",
                mvp_week1=mvp,
            )
        )
    return candidates


Backend = Callable[[Signal], list[IdeaCandidate]]


def generate(signals: list[Signal], backend: Backend = _rule_based_backend) -> list[IdeaCandidate]:
    candidates: list[IdeaCandidate] = []
    for signal in signals:
        candidates.extend(backend(signal))
    return candidates
