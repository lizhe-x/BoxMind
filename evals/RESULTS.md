# Eval results

One row per run, appended by `evals/run.py`; raw per-case output in `results/`. `prompt` is the content hash
of the prompt wording that produced the row (see `backend/app/services/llm.py`), so two rows with the same
prompt and different models compare models, and the same model with different prompts compare prompt versions.

| date | set | provider / model | prompt | n | metrics | latency | raw |
|---|---|---|---|---|---|---|---|
| 2026-10-22 | routing | claude_code / sonnet | interpret@8c50a69b15 | 60 | acc 1.00 · en 1.00 · zh 1.00 · ingest F1 1.00 · query F1 1.00 · operation F1 1.00 | p50 2752 ms | [json](results/routing-2026-10-22T153544Z.json) |
| 2026-10-22 | extraction | claude_code / sonnet | interpret@8c50a69b15 | 40 | exact 0.90 · en 1.00 · zh 0.80 · intent 1.00 · label 1.00 · location 1.00 · items P 1.00 R 1.00 · qty 0.95 | p50 2845 ms | [json](results/extraction-2026-10-22T153544Z.json) |
| 2026-10-22 | routing | claude_code / haiku | interpret@8c50a69b15 | 60 | acc 1.00 · en 1.00 · zh 1.00 · ingest F1 1.00 · query F1 1.00 · operation F1 1.00 | p50 2910 ms | [json](results/routing-2026-10-22T153728Z.json) |
| 2026-10-22 | extraction | claude_code / haiku | interpret@8c50a69b15 | 40 | exact 0.82 · en 0.95 · zh 0.70 · intent 1.00 · label 1.00 · location 1.00 · items P 0.98 R 0.98 · qty 0.92 | p50 3345 ms | [json](results/extraction-2026-10-22T153728Z.json) |
