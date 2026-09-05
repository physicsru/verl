# RA failure classification

### rl_eco_mix_step10 — failure buckets (depth >= 5, n per depth)

| depth | n | ok | truncated | plan_omission | episode_omission | syntax_error | assembly_wrong | def_NameError | def_TypeError | def_wrong_answer | other |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 256 | 243 | 0 | 0 | 0 | 0 | 0 | 1 | 12 | 0 | 0 |
| 6 | 256 | 236 | 0 | 0 | 0 | 0 | 0 | 1 | 19 | 0 | 0 |
| 7 | 256 | 225 | 0 | 0 | 1 | 0 | 0 | 3 | 26 | 0 | 1 |
| 8 | 256 | 234 | 0 | 0 | 2 | 0 | 0 | 1 | 18 | 0 | 1 |

### rl_eco_mix_step10 — per-episode statistics (depth 2-8)

| depth | n | plan_incomplete | recall_incomplete | cue_arity_err | episodes | ep_ok | ep_TypeError | ep_wrong | ep_other |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 256 | n/a | 0.000 | n/a | 479 | 1.000 | 0.000 | 0.000 | 0.000 |
| 3 | 256 | n/a | 0.000 | n/a | 721 | 0.997 | 0.003 | 0.000 | 0.000 |
| 4 | 256 | n/a | 0.000 | n/a | 1011 | 0.988 | 0.012 | 0.000 | 0.000 |
| 5 | 256 | n/a | 0.000 | n/a | 1281 | 0.991 | 0.009 | 0.000 | 0.000 |
| 6 | 256 | n/a | 0.000 | n/a | 1556 | 0.987 | 0.013 | 0.000 | 0.000 |
| 7 | 256 | n/a | 0.004 | n/a | 1845 | 0.985 | 0.015 | 0.000 | 0.000 |
| 8 | 256 | n/a | 0.008 | n/a | 1993 | 0.991 | 0.009 | 0.000 | 0.000 |

### rl_eco_mix_step10 — per-op episode verdicts (depth 2-8, all episodes of the op)

| op | episodes | ok | TypeError | wrong | other |
|---|---|---|---|---|---|
| func_0 | 615 | 0.948 | 0.052 | 0.000 | 0.000 |
| func_1 | 1 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_2 | 605 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_6 | 934 | 0.942 | 0.058 | 0.000 | 0.000 |
| func_7 | 831 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_8 | 928 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_10 | 634 | 0.998 | 0.002 | 0.000 | 0.000 |
| func_12 | 620 | 0.997 | 0.003 | 0.000 | 0.000 |
| func_14 | 619 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_16 | 628 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_18 | 947 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_21 | 622 | 0.997 | 0.003 | 0.000 | 0.000 |
| func_24 | 902 | 1.000 | 0.000 | 0.000 | 0.000 |
