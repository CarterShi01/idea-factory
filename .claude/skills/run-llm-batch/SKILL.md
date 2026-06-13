---
name: run-llm-batch
description: >-
  Fulfill an idea-factory LLM request pack BY HAND inside this Claude Code session
  (Max pool). Use when idea-gen/idea-eval paused with "--*-backend cc" and wrote a
  data/llm_jobs/<job>.request.jsonl. You ARE the LLM here: read each request,
  produce a schema-conforming JSON answer, write <job>.response.jsonl. Invoke as
  "/run-llm-batch [job-name]" (job-name optional; auto-discovers the pending pack).
---

# run-llm-batch — fulfill an LLM request pack by hand

idea-factory's `cc` backend never calls an LLM API and never invokes Claude Code
programmatically. Instead it writes a **self-contained request pack** and pauses.
This skill is the manual half.

**Who runs this:** a human, directly, inside an interactive Claude Code session.
It is *not* for OC/Hermes orchestration — it is CC-native and human-invoked.
**You, this CC session, are the model**: you read the pack, do the generate/judge
thinking yourself (that is what spends the Max pool, by design), and write the
response pack. Then the pipeline resumes.

## Hard rules

- **Do the core reasoning yourself, in this session — that is the whole point.**
  Producing the generate/judge answers here is what uses the Max pool. The one
  thing to avoid: **don't route the core call back through idea-factory's
  `router` backend** (Tencent `router_chat` / `--backend router` / the
  `IDEA_LLM_*` endpoint). If you were going to do that, you'd just run
  `--*-backend router` and skip this skill entirely.
- **Tools are allowed and encouraged when they help.** Use your normal CC tools
  (Read / Write / Bash), and other APIs or MCP servers if they genuinely improve
  an answer (look something up, fetch context). Using tools is still you doing
  the work manually in CC.
- **Process the whole batch in one go.** One pack = one human touchpoint. Don't
  stop halfway or ask the user to re-invoke per item.
- **Conform to each request's `schema` exactly.** The pipeline parses your
  `data` object against it.
- **Preserve every `id` verbatim.** Responses are matched back by `id`.
- Touch only `data/llm_jobs/`. Don't edit pipeline code or other data.

## Input — the request pack

`data/llm_jobs/<job>.request.jsonl`, one JSON object per line:

```json
{"id": "<candidate id>", "system": "<role/instructions>", "user": "<the item to act on>",
 "schema": { ... JSON schema the answer must satisfy ... },
 "temperature": 0.1, "model": "tc-code", "meta": {}}
```

Every line in one pack shares the same `system` and `schema` (they come from the
same step config, `config/llm/generate.json` or `judge.json`). So read the
`system` prompt and the `schema` **once** to understand the task and the required
output shape, then apply them to each line's `user`.

## Output — the response pack

`data/llm_jobs/<job>.response.jsonl`, one JSON object per line, one per request:

```json
{"id": "<same id as the request>", "data": { ...your schema-conforming answer... }, "ok": true}
```

If you genuinely cannot answer one item, emit
`{"id": "<id>", "ok": false, "error": "<why>"}` instead of guessing.

## Procedure

1. **Find the job.**
   - If a job name was passed (e.g. `judge-2026-06-13`), use
     `data/llm_jobs/<job>.request.jsonl`.
   - Otherwise list `data/llm_jobs/*.request.jsonl` whose sibling
     `*.response.jsonl` does **not** exist; pick the most recent. If several are
     pending, ask the user which one.

2. **Read the pack** with the Read tool. Note the shared `system` and `schema`.
   Count the lines so you know the batch size.

3. **Do the work — you are the model.** For each request line, read its `user`
   content and produce a JSON object that satisfies `schema`, applying the
   `system` instructions. Be decisive and internally consistent across the batch
   (same bar for every item). Typical packs:
   - **generate** → `{"candidates": [{title, pain, solution, target_user, probability}, ...]}`
   - **judge** → `{"verdict": "pursue|review|kill", "score": <0-100>, "killer_objection": "...",
     "riskiest_assumption": "...", "cheap_experiment": "≤2 周/≤$100 的最小验证"}`

4. **Write the response pack** to `data/llm_jobs/<job>.response.jsonl` with the
   Write tool — one line per request, `id` copied verbatim, `data` schema-conforming.
   Keep the same order as the requests.

5. **Validate** (fix anything it flags, then re-validate):

   ```bash
   JOB=<job> python3 - <<'PY'
   import json, os
   job = os.environ["JOB"]
   R = [json.loads(l) for l in open(f"data/llm_jobs/{job}.request.jsonl") if l.strip()]
   S = [json.loads(l) for l in open(f"data/llm_jobs/{job}.response.jsonl") if l.strip()]
   rid, sid = [r["id"] for r in R], [s["id"] for s in S]
   miss, extra = set(rid) - set(sid), set(sid) - set(rid)
   bad = [s["id"] for s in S if s.get("ok", True) and not isinstance(s.get("data"), dict)]
   print(f"requests={len(R)} responses={len(S)}")
   if miss:  print("MISSING ids:", sorted(miss))
   if extra: print("UNKNOWN ids:", sorted(extra))
   if bad:   print("responses with no data object:", bad)
   print("OK" if not (miss or extra or bad) else "FIX NEEDED")
   PY
   ```

6. **Done.** Tell the user the response pack is ready and to resume by re-running
   the original command, e.g. `idea-eval --judge-backend cc --date <date>` (or
   `idea-gen --gen-backend cc ...`). The pipeline will read the responses and
   continue.

## Notes

- For a large pack, work through it in chunks but write **one** final
  `response.jsonl` covering all items.
- Keep judgments calibrated to idea-factory's intent: real pain, solo-buildable,
  reachable users; a fatal flaw on any critical dimension → `kill`.
- The request pack is self-contained, so you usually won't need anything beyond
  it — but you may consult other tools/sources if they sharpen a judgment.
