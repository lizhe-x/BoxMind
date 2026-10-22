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
| 2026-10-22 | retrieval | embedding / paraphrase-multilingual-MiniLM-L12-v2 | - | 50 | R@1 0.52 · R@3 0.74 · R@8 0.80 · MRR 0.74 · en 0.94 · zh 0.66 · category 0.68 · cross 0.75 · exact 1.00 · synonym 0.89 | p50 3 ms | [json](results/retrieval-2026-10-22T155518Z.json) |
| 2026-10-22 | tools | claude_code / sonnet | agent@2b5eb4f024 | 40 | pass 0.85 · en 0.80 · zh 0.90 · tools 0.89 · confirm 1.00 · args 1.00 · state 0.89 · missed gate 0 · spurious gate 0 · steps 1.7 | p50 11453 ms | [json](results/tools-2026-10-22T155518Z.json) |
| 2026-10-22 | retrieval | embedding / paraphrase-multilingual-MiniLM-L12-v2 | - | 50 | R@1 0.52 · R@3 0.74 · R@8 0.80 · MRR 0.74 · en 0.94 · zh 0.66 · category 0.68 · cross 0.75 · exact 1.00 · synonym 0.89 | p50 3 ms | [json](results/retrieval-2026-10-22T155935Z.json) |
| 2026-10-22 | tools | claude_code / sonnet | agent@2b5eb4f024 | 40 | pass 1.00 · en 1.00 · zh 1.00 · tools 1.00 · confirm 1.00 · args 1.00 · state 1.00 · missed gate 0 · spurious gate 0 · steps 1.7 | p50 9632 ms | [json](results/tools-2026-10-22T155935Z.json) |
| 2026-10-22 | tools | claude_code / haiku | agent@2b5eb4f024 | 40 | pass 0.97 · en 1.00 · zh 0.95 · tools 1.00 · confirm 1.00 · args 0.97 · state 0.97 · missed gate 0 · spurious gate 0 · steps 1.8 | p50 6376 ms | [json](results/tools-2026-10-22T160145Z.json) |
