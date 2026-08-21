# Per-op depth-1 recall probe (greedy@1, hidden bodies)

| op | name | split | n | stage15 | stage1_baseline |
|---|---|---|---|---|---|
| func_0 | deterministic_shuffle | EVAL | 64 | 1.000 | 0.000 |
| func_1 | repeat_str | train | 64 | 1.000 | 0.422 |
| func_2 | remove_vowels | EVAL | 64 | 1.000 | 0.203 |
| func_3 | sort_chars | train | 64 | 1.000 | 0.047 |
| func_4 | reverse_words | train | 64 | 1.000 | 0.500 |
| func_5 | add_prefix | train | 64 | 1.000 | 0.031 |
| func_6 | add_suffix | EVAL | 64 | 1.000 | 0.734 |
| func_7 | interlace_str | EVAL | 64 | 1.000 | 0.000 |
| func_8 | rotate_str | EVAL | 64 | 1.000 | 0.016 |
| func_9 | mirror_str | train | 64 | 1.000 | 0.000 |
| func_10 | alternate_case | EVAL | 64 | 1.000 | 0.000 |
| func_11 | shift_chars | train | 64 | 1.000 | 0.000 |
| func_12 | vowel_to_number | EVAL | 64 | 1.000 | 0.203 |
| func_13 | insert_separator | train | 64 | 1.000 | 0.109 |
| func_14 | duplicate_every_char | EVAL | 64 | 1.000 | 0.000 |
| func_15 | fancy_brackets | train | 64 | 1.000 | 0.000 |
| func_16 | compress_repeats | EVAL | 64 | 1.000 | 0.438 |
| func_17 | recursive_reverse | train | 64 | 1.000 | 0.281 |
| func_18 | loop_concat | EVAL | 64 | 1.000 | 0.469 |
| func_19 | while_rotate | train | 64 | 1.000 | 0.000 |
| func_20 | recursive_interlace | train | 64 | 1.000 | 0.000 |
| func_21 | loop_filter_nonalpha | EVAL | 64 | 1.000 | 0.672 |
| func_22 | verify_even_length | train | 64 | 1.000 | 0.312 |
| func_23 | backchain_add_digit | train | 64 | 1.000 | 0.094 |
| func_24 | backchain_palindrome | EVAL | 64 | 1.000 | 0.000 |
| — | **mean ALL** | | | 1.000 | 0.181 |
| — | **mean train ops** | | | 1.000 | 0.138 |
| — | **mean eval ops** | | | 1.000 | 0.228 |
