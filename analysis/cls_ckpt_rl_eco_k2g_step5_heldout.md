# RA failure classification

### rl_eco_k2g_step5 — failure buckets (depth >= 5, n per depth)

| depth | n | ok | truncated | plan_omission | episode_omission | syntax_error | assembly_wrong | def_NameError | def_TypeError | def_wrong_answer | other |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 256 | 249 | 0 | 0 | 0 | 0 | 0 | 0 | 7 | 0 | 0 |
| 6 | 256 | 243 | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 0 | 1 |
| 7 | 256 | 240 | 1 | 0 | 0 | 0 | 0 | 1 | 11 | 0 | 3 |
| 8 | 256 | 240 | 0 | 0 | 2 | 0 | 0 | 1 | 10 | 0 | 3 |

### rl_eco_k2g_step5 — per-episode statistics (depth 2-8)

| depth | n | plan_incomplete | recall_incomplete | cue_arity_err | episodes | ep_ok | ep_TypeError | ep_wrong | ep_other |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 256 | n/a | 0.000 | n/a | 479 | 1.000 | 0.000 | 0.000 | 0.000 |
| 3 | 256 | n/a | 0.000 | n/a | 721 | 0.999 | 0.001 | 0.000 | 0.000 |
| 4 | 256 | n/a | 0.000 | n/a | 1011 | 0.994 | 0.006 | 0.000 | 0.000 |
| 5 | 256 | n/a | 0.000 | n/a | 1281 | 0.995 | 0.005 | 0.000 | 0.000 |
| 6 | 256 | n/a | 0.000 | n/a | 1556 | 0.992 | 0.008 | 0.000 | 0.000 |
| 7 | 256 | n/a | 0.000 | n/a | 1855 | 0.994 | 0.006 | 0.000 | 0.000 |
| 8 | 256 | n/a | 0.008 | n/a | 2002 | 0.995 | 0.005 | 0.000 | 0.000 |

### rl_eco_k2g_step5 — per-op episode verdicts (depth 2-8, all episodes of the op)

| op | episodes | ok | TypeError | wrong | other |
|---|---|---|---|---|---|
| func_0 | 615 | 0.998 | 0.002 | 0.000 | 0.000 |
| func_2 | 608 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_6 | 934 | 0.959 | 0.041 | 0.000 | 0.000 |
| func_7 | 832 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_8 | 930 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_10 | 637 | 0.998 | 0.002 | 0.000 | 0.000 |
| func_12 | 620 | 0.997 | 0.003 | 0.000 | 0.000 |
| func_14 | 621 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_16 | 631 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_18 | 949 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_21 | 624 | 0.992 | 0.008 | 0.000 | 0.000 |
| func_24 | 904 | 1.000 | 0.000 | 0.000 | 0.000 |
