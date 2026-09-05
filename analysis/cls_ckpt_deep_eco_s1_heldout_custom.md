# RA failure classification

### deep_eco_s1_heldout — failure buckets (depth >= 5, n per depth)

| depth | n | ok | truncated | plan_omission | episode_omission | syntax_error | assembly_wrong | def_NameError | def_TypeError | def_wrong_answer | other |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 6 | 256 | 249 | 0 | 0 | 0 | 0 | 0 | 0 | 7 | 0 | 0 |
| 8 | 256 | 235 | 0 | 0 | 0 | 6 | 0 | 2 | 13 | 0 | 0 |
| 10 | 256 | 223 | 0 | 0 | 1 | 16 | 0 | 2 | 13 | 0 | 1 |
| 12 | 256 | 200 | 0 | 0 | 11 | 17 | 0 | 1 | 26 | 0 | 1 |
| 14 | 256 | 187 | 0 | 0 | 5 | 40 | 1 | 3 | 18 | 0 | 2 |
| 16 | 256 | 173 | 0 | 0 | 6 | 42 | 1 | 2 | 27 | 0 | 5 |
| 18 | 256 | 140 | 0 | 0 | 9 | 72 | 1 | 2 | 26 | 0 | 6 |
| 20 | 256 | 128 | 0 | 0 | 16 | 91 | 1 | 0 | 17 | 0 | 3 |

### deep_eco_s1_heldout — per-episode statistics (depth 2-8)

| depth | n | plan_incomplete | recall_incomplete | cue_arity_err | episodes | ep_ok | ep_TypeError | ep_wrong | ep_other |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 256 | n/a | 0.000 | n/a | 512 | 1.000 | 0.000 | 0.000 | 0.000 |
| 4 | 256 | n/a | 0.000 | n/a | 1024 | 0.998 | 0.002 | 0.000 | 0.000 |
| 6 | 256 | n/a | 0.000 | n/a | 1536 | 0.995 | 0.005 | 0.000 | 0.000 |
| 8 | 256 | n/a | 0.000 | n/a | 2048 | 0.993 | 0.007 | 0.000 | 0.000 |

### deep_eco_s1_heldout — per-op episode verdicts (depth 2-8, all episodes of the op)

| op | episodes | ok | TypeError | wrong | other |
|---|---|---|---|---|---|
| func_0 | 1716 | 0.998 | 0.002 | 0.000 | 0.000 |
| func_2 | 1693 | 0.999 | 0.000 | 0.001 | 0.000 |
| func_6 | 1697 | 0.945 | 0.055 | 0.000 | 0.000 |
| func_7 | 1674 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_8 | 1693 | 0.990 | 0.010 | 0.000 | 0.000 |
| func_10 | 1673 | 0.999 | 0.001 | 0.000 | 0.000 |
| func_12 | 1667 | 0.992 | 0.008 | 0.000 | 0.000 |
| func_14 | 1645 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_16 | 1688 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_18 | 1643 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_21 | 1678 | 0.996 | 0.004 | 0.000 | 0.000 |
| func_24 | 1659 | 0.948 | 0.052 | 0.000 | 0.000 |
