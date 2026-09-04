# RA failure classification

### eco_init — failure buckets (depth >= 5, n per depth)

| depth | n | ok | truncated | plan_omission | episode_omission | syntax_error | assembly_wrong | def_NameError | def_TypeError | def_wrong_answer | other |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 256 | 244 | 0 | 0 | 0 | 4 | 0 | 1 | 7 | 0 | 0 |
| 6 | 256 | 241 | 0 | 0 | 1 | 4 | 0 | 0 | 10 | 0 | 0 |
| 7 | 256 | 227 | 0 | 0 | 4 | 14 | 1 | 1 | 9 | 0 | 0 |
| 8 | 256 | 214 | 0 | 0 | 13 | 18 | 0 | 0 | 10 | 0 | 1 |

### eco_init — per-episode statistics (depth 2-8)

| depth | n | plan_incomplete | recall_incomplete | cue_arity_err | episodes | ep_ok | ep_TypeError | ep_wrong | ep_other |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 256 | n/a | 0.000 | n/a | 479 | 1.000 | 0.000 | 0.000 | 0.000 |
| 3 | 256 | n/a | 0.000 | n/a | 721 | 1.000 | 0.000 | 0.000 | 0.000 |
| 4 | 256 | n/a | 0.000 | n/a | 1011 | 0.996 | 0.004 | 0.000 | 0.000 |
| 5 | 256 | n/a | 0.000 | n/a | 1281 | 0.995 | 0.005 | 0.000 | 0.000 |
| 6 | 256 | n/a | 0.004 | n/a | 1555 | 0.994 | 0.006 | 0.000 | 0.000 |
| 7 | 256 | n/a | 0.016 | n/a | 1840 | 0.995 | 0.005 | 0.000 | 0.000 |
| 8 | 256 | n/a | 0.051 | n/a | 1977 | 0.994 | 0.006 | 0.000 | 0.000 |

### eco_init — per-op episode verdicts (depth 2-8, all episodes of the op)

| op | episodes | ok | TypeError | wrong | other |
|---|---|---|---|---|---|
| func_0 | 612 | 0.998 | 0.002 | 0.000 | 0.000 |
| func_2 | 603 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_6 | 931 | 0.965 | 0.035 | 0.000 | 0.000 |
| func_7 | 831 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_8 | 924 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_10 | 632 | 0.997 | 0.003 | 0.000 | 0.000 |
| func_12 | 617 | 0.997 | 0.003 | 0.000 | 0.000 |
| func_14 | 618 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_16 | 626 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_18 | 947 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_21 | 621 | 0.994 | 0.006 | 0.000 | 0.000 |
| func_24 | 902 | 1.000 | 0.000 | 0.000 | 0.000 |
