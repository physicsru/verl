# RA failure classification

### alt_v1_s7 — failure buckets (depth >= 5, n per depth)

| depth | n | ok | truncated | plan_omission | episode_omission | syntax_error | assembly_wrong | def_NameError | def_TypeError | def_wrong_answer | other |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 256 | 76 | 0 | 0 | 1 | 0 | 0 | 0 | 132 | 47 | 0 |
| 6 | 256 | 48 | 0 | 0 | 4 | 2 | 0 | 1 | 163 | 38 | 0 |
| 7 | 256 | 25 | 0 | 0 | 12 | 2 | 0 | 2 | 183 | 32 | 0 |
| 8 | 256 | 24 | 0 | 0 | 15 | 1 | 0 | 1 | 193 | 22 | 0 |

### alt_v1_s7 — per-episode statistics (depth 2-8)

| depth | n | plan_incomplete | recall_incomplete | cue_arity_err | episodes | ep_ok | ep_TypeError | ep_wrong | ep_other |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 256 | n/a | 0.000 | n/a | 479 | 0.879 | 0.081 | 0.040 | 0.000 |
| 3 | 256 | n/a | 0.004 | n/a | 720 | 0.842 | 0.106 | 0.053 | 0.000 |
| 4 | 256 | n/a | 0.008 | n/a | 1009 | 0.811 | 0.120 | 0.068 | 0.001 |
| 5 | 256 | n/a | 0.004 | n/a | 1280 | 0.812 | 0.111 | 0.077 | 0.000 |
| 6 | 256 | n/a | 0.016 | n/a | 1552 | 0.774 | 0.129 | 0.097 | 0.001 |
| 7 | 256 | n/a | 0.047 | n/a | 1829 | 0.789 | 0.132 | 0.079 | 0.000 |
| 8 | 256 | n/a | 0.059 | n/a | 1968 | 0.780 | 0.128 | 0.092 | 0.000 |

### alt_v1_s7 — per-op episode verdicts (depth 2-8, all episodes of the op)

| op | episodes | ok | TypeError | wrong | other |
|---|---|---|---|---|---|
| func_qzk | 614 | 0.910 | 0.077 | 0.013 | 0.000 |
| func_vex | 602 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_lsiw | 932 | 0.911 | 0.087 | 0.001 | 0.001 |
| func_kacy | 831 | 0.268 | 0.000 | 0.732 | 0.000 |
| func_dmov | 927 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_gethy | 631 | 0.902 | 0.000 | 0.098 | 0.000 |
| func_sfin | 617 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_xque | 605 | 0.967 | 0.002 | 0.031 | 0.000 |
| func_ubjet | 617 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_pidz | 944 | 0.878 | 0.119 | 0.003 | 0.000 |
| func_owgis | 618 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_umket | 899 | 0.077 | 0.922 | 0.000 | 0.001 |

### alt_eco_s1 — failure buckets (depth >= 5, n per depth)

| depth | n | ok | truncated | plan_omission | episode_omission | syntax_error | assembly_wrong | def_NameError | def_TypeError | def_wrong_answer | other |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 256 | 120 | 0 | 0 | 0 | 0 | 0 | 58 | 78 | 0 | 0 |
| 6 | 256 | 92 | 0 | 0 | 2 | 1 | 0 | 76 | 85 | 0 | 0 |
| 7 | 256 | 46 | 0 | 0 | 1 | 0 | 0 | 92 | 117 | 0 | 0 |
| 8 | 256 | 46 | 0 | 0 | 0 | 2 | 0 | 88 | 120 | 0 | 0 |

### alt_eco_s1 — per-episode statistics (depth 2-8)

