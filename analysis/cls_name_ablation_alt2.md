# RA failure classification

### alt2_v1_s1 — failure buckets (depth >= 5, n per depth)

| depth | n | ok | truncated | plan_omission | episode_omission | syntax_error | assembly_wrong | def_NameError | def_TypeError | def_wrong_answer | other |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 256 | 73 | 0 | 0 | 0 | 0 | 0 | 2 | 140 | 39 | 2 |
| 6 | 256 | 62 | 0 | 0 | 0 | 4 | 0 | 3 | 160 | 24 | 3 |
| 7 | 256 | 30 | 1 | 0 | 10 | 2 | 0 | 0 | 182 | 28 | 3 |
| 8 | 256 | 29 | 0 | 0 | 5 | 8 | 0 | 2 | 189 | 21 | 2 |

### alt2_v1_s1 — per-episode statistics (depth 2-8)

| depth | n | plan_incomplete | recall_incomplete | cue_arity_err | episodes | ep_ok | ep_TypeError | ep_wrong | ep_other |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 256 | n/a | 0.000 | n/a | 479 | 0.942 | 0.038 | 0.021 | 0.000 |
| 3 | 256 | n/a | 0.000 | n/a | 721 | 0.883 | 0.083 | 0.033 | 0.000 |
| 4 | 256 | n/a | 0.000 | n/a | 1011 | 0.851 | 0.105 | 0.044 | 0.001 |
| 5 | 256 | n/a | 0.000 | n/a | 1281 | 0.799 | 0.123 | 0.069 | 0.009 |
| 6 | 256 | n/a | 0.000 | n/a | 1556 | 0.803 | 0.127 | 0.064 | 0.006 |
| 7 | 256 | n/a | 0.043 | n/a | 1832 | 0.793 | 0.131 | 0.073 | 0.003 |
| 8 | 256 | n/a | 0.020 | n/a | 1985 | 0.789 | 0.127 | 0.076 | 0.008 |

### alt2_v1_s1 — per-op episode verdicts (depth 2-8, all episodes of the op)

| op | episodes | ok | TypeError | wrong | other |
|---|---|---|---|---|---|
| func_ubiz | 611 | 0.989 | 0.000 | 0.008 | 0.003 |
| func_xojum | 604 | 0.947 | 0.000 | 0.051 | 0.002 |
| func_hocif | 932 | 0.998 | 0.000 | 0.000 | 0.002 |
| func_zeqi | 831 | 0.939 | 0.008 | 0.052 | 0.001 |
| func_eqah | 926 | 0.743 | 0.243 | 0.002 | 0.012 |
| func_hevul | 633 | 0.310 | 0.000 | 0.689 | 0.002 |
| func_demad | 620 | 0.974 | 0.000 | 0.024 | 0.002 |
| func_azes | 613 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_reben | 627 | 0.941 | 0.006 | 0.026 | 0.027 |
| func_lafud | 948 | 0.998 | 0.000 | 0.000 | 0.002 |
| func_qos | 621 | 0.984 | 0.005 | 0.005 | 0.006 |
| func_uzuw | 899 | 0.118 | 0.881 | 0.000 | 0.001 |

### alt2_eco_s1 — failure buckets (depth >= 5, n per depth)

| depth | n | ok | truncated | plan_omission | episode_omission | syntax_error | assembly_wrong | def_NameError | def_TypeError | def_wrong_answer | other |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 256 | 124 | 0 | 0 | 0 | 0 | 0 | 47 | 85 | 0 | 0 |
| 6 | 256 | 97 | 0 | 0 | 0 | 8 | 0 | 61 | 90 | 0 | 0 |
| 7 | 256 | 49 | 1 | 0 | 4 | 14 | 0 | 80 | 108 | 0 | 0 |
| 8 | 256 | 40 | 2 | 0 | 2 | 16 | 2 | 80 | 114 | 0 | 0 |

### alt2_eco_s1 — per-episode statistics (depth 2-8)

