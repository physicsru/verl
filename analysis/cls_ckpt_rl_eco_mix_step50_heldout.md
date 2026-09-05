# RA failure classification

### rl_eco_mix_step50 — failure buckets (depth >= 5, n per depth)

| depth | n | ok | truncated | plan_omission | episode_omission | syntax_error | assembly_wrong | def_NameError | def_TypeError | def_wrong_answer | other |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 256 | 235 | 0 | 0 | 0 | 0 | 0 | 1 | 19 | 1 | 0 |
| 6 | 256 | 228 | 0 | 0 | 0 | 0 | 0 | 0 | 27 | 0 | 1 |
| 7 | 256 | 216 | 0 | 0 | 1 | 0 | 0 | 3 | 33 | 1 | 2 |
| 8 | 256 | 214 | 0 | 0 | 0 | 0 | 0 | 2 | 37 | 0 | 3 |

### rl_eco_mix_step50 — per-episode statistics (depth 2-8)

| depth | n | plan_incomplete | recall_incomplete | cue_arity_err | episodes | ep_ok | ep_TypeError | ep_wrong | ep_other |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 256 | n/a | 0.000 | n/a | 479 | 0.996 | 0.004 | 0.000 | 0.000 |
| 3 | 256 | n/a | 0.000 | n/a | 721 | 0.990 | 0.010 | 0.000 | 0.000 |
| 4 | 256 | n/a | 0.000 | n/a | 1011 | 0.967 | 0.032 | 0.001 | 0.000 |
| 5 | 256 | n/a | 0.000 | n/a | 1281 | 0.984 | 0.015 | 0.001 | 0.000 |
| 6 | 256 | n/a | 0.000 | n/a | 1557 | 0.983 | 0.017 | 0.000 | 0.000 |
| 7 | 256 | n/a | 0.004 | n/a | 1851 | 0.982 | 0.018 | 0.001 | 0.000 |
| 8 | 256 | n/a | 0.000 | n/a | 1998 | 0.980 | 0.020 | 0.000 | 0.000 |

### rl_eco_mix_step50 — per-op episode verdicts (depth 2-8, all episodes of the op)

| op | episodes | ok | TypeError | wrong | other |
|---|---|---|---|---|---|
| func_0 | 616 | 0.995 | 0.000 | 0.005 | 0.000 |
| func_1 | 3 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_2 | 607 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_6 | 934 | 0.858 | 0.142 | 0.000 | 0.000 |
| func_7 | 831 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_8 | 928 | 0.983 | 0.017 | 0.000 | 0.000 |
| func_10 | 635 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_12 | 621 | 0.998 | 0.002 | 0.000 | 0.000 |
| func_14 | 619 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_16 | 633 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_18 | 947 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_21 | 622 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_24 | 902 | 0.990 | 0.010 | 0.000 | 0.000 |
