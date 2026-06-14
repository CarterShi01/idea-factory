"""ff2 founder-fit (迭代③) prompt-content invariants.

ff2 投资人复评把项目从 3/10 钉在『往痛点贴创始人标签』。本轮三条核心改动落在
**prompt 文案**里(不是纯代码),容易随后续编辑悄悄漂走。这些测试把 ff2 的意图
钉成不变式:漂走即编译失败(=OC 的 as-code 真义,consistency-invariants-as-ci-rules)。

覆盖:
1. 生成 prompt『从独占资源反推』而非『先有痛点再贴标签』,且含竞争模拟(印度/YC 团队)。
2. critique + judge prompt 含『独占但盘子过小』(ff2 #8)市场规模 sanity。

这些是 *文案存在性* 断言(关键词必须出现),不假设具体措辞顺序,所以正常润色不会误伤,
但若有人把反推/竞争模拟/市场 sanity 整段删掉就会红。
"""

from pathlib import Path

from idea_core.llm import load_step_config

# Resolve the repo's config/llm relative to this test file so the suite is
# cwd-independent (the loader otherwise reads "config/llm" relative to cwd).
_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config" / "llm"


def _cfg(step: str) -> dict:
    return load_step_config(step, config_dir=_CONFIG_DIR)


def test_generate_prompt_reverses_from_monopoly_resource():
    cfg = _cfg("generate")
    sys = cfg["system"]
    # 反推: 从『独占资源』出发,而非给通用痛点贴标签。
    assert "独占资源" in sys
    assert "反推" in sys
    assert "贴标签" in sys  # 明确点名要避免的反模式
    # 三步顺序锚点。
    assert "第 1 步" in sys and "第 2 步" in sys and "第 3 步" in sys


def test_generate_prompt_has_competition_simulation():
    cfg = _cfg("generate")
    sys = cfg["system"]
    # 竞争模拟硬门:YC 下一批 / 印度团队凭什么赢。
    assert "竞争模拟" in sys
    assert "印度团队" in sys
    assert "YC" in sys


def test_generate_prompt_has_explicit_pos_neg_examples():
    cfg = _cfg("generate")
    sys = cfg["system"]
    # ff2 指定的反面(英文通用客服插件=毙)与正面(蒙语政企客服=留)例子。
    assert "英文通用客服插件" in sys      # 反面例子
    assert "蒙语政企客服" in sys          # 正面例子


def test_generate_user_template_carries_reverse_instruction():
    cfg = _cfg("generate")
    user = cfg["user_template"]
    assert "独占资源" in user
    assert "印度团队" in user or "竞争模拟" in user


def test_fusion_prompt_also_reverses():
    cfg = _cfg("generate")
    fusion_sys = cfg["fusion"]["system"]
    assert "独占资源" in fusion_sys
    assert "反推" in fusion_sys


def test_critique_prompt_flags_tiny_monopoly_market():
    cfg = _cfg("critique")
    sys = cfg["system"]
    # ff2 #8: 独占但盘子过小 / 理论 fit 但市场不存在。
    assert "盘子过小" in sys or "盘子太小" in sys
    assert "独占" in sys
    assert "ff2" in sys  # 锚到本轮复评


def test_judge_prompt_flags_tiny_monopoly_market():
    cfg = _cfg("judge")
    sys = cfg["system"]
    assert "盘子太小" in sys or "市场不存在" in sys
    assert "ff2" in sys
