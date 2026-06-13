"""源③ 模拟痛点（离线基线版）：把 data/raw/personas.json 的每条痛点展开成合成信号。

Phase A 只保留与原 collect_personas 等价的离线行为（确定性、零 token），以便 demo /
测试不变。Phase B 在此基础上叠加：可增长人群 taxonomy、动态全选+细分挑选、四维价值
打分、LLM 合成痛点、真实信号佐证闸门（见 idea_gen.persona 包）。
"""

from __future__ import annotations

from idea_core.models import SOURCE_PERSONA

from . import CollectContext, read_json, register


class PersonaAdapter:
    name = "persona"
    source = SOURCE_PERSONA
    needs_llm = False  # 离线基线不调 LLM；Phase B 的 live 合成会切 True

    def collect(self, ctx: CollectContext) -> list[dict]:
        personas = read_json(ctx.raw_dir / "personas.json")
        records: list[dict] = []
        for persona in personas:
            who = persona.get("persona", "目标用户")
            for pain in persona.get("pains", []):
                records.append(
                    {
                        "source": self.source,
                        "source_name": "persona",
                        "title": pain.get("summary", ""),
                        "text": pain.get("verbatim", pain.get("summary", "")),
                        "pain": pain.get("summary", ""),
                        "category": persona.get("domain"),
                        "target_user": who,
                        "confidence": "synthetic",
                        "corroborated": pain.get("corroborated", False),
                    }
                )
        return records


register(PersonaAdapter())
