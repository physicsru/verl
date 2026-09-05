# RA failure classification

### deep_eco_s1_trainops — failure buckets (depth >= 5, n per depth)

| depth | n | ok | truncated | plan_omission | episode_omission | syntax_error | assembly_wrong | def_NameError | def_TypeError | def_wrong_answer | other |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 6 | 256 | 255 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 8 | 256 | 253 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| 10 | 256 | 248 | 0 | 0 | 1 | 7 | 0 | 0 | 0 | 0 | 0 |
| 12 | 256 | 243 | 0 | 0 | 1 | 12 | 0 | 0 | 0 | 0 | 0 |
| 14 | 256 | 229 | 0 | 0 | 2 | 23 | 2 | 0 | 0 | 0 | 0 |
| 16 | 256 | 213 | 0 | 0 | 8 | 33 | 2 | 0 | 0 | 0 | 0 |
| 18 | 256 | 187 | 0 | 0 | 8 | 61 | 0 | 0 | 0 | 0 | 0 |
| 20 | 256 | 177 | 1 | 0 | 15 | 62 | 1 | 0 | 0 | 0 | 0 |

### deep_eco_s1_trainops — per-episode statistics (depth 2-8)

| depth | n | plan_incomplete | recall_incomplete | cue_arity_err | episodes | ep_ok | ep_TypeError | ep_wrong | ep_other |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 256 | n/a | 0.000 | n/a | 512 | 1.000 | 0.000 | 0.000 | 0.000 |
| 4 | 256 | n/a | 0.000 | n/a | 1024 | 1.000 | 0.000 | 0.000 | 0.000 |
| 6 | 256 | n/a | 0.000 | n/a | 1536 | 1.000 | 0.000 | 0.000 | 0.000 |
| 8 | 256 | n/a | 0.000 | n/a | 2048 | 1.000 | 0.000 | 0.000 | 0.000 |

### deep_eco_s1_trainops — per-op episode verdicts (depth 2-8, all episodes of the op)

| op | episodes | ok | TypeError | wrong | other |
|---|---|---|---|---|---|
| func_1 | 1456 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_3 | 1629 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_4 | 1606 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_5 | 1613 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_9 | 1516 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_11 | 1610 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_13 | 1493 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_15 | 1463 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_17 | 1628 | 0.999 | 0.000 | 0.000 | 0.001 |
| func_19 | 1616 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_20 | 1641 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_22 | 1646 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_23 | 1631 | 1.000 | 0.000 | 0.000 | 0.000 |
