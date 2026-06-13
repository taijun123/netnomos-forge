# NetNomos Forge

NetNomos Forge is a productization demo that combines **NetNomos rule discovery**, **LeJIT constrained generation**, **RAG-based rule explanation**, and a **dual-track compliance report workflow**.

The project turns domain data into reusable rules, explains those rules in business language, checks new material against the rules, and compares unconstrained model output with rule-constrained output.

Current W4 demos cover two vertical scenarios:

- **Network traffic**: CIDDS-style NetFlow rule discovery and constrained A/B generation.
- **Finance**: synthetic financial statements, injected accounting errors, rule validation, value projection, and A/B report comparison.

Chinese README: [README.zh-CN.md](README.zh-CN.md)

## What It Demonstrates

NetNomos Forge shows a practical pattern for controlling model output without modifying the base model:

1. Upload or select a data source.
2. Discover or load rules from clean data.
3. Explain rules with scenario knowledge and citations.
4. Upload new material for validation.
5. Run a rule check and capture violations.
6. Ask for a report through a user prompt.
7. Compare:
   - **Track A**: unconstrained model or deterministic mock output.
   - **Track B**: rule-checked, projected, and slot-filled constrained output.
8. Preview and download the report.

The key product value is the visible difference between fluent but unsafe output and output that is governed by explicit, inspectable rules.

## Current W4 Status

Implemented:

- FastAPI backend with background jobs, SSE workflow events, and job result polling.
- Multipart file upload to `/api/data-sources`, with files saved under `demo_artifacts/uploads/<scenario>/`.
- Request context propagation through workflow jobs: `dataSourceId`, `trainingDataSourceId`, `validationDataSourceId`, `question`, and `reportPrompt`.
- Rule source badges in the UI: `learned` rules are shown as data-discovered, while manual rules are shown as domain rules.
- Network demo loads archived NetNomos-discovered CIDDS golden rules.
- Finance demo validates injected accounting faults and generates dual-track reports.
- Workflow progress UI showing stages and processors such as NetNomos hitting-set/Z3, RuleExplainer/RAG, validation, projection, and A/B report generation.
- Demo asset folders for repeatable user-facing uploads and prompts.

Important W4 boundary:

- Uploaded files are saved and passed through the workflow as data source identifiers.
- The current validation and A/B outputs still reuse stable scenario pipelines rather than parsing arbitrary uploaded CSV/PDF/PCAP files row by row.
- This is intentional for W4 demo stability and is documented in the demo asset README files.

## Repository Layout

```text
netnomos-forge/
├── forge/                         Core SDK and scenario logic
│   ├── contracts.py               Frozen project contract; do not edit casually
│   ├── core/                      Engine, explainer, LLM routing, generator, projector, reporter
│   ├── scenarios/                 Scenario specs, knowledge, generators, validators
│   └── rulesets/                  Learned/golden rule assets and LeJIT bundles
├── server/                        FastAPI orchestrator, SSE jobs, in-memory store
├── web/                           React/Vite product demo UI
├── demo_artifacts/                Demo upload assets, generated reports, uploaded files
├── docs/                          API notes, W4 scripts, project reports
├── scripts/                       Validation and host helper scripts
├── tests/                         Python test suite
└── agents/                        Multi-agent collaboration notes/config
```

Expected workspace layout:

```text
model_control/
├── NetNomos/
├── LeJIT/
└── netnomos-forge/
```

`pyproject.toml` references `../NetNomos` and `../LeJIT` as editable local dependencies.

## Demo Assets

Use the top-level user guide:

```text
demo_artifacts/w4_demo_assets/user.md
```

Finance demo assets:

```text
demo_artifacts/w4_demo_assets/finance/
├── huaxin_audit_package.csv                  Upload this in the Finance "资料上传" step
├── finance_training_clean_960_correct.csv    Clean 960-row training reference
├── finance_training_clean_960_correct_zh.csv Clean 960-row training reference with Chinese headers
├── huaxin_clean_reference.csv                Clean 8-period reference package
├── truth_table.json                          Injected-fault truth table
├── prompts.md                                Copyable report prompts and talk track
└── README.md                                 Scenario instructions and limitations
```

Network demo assets:

```text
demo_artifacts/w4_demo_assets/network/
├── netflow_rule_anomaly_upload.csv             Upload this in the Network "新资料核查" step
├── cidds_wk2_normal_10k_correct_training.csv  Clean 10,000-row CIDDS training reference
├── network_generated_10_reference.csv         Generated NetFlow sample reference
├── network_b_track_reference_sample.json      Track B compliant sample reference
├── prompts.md                                 Copyable report prompts and talk track
└── README.md                                  Scenario instructions and limitations
```

