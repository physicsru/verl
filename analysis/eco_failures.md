# RA failure classification

### eco_heldout — failure buckets (depth >= 5, n per depth)

| depth | n | ok | truncated | plan_omission | episode_omission | syntax_error | assembly_wrong | def_NameError | def_TypeError | def_wrong_answer | other |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 256 | 244 | 0 | 0 | 0 | 4 | 0 | 1 | 7 | 0 | 0 |
| 6 | 256 | 239 | 0 | 0 | 1 | 4 | 0 | 0 | 12 | 0 | 0 |
| 7 | 256 | 227 | 0 | 0 | 4 | 14 | 1 | 1 | 9 | 0 | 0 |
| 8 | 256 | 213 | 0 | 0 | 14 | 18 | 0 | 0 | 10 | 0 | 1 |

### eco_heldout — per-episode statistics (depth 2-8)

| depth | n | plan_incomplete | recall_incomplete | cue_arity_err | episodes | ep_ok | ep_TypeError | ep_wrong | ep_other |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 256 | n/a | 0.000 | n/a | 479 | 1.000 | 0.000 | 0.000 | 0.000 |
| 3 | 256 | n/a | 0.000 | n/a | 721 | 0.999 | 0.001 | 0.000 | 0.000 |
| 4 | 256 | n/a | 0.000 | n/a | 1011 | 0.995 | 0.005 | 0.000 | 0.000 |
| 5 | 256 | n/a | 0.000 | n/a | 1281 | 0.995 | 0.005 | 0.000 | 0.000 |
| 6 | 256 | n/a | 0.004 | n/a | 1555 | 0.992 | 0.008 | 0.000 | 0.000 |
| 7 | 256 | n/a | 0.016 | n/a | 1840 | 0.995 | 0.005 | 0.000 | 0.000 |
| 8 | 256 | n/a | 0.055 | n/a | 1976 | 0.994 | 0.006 | 0.000 | 0.000 |

### eco_trainops — failure buckets (depth >= 5, n per depth)

| depth | n | ok | truncated | plan_omission | episode_omission | syntax_error | assembly_wrong | def_NameError | def_TypeError | def_wrong_answer | other |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 256 | 254 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| 6 | 256 | 251 | 0 | 0 | 4 | 1 | 0 | 0 | 0 | 0 | 0 |
| 7 | 256 | 241 | 0 | 0 | 6 | 9 | 0 | 0 | 0 | 0 | 0 |
| 8 | 256 | 224 | 0 | 0 | 16 | 16 | 0 | 0 | 0 | 0 | 0 |

### eco_trainops — per-episode statistics (depth 2-8)

| depth | n | plan_incomplete | recall_incomplete | cue_arity_err | episodes | ep_ok | ep_TypeError | ep_wrong | ep_other |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 256 | n/a | 0.000 | n/a | 485 | 1.000 | 0.000 | 0.000 | 0.000 |
| 3 | 256 | n/a | 0.000 | n/a | 736 | 1.000 | 0.000 | 0.000 | 0.000 |
| 4 | 256 | n/a | 0.000 | n/a | 1036 | 1.000 | 0.000 | 0.000 | 0.000 |
| 5 | 256 | n/a | 0.000 | n/a | 1330 | 1.000 | 0.000 | 0.000 | 0.000 |
| 6 | 256 | n/a | 0.016 | n/a | 1612 | 1.000 | 0.000 | 0.000 | 0.000 |
| 7 | 256 | n/a | 0.023 | n/a | 1913 | 1.000 | 0.000 | 0.000 | 0.000 |
| 8 | 256 | n/a | 0.062 | n/a | 2196 | 1.000 | 0.000 | 0.000 | 0.000 |
