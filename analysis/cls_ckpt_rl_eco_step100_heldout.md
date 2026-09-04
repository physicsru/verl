# RA failure classification

### rl_eco_step100 — failure buckets (depth >= 5, n per depth)

| depth | n | ok | truncated | plan_omission | episode_omission | syntax_error | assembly_wrong | def_NameError | def_TypeError | def_wrong_answer | other |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 256 | 175 | 0 | 0 | 0 | 1 | 0 | 0 | 79 | 1 | 0 |
| 6 | 256 | 151 | 0 | 0 | 0 | 0 | 0 | 1 | 104 | 0 | 0 |
| 7 | 256 | 107 | 0 | 0 | 1 | 0 | 0 | 0 | 144 | 2 | 2 |
| 8 | 256 | 108 | 0 | 0 | 1 | 0 | 0 | 1 | 144 | 0 | 2 |

### rl_eco_step100 — per-episode statistics (depth 2-8)

| depth | n | plan_incomplete | recall_incomplete | cue_arity_err | episodes | ep_ok | ep_TypeError | ep_wrong | ep_other |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 256 | n/a | 0.000 | n/a | 479 | 0.937 | 0.063 | 0.000 | 0.000 |
| 3 | 256 | n/a | 0.000 | n/a | 721 | 0.950 | 0.050 | 0.000 | 0.000 |
| 4 | 256 | n/a | 0.000 | n/a | 1011 | 0.941 | 0.059 | 0.000 | 0.000 |
| 5 | 256 | n/a | 0.000 | n/a | 1281 | 0.937 | 0.062 | 0.001 | 0.001 |
| 6 | 256 | n/a | 0.000 | n/a | 1556 | 0.933 | 0.067 | 0.000 | 0.000 |
| 7 | 256 | n/a | 0.004 | n/a | 1843 | 0.919 | 0.080 | 0.001 | 0.000 |
| 8 | 256 | n/a | 0.004 | n/a | 1993 | 0.924 | 0.076 | 0.000 | 0.000 |

### rl_eco_step100 — per-op episode verdicts (depth 2-8, all episodes of the op)

| op | episodes | ok | TypeError | wrong | other |
|---|---|---|---|---|---|
| func_0 | 614 | 0.029 | 0.964 | 0.005 | 0.002 |
| func_2 | 605 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_6 | 932 | 0.998 | 0.002 | 0.000 | 0.000 |
| func_7 | 831 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_8 | 929 | 0.994 | 0.006 | 0.000 | 0.000 |
| func_10 | 633 | 0.998 | 0.002 | 0.000 | 0.000 |
| func_12 | 620 | 0.995 | 0.005 | 0.000 | 0.000 |
| func_14 | 619 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_16 | 630 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_18 | 947 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_21 | 622 | 0.994 | 0.006 | 0.000 | 0.000 |
| func_24 | 902 | 1.000 | 0.000 | 0.000 | 0.000 |
