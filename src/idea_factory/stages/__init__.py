"""层3 八段漏斗。每段一个子包,暴露 run(ctx) -> StageResult。

铁律(tests/test_stage_isolation.py 钉死):兄弟段互不 import;只能 import
contract / runtime / factors。组合只发生在 idea_factory.pipeline。
"""
