# RA failure classification

### c4_heldout — failure buckets (depth >= 3, n per depth)

| depth | n | ok | truncated | plan_omission | episode_omission | syntax_error | assembly_wrong | def_NameError | def_TypeError | def_wrong_answer | other |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | 256 | 227 | 0 | 0 | 1 | 0 | 0 | 0 | 28 | 0 | 0 |
| 4 | 256 | 172 | 0 | 0 | 15 | 0 | 0 | 0 | 69 | 0 | 0 |
| 5 | 256 | 115 | 0 | 0 | 40 | 0 | 0 | 1 | 100 | 0 | 0 |
| 6 | 256 | 77 | 0 | 0 | 85 | 0 | 0 | 0 | 94 | 0 | 0 |
| 7 | 256 | 50 | 0 | 0 | 121 | 0 | 0 | 1 | 84 | 0 | 0 |
| 8 | 256 | 29 | 1 | 0 | 159 | 3 | 0 | 3 | 61 | 0 | 0 |

### c4_heldout — per-episode statistics (depth 2-8)

| depth | n | plan_incomplete | recall_incomplete | cue_arity_err | episodes | ep_ok | ep_TypeError | ep_wrong | ep_other |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 256 | n/a | 0.000 | n/a | 481 | 1.000 | 0.000 | 0.000 | 0.000 |
| 3 | 256 | n/a | 0.004 | n/a | 720 | 0.958 | 0.042 | 0.000 | 0.000 |
| 4 | 256 | n/a | 0.059 | n/a | 994 | 0.918 | 0.082 | 0.000 | 0.000 |
| 5 | 256 | n/a | 0.156 | n/a | 1216 | 0.898 | 0.102 | 0.000 | 0.000 |
| 6 | 256 | n/a | 0.332 | n/a | 1390 | 0.886 | 0.114 | 0.000 | 0.000 |
| 7 | 256 | n/a | 0.473 | n/a | 1569 | 0.864 | 0.136 | 0.000 | 0.000 |
| 8 | 256 | n/a | 0.625 | n/a | 1593 | 0.862 | 0.138 | 0.000 | 0.000 |