| depth | n | plan_incomplete | recall_incomplete | cue_arity_err | episodes | ep_ok | ep_TypeError | ep_wrong | ep_other |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 256 | n/a | 0.000 | n/a | 479 | 0.952 | 0.048 | 0.000 | 0.000 |
| 3 | 256 | n/a | 0.000 | n/a | 721 | 0.926 | 0.074 | 0.000 | 0.000 |
| 4 | 256 | n/a | 0.000 | n/a | 1011 | 0.931 | 0.069 | 0.000 | 0.000 |
| 5 | 256 | n/a | 0.000 | n/a | 1281 | 0.917 | 0.083 | 0.000 | 0.000 |
| 6 | 256 | n/a | 0.000 | n/a | 1556 | 0.922 | 0.077 | 0.000 | 0.001 |
| 7 | 256 | n/a | 0.016 | n/a | 1845 | 0.915 | 0.085 | 0.000 | 0.000 |
| 8 | 256 | n/a | 0.008 | n/a | 1992 | 0.918 | 0.081 | 0.000 | 0.001 |

### alt2_eco_s1 — per-op episode verdicts (depth 2-8, all episodes of the op)

| op | episodes | ok | TypeError | wrong | other |
|---|---|---|---|---|---|
| func_ubiz | 616 | 0.917 | 0.083 | 0.000 | 0.000 |
| func_xojum | 606 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_hocif | 933 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_zeqi | 831 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_eqah | 930 | 0.999 | 0.000 | 0.000 | 0.001 |
| func_hevul | 633 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_demad | 621 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_azes | 616 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_reben | 630 | 0.978 | 0.022 | 0.000 | 0.000 |
| func_lafud | 947 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_qos | 620 | 0.995 | 0.005 | 0.000 | 0.000 |
| func_uzuw | 902 | 0.306 | 0.691 | 0.000 | 0.003 |

### alt2_eco_s7 — failure buckets (depth >= 5, n per depth)

| depth | n | ok | truncated | plan_omission | episode_omission | syntax_error | assembly_wrong | def_NameError | def_TypeError | def_wrong_answer | other |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 256 | 251 | 0 | 0 | 0 | 0 | 0 | 1 | 4 | 0 | 0 |
| 6 | 256 | 245 | 2 | 0 | 1 | 1 | 0 | 4 | 3 | 0 | 0 |
| 7 | 256 | 237 | 0 | 0 | 6 | 4 | 0 | 8 | 0 | 1 | 0 |
| 8 | 256 | 226 | 0 | 0 | 10 | 3 | 0 | 14 | 2 | 1 | 0 |

### alt2_eco_s7 — per-episode statistics (depth 2-8)

| depth | n | plan_incomplete | recall_incomplete | cue_arity_err | episodes | ep_ok | ep_TypeError | ep_wrong | ep_other |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 256 | n/a | 0.000 | n/a | 479 | 1.000 | 0.000 | 0.000 | 0.000 |
| 3 | 256 | n/a | 0.000 | n/a | 721 | 0.999 | 0.001 | 0.000 | 0.000 |
| 4 | 256 | n/a | 0.000 | n/a | 1011 | 0.998 | 0.002 | 0.000 | 0.000 |
| 5 | 256 | n/a | 0.000 | n/a | 1281 | 0.997 | 0.003 | 0.000 | 0.000 |
| 6 | 256 | n/a | 0.008 | n/a | 1551 | 0.997 | 0.003 | 0.000 | 0.000 |
| 7 | 256 | n/a | 0.023 | n/a | 1839 | 0.999 | 0.000 | 0.001 | 0.000 |
| 8 | 256 | n/a | 0.039 | n/a | 1979 | 0.998 | 0.001 | 0.001 | 0.000 |

### alt2_eco_s7 — per-op episode verdicts (depth 2-8, all episodes of the op)

| op | episodes | ok | TypeError | wrong | other |
|---|---|---|---|---|---|
| func_ubiz | 614 | 0.998 | 0.002 | 0.000 | 0.000 |
| func_xojum | 604 | 0.998 | 0.002 | 0.000 | 0.000 |
| func_hocif | 933 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_zeqi | 831 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_eqah | 926 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_hevul | 632 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_demad | 620 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_azes | 613 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_reben | 628 | 0.989 | 0.006 | 0.005 | 0.000 |
| func_lafud | 946 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_qos | 616 | 0.989 | 0.011 | 0.000 | 0.000 |
| func_uzuw | 898 | 1.000 | 0.000 | 0.000 | 0.000 |
