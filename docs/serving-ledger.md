# Serving ledger — which serving has run which tier, and how it went

**Generated from `docs/traces/*.jsonl`. Do not hand-edit.** Regenerate with:

```bash
.venv/bin/python3 -c "import sys;sys.path.insert(0,'.');\
from tests.serving_ledger import derive,render;print(render(*derive('docs/traces')))"
```

`tests/test_serving_ledger.py` regenerates this table and fails if the committed
one has drifted, so it cannot go stale the way a hand-stamped fact does
(convention 24).

## Why this file exists

Which serving works at which tier is **the most expensive fact this project
keeps re-buying.** It was recorded in §6.1's triage table, §6.11's convergence
finding, B4's six-way pin test, the B12 sweep traces, and two pre-registrations
— and in none of them *together*. So every session re-derived it from trace
headers at the cost of a live run. §6.1 still carries a row reading
*"(unrecorded, likely StreamLake)"*.

Every committed trace header already names its model map and its provider pins,
and every unit beneath it names a terminal. **The record was always there; it
was never indexed.** This is that index.

## The ledger

| tier | model | serving | how | n | completed | other terminals | errors |
|---|---|---|---|---|---|---|---|
| `architecture` | `deepseek/deepseek-v4-pro` | **Alibaba** | rotated | 1 | 0 | — | 1 |
| `architecture` | `deepseek/deepseek-v4-pro` | **Baidu** | rotated | 2 | 1 | — | 1 |
| `architecture` | `deepseek/deepseek-v4-pro` | **DigitalOcean** | rotated | 2 | 1 | blocked 1 | 0 |
| `architecture` | `deepseek/deepseek-v4-pro` | **Novita** | rotated | 2 | 1 | blocked 1 | 0 |
| `architecture` | `deepseek/deepseek-v4-pro` | **SiliconFlow** | rotated | 2 | 1 | blocked 1 | 0 |
| `architecture` | `deepseek/deepseek-v4-pro` | **StreamLake** | rotated | 1 | 1 | — | 0 |
| `architecture` | `deepseek/deepseek-v4-pro` | **StreamLake** | pinned | 346 | 285 | blocked 13, escalated 8 | 40 |
| `architecture` | `thinkingmachines/inkling-small` | **DeepInfra** | pinned | 9 | 3 | blocked 5, escalated 1 | 0 |
| `architecture` | `xiaomi/mimo-v2.6-pro:exacto` | **deepinfra/fp8** | pinned | 1 | 0 | blocked 1 | 0 |
| `architecture` | `xiaomi/mimo-v2.6-pro:exacto` | **xiaomi/fp8** | pinned | 8 | 0 | blocked 7, escalated 1 | 0 |
| `architecture` | `z-ai/glm-5.3` | **Alibaba** | pinned | 1 | 0 | blocked 1 | 0 |
| `architecture` | `z-ai/glm-5.3` | **Baidu** | pinned | 1 | 0 | blocked 1 | 0 |
| `architecture` | `z-ai/glm-5.3` | **DigitalOcean** | pinned | 11 | 0 | blocked 11 | 0 |
| `architecture` | `z-ai/glm-5.3` | **Relace** | pinned | 3 | 0 | blocked 3 | 0 |
| `architecture` | `z-ai/glm-5.3` | **StreamLake** | pinned | 1 | 0 | — | 1 |
| `architecture` | `z-ai/glm-5.3-prime` | **Alibaba** | pinned | 2 | 0 | blocked 2 | 0 |
| `engineering` | `deepseek/deepseek-v4-flash` | **Alibaba** | rotated | 4 | 0 | blocked 2 | 2 |
| `engineering` | `deepseek/deepseek-v4-flash` | **AtlasCloud** | rotated | 3 | 0 | — | 3 |
| `engineering` | `deepseek/deepseek-v4-flash` | **Azure** | rotated | 2 | 0 | escalated 1 | 1 |
| `engineering` | `deepseek/deepseek-v4-flash` | **Baidu** | rotated | 2 | 0 | blocked 2 | 0 |
| `engineering` | `deepseek/deepseek-v4-flash` | **DeepInfra** | rotated | 6 | 0 | blocked 3, escalated 1 | 2 |
| `engineering` | `deepseek/deepseek-v4-flash` | **DeepInfra** | pinned | 10 | 2 | — | 8 |
| `engineering` | `deepseek/deepseek-v4-flash` | **DigitalOcean** | rotated | 8 | 0 | blocked 1, escalated 1 | 6 |
| `engineering` | `deepseek/deepseek-v4-flash` | **DigitalOcean** | pinned | 12 | 5 | escalated 2 | 5 |
| `engineering` | `deepseek/deepseek-v4-flash` | **GMICloud** | rotated | 5 | 0 | blocked 2 | 3 |
| `engineering` | `deepseek/deepseek-v4-flash` | **GMICloud** | pinned | 248 | 233 | blocked 6, escalated 1 | 8 |
| `engineering` | `deepseek/deepseek-v4-flash` | **Mancer 2** | rotated | 3 | 1 | — | 2 |
| `engineering` | `deepseek/deepseek-v4-flash` | **NextBit** | rotated | 3 | 0 | blocked 1 | 2 |
| `engineering` | `deepseek/deepseek-v4-flash` | **Novita** | rotated | 4 | 1 | blocked 1 | 2 |
| `engineering` | `deepseek/deepseek-v4-flash` | **OpenInference** | rotated | 18 | 2 | blocked 4, escalated 2 | 10 |
| `engineering` | `deepseek/deepseek-v4-flash` | **OpenInference** | pinned | 13 | 10 | escalated 2 | 1 |
| `engineering` | `deepseek/deepseek-v4-flash` | **Parasail** | rotated | 3 | 0 | — | 3 |
| `engineering` | `deepseek/deepseek-v4-flash` | **Phala** | rotated | 4 | 0 | blocked 1 | 3 |
| `engineering` | `deepseek/deepseek-v4-flash` | **SiliconFlow** | rotated | 2 | 0 | blocked 1, escalated 1 | 0 |
| `engineering` | `deepseek/deepseek-v4-flash` | **SiliconFlow** | pinned | 9 | 6 | — | 3 |
| `engineering` | `deepseek/deepseek-v4-flash` | **StreamLake** | rotated | 6 | 1 | blocked 2 | 3 |
| `engineering` | `deepseek/deepseek-v4-flash` | **StreamLake** | pinned | 10 | 5 | blocked 1, escalated 1 | 3 |
| `engineering` | `deepseek/deepseek-v4-flash` | **Venice** | rotated | 4 | 0 | blocked 2 | 2 |
| `engineering` | `deepseek/deepseek-v4-flash` | **Wafer** | rotated | 2 | 0 | — | 2 |
| `engineering` | `google/gemini-2.5-flash` | **GMICloud** | pinned | 1 | 0 | — | 1 |
| `engineering` | `minimax/minimax-m3` | **DeepInfra** | pinned | 1 | 0 | blocked 1 | 0 |
| `engineering` | `qwen/qwen3-235b-a22b-2507` | **Nebius** | pinned | 20 | 0 | blocked 19, escalated 1 | 0 |
| `engineering` | `xiaomi/mimo-v2.6-flash` | **Xiaomi** | pinned | 9 | 1 | blocked 8 | 0 |
| `engineering` | `z-ai/glm-5` | **StreamLake** | pinned | 6 | 2 | blocked 3, escalated 1 | 0 |
| `escalation` | `moonshotai/kimi-k3` | **Chutes** | rotated | 1 | 0 | escalated 1 | 0 |
| `escalation` | `moonshotai/kimi-k3` | **DeepInfra** | rotated | 2 | 0 | — | 2 |
| `escalation` | `moonshotai/kimi-k3` | **DigitalOcean** | rotated | 4 | 0 | escalated 1 | 3 |
| `escalation` | `moonshotai/kimi-k3` | **InferenceNet** | rotated | 1 | 0 | — | 1 |
| `escalation` | `moonshotai/kimi-k3` | **Modal** | rotated | 2 | 0 | blocked 1 | 1 |
| `escalation` | `moonshotai/kimi-k3` | **Moonshot AI** | pinned | 21 | 3 | blocked 17, escalated 1 | 0 |
| `escalation` | `moonshotai/kimi-k3` | **Relace** | pinned | 2 | 0 | blocked 2 | 0 |
| `escalation` | `moonshotai/kimi-k3` | **Sail Research** | rotated | 4 | 0 | escalated 1 | 3 |
| `escalation` | `moonshotai/kimi-k3` | **Together** | rotated | 3 | 0 | blocked 1 | 2 |
| `escalation` | `moonshotai/kimi-k3:exacto` | **inference-net/fp4** | pinned | 15 | 0 | blocked 14, escalated 1 | 0 |
| `escalation` | `openai/gpt-6.1-sol-pro` | **OpenAI** | pinned | 3 | 0 | blocked 3 | 0 |
| `judge` | `deepseek/deepseek-v4-flash` | **DigitalOcean** | pinned | 2 | 0 | blocked 2 | 0 |
| `judge` | `deepseek/deepseek-v4-pro-0813:exacto` | **relace/fp4** | pinned | 1 | 0 | blocked 1 | 0 |
| `judge` | `moonshotai/kimi-k2.5:exacto` | **siliconflow/int4** | pinned | 11 | 0 | blocked 10, escalated 1 | 0 |
| `judge` | `openai/gpt-5.2-chat` | **Azure** | pinned | 1 | 0 | blocked 1 | 0 |
| `judge` | `openai/gpt-6.1-sol-pro` | **OpenAI** | pinned | 3 | 0 | blocked 3 | 0 |
| `premium` | `openai/gpt-6.1-sol-pro` | **OpenAI** | pinned | 5 | 0 | blocked 5 | 0 |
| `premium` | `openai/gpt-6.1-sol-pro:exacto` | **Azure** | pinned | 15 | 0 | blocked 14, escalated 1 | 0 |
| `premium` | `z-ai/glm-5.3` | **Friendli** | pinned | 8 | 0 | blocked 8 | 0 |
| `premium` | `z-ai/glm-5.3-prime` | **Alibaba** | pinned | 13 | 3 | blocked 9, escalated 1 | 0 |
| `ranker` | `qwen/qwen3-reranker-8b` | **Fireworks** | pinned | 41 | 3 | blocked 36, escalated 2 | 0 |
| `research` | `google/gemini-2.5-flash` | **Google** | rotated | 126 | 68 | blocked 9, escalated 8 | 41 |
| `research` | `google/gemini-2.5-flash` | **Google** | pinned | 32 | 3 | blocked 28, escalated 1 | 0 |
| `research` | `google/gemini-3.8-flash` | **google-ai-studio** | pinned | 9 | 0 | blocked 8, escalated 1 | 0 |
| `research` | `moonshotai/kimi-k3` | **InferenceNet** | rotated | 1 | 0 | — | 1 |
| `research` | `moonshotai/kimi-k3` | **Modal** | rotated | 1 | 0 | — | 1 |
| `search` | `perplexity/sonar` | **Perplexity** | rotated | 54 | 22 | blocked 4, escalated 3 | 25 |
| `search` | `perplexity/sonar` | **Perplexity** | pinned | 41 | 3 | blocked 36, escalated 2 | 0 |
| `search` | `perplexity/sonar-pro` | **Perplexity** | rotated | 30 | 24 | blocked 2, escalated 1 | 3 |
| `triage` | `deepseek/deepseek-v4-flash` | **Alibaba** | pinned | 367 | 289 | blocked 26, escalated 9 | 43 |
| `triage` | `deepseek/deepseek-v4-flash` | **DigitalOcean** | pinned | 7 | 0 | blocked 7 | 0 |
| `triage` | `deepseek/deepseek-v4-pro-0813:exacto` | **relace/fp4** | pinned | 2 | 0 | blocked 2 | 0 |
| `triage` | `google/gemini-3.8-flash` | **google** | pinned | 1 | 0 | blocked 1 | 0 |
| `triage` | `google/gemini-3.8-flash` | **google-ai-studio** | pinned | 10 | 0 | blocked 9, escalated 1 | 0 |