| depth | n | plan_incomplete | recall_incomplete | cue_arity_err | episodes | ep_ok | ep_TypeError | ep_wrong | ep_other |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 256 | n/a | 0.000 | n/a | 479 | 0.965 | 0.035 | 0.000 | 0.000 |
| 3 | 256 | n/a | 0.000 | n/a | 721 | 0.933 | 0.067 | 0.000 | 0.000 |
| 4 | 256 | n/a | 0.000 | n/a | 1011 | 0.935 | 0.065 | 0.000 | 0.000 |
| 5 | 256 | n/a | 0.000 | n/a | 1281 | 0.925 | 0.075 | 0.000 | 0.000 |
| 6 | 256 | n/a | 0.008 | n/a | 1554 | 0.928 | 0.072 | 0.000 | 0.000 |
| 7 | 256 | n/a | 0.004 | n/a | 1850 | 0.915 | 0.085 | 0.000 | 0.000 |
| 8 | 256 | n/a | 0.000 | n/a | 1995 | 0.922 | 0.078 | 0.000 | 0.000 |

### alt_eco_s1 — per-op episode verdicts (depth 2-8, all episodes of the op)

| op | episodes | ok | TypeError | wrong | other |
|---|---|---|---|---|---|
| func_qzk | 615 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_vex | 606 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_lsiw | 935 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_kacy | 831 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_dmov | 928 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_gethy | 634 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_sfin | 622 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_xque | 618 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_ubjet | 630 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_pidz | 947 | 0.998 | 0.002 | 0.000 | 0.000 |
| func_owgis | 621 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_umket | 904 | 0.281 | 0.719 | 0.000 | 0.000 |

### alt_eco_s7 — failure buckets (depth >= 5, n per depth)

| depth | n | ok | truncated | plan_omission | episode_omission | syntax_error | assembly_wrong | def_NameError | def_TypeError | def_wrong_answer | other |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 256 | 176 | 0 | 0 | 0 | 0 | 0 | 0 | 80 | 0 | 0 |
| 6 | 256 | 156 | 0 | 0 | 1 | 0 | 0 | 0 | 99 | 0 | 0 |
| 7 | 256 | 114 | 0 | 0 | 11 | 0 | 0 | 0 | 131 | 0 | 0 |
| 8 | 256 | 114 | 0 | 0 | 12 | 2 | 0 | 0 | 128 | 0 | 0 |

### alt_eco_s7 — per-episode statistics (depth 2-8)

| depth | n | plan_incomplete | recall_incomplete | cue_arity_err | episodes | ep_ok | ep_TypeError | ep_wrong | ep_other |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 256 | n/a | 0.000 | n/a | 479 | 0.967 | 0.033 | 0.000 | 0.000 |
| 3 | 256 | n/a | 0.000 | n/a | 721 | 0.939 | 0.061 | 0.000 | 0.000 |
| 4 | 256 | n/a | 0.000 | n/a | 1011 | 0.946 | 0.054 | 0.000 | 0.000 |
| 5 | 256 | n/a | 0.000 | n/a | 1281 | 0.937 | 0.063 | 0.000 | 0.000 |
| 6 | 256 | n/a | 0.004 | n/a | 1555 | 0.933 | 0.067 | 0.000 | 0.000 |
| 7 | 256 | n/a | 0.043 | n/a | 1833 | 0.925 | 0.075 | 0.000 | 0.000 |
| 8 | 256 | n/a | 0.047 | n/a | 1971 | 0.930 | 0.070 | 0.000 | 0.000 |

### alt_eco_s7 — per-op episode verdicts (depth 2-8, all episodes of the op)

| op | episodes | ok | TypeError | wrong | other |
|---|---|---|---|---|---|
| func_qzk | 610 | 0.974 | 0.026 | 0.000 | 0.000 |
| func_vex | 602 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_lsiw | 932 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_kacy | 828 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_dmov | 923 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_gethy | 630 | 0.990 | 0.010 | 0.000 | 0.000 |
| func_sfin | 618 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_xque | 616 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_ubjet | 626 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_pidz | 946 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_owgis | 619 | 1.000 | 0.000 | 0.000 | 0.000 |
| func_umket | 901 | 0.387 | 0.613 | 0.000 | 0.000 |