## Quick Start

Install dependencies:

```powershell
cd E:\yanchh\model_control\netnomos-forge
uv sync
```

Run validation:

```powershell
uv run python scripts/quick_validate.py
uv run python -m pytest tests/test_pipeline.py
```

Start the backend:

```powershell
uv run uvicorn server.app:create_app --factory --host 0.0.0.0 --port 8000
```

Start the frontend:

```powershell
cd web
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

```text
http://127.0.0.1:5173/?v=w4source#/network
http://127.0.0.1:5173/?v=w4source#/finance
```

## Backend API Summary

Core endpoints:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/data-sources` | Register or upload a data source. Multipart uploads are persisted under `demo_artifacts/uploads/<scenario>/`. |
| `POST` | `/api/rulesets/upload` | Load a scenario rule set from default or supplied rule files. |
| `POST` | `/api/rulesets/learn` | Start a background workflow job. |
| `GET` | `/api/rulesets/{ruleset_id}/cards` | Return rule cards for a rule set. |
| `POST` | `/api/reports/generate` | Generate a dual-track report synchronously. |
| `GET` | `/api/workflow/events/stream` | Subscribe to workflow events by `sequence` or `job_id`. |
| `GET` | `/api/jobs/{job_id}` | Poll job status, events, request context, and final result. |
| `POST` | `/api/chat/constrained` | Draft a response and check numeric tokens against Track B compliant slots. |
| `GET` | `/api/health` | Health check. |

Supported scenario IDs:

- `finance_v1`
- `network_cidds`
- `network_pcap` currently reuses the network pipeline.

## Frontend Demo Flow

Finance:

1. Preview clean synthetic training data.
2. Learn/load finance rules.
3. Upload `huaxin_audit_package.csv`.
4. Run material validation.
5. Enter a report question.
6. Run A/B dual-track comparison.
7. Preview and download the report.

Network:

1. Confirm built-in CIDDS training data.
2. Load archived NetNomos-discovered rules.
3. Inspect rule cards and source badges.
4. Upload `netflow_rule_anomaly_upload.csv`.
5. Run new-material validation.
6. Enter a report question.
7. Run A/B dual-track comparison.
8. Preview and download the report.

## LLM and RAG Configuration

Ollama is optional. If unavailable, the system falls back through `ollama -> codex -> mock`, preserving deterministic demo behavior.

Useful environment variables:

| Variable | Default | Purpose |
|---|---:|---|
| `FORGE_RULECARD_LLM` | empty | Set to `1/true/yes/on` to enable LLM polishing for rule cards. |
| `FORGE_RULECARD_LLM_MAX_CARDS` | `2` | Maximum rule cards to polish per workflow. |
| `FORGE_RAG_TOP_K` | `3` | Number of knowledge snippets per rule. |
| `FORGE_RAG_MAX_SECTION_CHARS` | `1200` | Max characters per knowledge section. |
| `FORGE_RAG_MAX_CONTEXT_CHARS` | `3600` | Max RAG context in the prompt. |
| `FORGE_OLLAMA_EXPLAIN_MODEL` | `gemma3:27b` | Default explain-role Ollama model. |
| `FORGE_OLLAMA_DRAFT_MODEL` | `qwen2.5:14b-instruct` | Default draft-role Ollama model. |
| `FORGE_OLLAMA_HOST` / `OLLAMA_HOST` | `http://localhost:11434` | Ollama endpoint. |

## Testing

Common checks:

```powershell
uv run python scripts/quick_validate.py
uv run python -m pytest tests/test_pipeline.py
cd web
npm run build
```

Known caveats:

- Some upstream NetNomos reads can hit Windows GBK/UTF-8 issues unless UTF-8 mode is enabled.
- Full generic parsing of arbitrary uploaded PDF/Word/PCAP files is not yet implemented in W4.
- The in-memory job store is sufficient for demos but is not durable across backend restarts.
- Full finance workflows can take tens of seconds because report generation and validation run through the full scenario pipeline.

## Development Notes

- Keep `forge/contracts.py` stable unless the project contract is intentionally being revised.
- Higher-level code should import through `forge` APIs rather than directly depending on NetNomos or LeJIT internals.
- Heavy dependencies are lazily imported so that pure-Python tests and imports can run in constrained environments.
- Track B report text should be generated from controlled slots; numeric values should come from validated data or projected corrections.
