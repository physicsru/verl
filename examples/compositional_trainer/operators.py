"""Atomic string operators ("skills") for the compositional-generalization pipeline.

This module is *plumbing*: it holds the operator implementations plus the
train/eval splits and the length-preserving subset. In the algorithm we only
reason about question sets S and C; this file is just the skill library that
those sets are materialized from and that the executor runs.

Operator *bodies* are copied verbatim from RL-Compositionality's
``examples/data_preprocess/string_data.py`` so the ``paper`` pool is
byte-faithful to that baseline (same code, same ``func_0..func_24`` opaque
names, same train/eval split).

Two pools (see ``POOLS``):

* ``paper``   — all 25 operators, paper train_set(13)/eval_set(12) split.
                Includes growth operators; used for the *baseline*.
* ``lenpres`` — the 8 strictly length-preserving, unary operators (a subset of
                the 25). |output| == |input| at any composition depth, which is
                what makes the deep curriculum / depth-100 eval tractable. The
                train/eval assignment is *inherited from the paper split* (so
                e.g. ``rotate_str`` stays held-out).

Pure stdlib only — safe to import inside data generation, the reward function,
and offline checks.
"""

import os
from itertools import chain
from math import gcd

# ---------------------------------------------------------------------------
# Operators (verbatim from string_data.py)
# ---------------------------------------------------------------------------


def deterministic_shuffle(s):
    """Reorder characters using a fixed multiplier permutation."""
    L = len(s)
    if L == 0:
        return s
    multiplier = 3
    while gcd(multiplier, L) != 1:
        multiplier += 2
    return ''.join(s[(i * multiplier) % L] for i in range(L))


def repeat_str(s, n):
    """Repeat the string s exactly n times."""
    return s * n


def remove_vowels(s):
    """Remove vowels from the string."""
    vowels = 'aeiouAEIOU'
    return ''.join(ch for ch in s if ch not in vowels)


def sort_chars(s):
    """Sort the characters in the string."""
    return ''.join(sorted(s))


def reverse_words(s):
    """Reverse the order of words in the string."""
    words = s.split()
    return ' '.join(reversed(words))


def add_prefix(s, pre):
    """Add a fixed prefix to the string."""
    return pre + s


def add_suffix(s, suf):
    """Add a fixed suffix to the string."""
    return s + suf


def interlace_str(s1, s2):
    """Interlace two strings character by character (iterative)."""
    result = []
    len1, len2 = len(s1), len(s2)
    for i in range(max(len1, len2)):
        if i < len1:
            result.append(s1[i])
        if i < len2:
            result.append(s2[i])
    return ''.join(result)


def rotate_str(s, n):
    """Rotate the string s by n positions using slicing."""
    if not s:
        return s
    n = n % len(s)
    return s[n:] + s[:n]


def mirror_str(s):
    """Append the reversed string to the original."""
    return s + s[::-1]


def alternate_case(s):
    """Alternate the case of characters (even-index lower, odd-index upper)."""
    return ''.join(ch.lower() if i % 2 == 0 else ch.upper() for i, ch in enumerate(s))


def shift_chars(s, shift):
    """Shift alphabetical characters by a fixed amount (wrapping). Non-letters unchanged."""

    def shift_char(ch):
        if 'a' <= ch <= 'z':
            return chr((ord(ch) - ord('a') + shift) % 26 + ord('a'))
        elif 'A' <= ch <= 'Z':
            return chr((ord(ch) - ord('A') + shift) % 26 + ord('A'))
        return ch

    return ''.join(shift_char(ch) for ch in s)


def vowel_to_number(s):
    """Replace vowels with numbers: a/A->1, e/E->2, i/I->3, o/O->4, u/U->5."""
    mapping = {'a': '1', 'e': '2', 'i': '3', 'o': '4', 'u': '5', 'A': '1', 'E': '2', 'I': '3', 'O': '4', 'U': '5'}
    return ''.join(mapping.get(ch, ch) for ch in s)


def insert_separator(s, sep):
    """Insert a fixed separator between every two characters."""
    return sep.join(s)


def duplicate_every_char(s):
    """Duplicate every character in the string."""
    return ''.join(ch * 2 for ch in s)


def fancy_brackets(s):
    """Enclose each character in fancy brackets."""
    return ''.join("«" + ch + "»" for ch in s)


def compress_repeats(s):
    """Remove adjacent duplicate characters (compress repeats)."""
    if not s:
        return s
    result = [s[0]]
    for ch in s[1:]:
        if ch != result[-1]:
            result.append(ch)
    return ''.join(result)


def recursive_reverse(s):
    """Recursively reverse the string."""
    if s == "":
        return s
    return recursive_reverse(s[1:]) + s[0]


def loop_concat(s, n):
    """Concatenate s with itself n times using a loop."""
    result = ""
    for _ in range(n):
        result += s
    return result


def while_rotate(s, n):
    """Rotate the string using a while loop (n times)."""
    count = 0
    while count < n and s:
        s = s[1:] + s[0]
        count += 1
    return s


def recursive_interlace(s1, s2):
    """Recursively interlace two strings character by character."""
    if not s1 or not s2:
        return s1 + s2
    return s1[0] + s2[0] + recursive_interlace(s1[1:], s2[1:])


def loop_filter_nonalpha(s):
    """Remove non-alphabetic characters using an explicit loop."""
    result = ""
    for ch in s:
        if ch.isalpha():
            result += ch
    return result


def verify_even_length(s):
    """If the length of s is even, return s; otherwise remove the last character."""
    return s if len(s) % 2 == 0 else s[:-1]


def backchain_add_digit(s, depth):
    """Backtracking: deterministically transform s so it contains a digit."""

    def has_digit(t):
        return any(ch.isdigit() for ch in t)

    transformations = [
        lambda t: t + "1",
        lambda t: "2" + t,
        lambda t: t.replace("a", "3"),
        lambda t: t[::-1],
    ]

    def helper(t, d):
        if has_digit(t):
            return t
        if d == 0:
            return None
        for trans in transformations:
            new_t = trans(t)
            res = helper(new_t, d - 1)
            if res is not None:
                return res
        return None

    result = helper(s, depth)
    return result if result is not None else s


def backchain_palindrome(s, depth):
    """Back chaining: try to transform s into a palindrome by appending its reverse."""
    if s == s[::-1]:
        return s
    if depth <= 0:
        return s
    new_s = s + s[::-1]
    return backchain_palindrome(new_s, depth - 1)


# ---------------------------------------------------------------------------
# Extension ops (paper50 pool, 2026-09-04): 25 more skills in the same style —
# pure, total on any string (incl. ""), bounded growth (<= x2 + const), one-line
# docstring = the gloss (must not contain another op's name). They get
# func_25..func_49; the first 25 names/ids are untouched, so the `paper` pool
# stays byte-faithful. 13 join the train split, 12 the eval split (see POOLS).
# ---------------------------------------------------------------------------


def swap_pairs(s):
    """Swap every two adjacent characters (a trailing single character stays)."""
    chars = list(s)
    for i in range(0, len(chars) - 1, 2):
        chars[i], chars[i + 1] = chars[i + 1], chars[i]
    return ''.join(chars)


def rotate_halves(s):
    """Swap the first half and the second half of the string."""
    m = len(s) // 2
    return s[m:] + s[:m]


def double_vowels(s):
    """Write every vowel twice."""
    return ''.join(ch * 2 if ch in 'aeiouAEIOU' else ch for ch in s)


def count_prefix(s):
    """Prepend the number of characters to the string."""
    return str(len(s)) + s


def dedup_chars(s):
    """Keep only the first occurrence of each character."""
    seen = set()
    result = []
    for ch in s:
        if ch not in seen:
            seen.add(ch)
            result.append(ch)
    return ''.join(result)


def interleave_reverse(s):
    """Alternate the characters of the string with those of its reverse."""
    r = s[::-1]
    return ''.join(a + b for a, b in zip(s, r))


def halve_string(s):
    """Keep the first half of the string (rounding up)."""
    return s[:(len(s) + 1) // 2]


def wrap_brackets(s, n):
    """Wrap the string in n layers of square brackets."""
    for _ in range(n):
        s = '[' + s + ']'
    return s


def caesar_back(s, shift):
    """Shift letters backwards in the alphabet by a fixed amount (wrapping); other characters unchanged."""
    out = []
    for ch in s:
        if 'a' <= ch <= 'z':
            out.append(chr((ord(ch) - ord('a') - shift) % 26 + ord('a')))
        elif 'A' <= ch <= 'Z':
            out.append(chr((ord(ch) - ord('A') - shift) % 26 + ord('A')))
        else:
            out.append(ch)
    return ''.join(out)


def repeat_first(s, n):
    """Prepend the first character repeated n times."""
    if not s:
        return s
    return s[0] * n + s


def mark_vowels(s):
    """Put an asterisk after every vowel."""
    return ''.join(ch + '*' if ch in 'aeiouAEIOU' else ch for ch in s)


def zigzag(s):
    """Characters at even positions first, then characters at odd positions."""
    return s[0::2] + s[1::2]


def move_max_end(s):
    """Move the largest character (first occurrence) to the end."""
    if not s:
        return s
    i = s.index(max(s))
    return s[:i] + s[i + 1:] + s[i]


def upper_vowels(s):
    """Uppercase every vowel."""
    return ''.join(ch.upper() if ch in 'aeiou' else ch for ch in s)


def remove_consonants(s):
    """Remove consonant letters, keeping vowels and non-letters."""
    return ''.join(ch for ch in s if not (ch.isalpha() and ch.lower() not in 'aeiou'))


def double_middle(s):
    """Write the middle character twice."""
    if not s:
        return s
    m = len(s) // 2
    return s[:m] + s[m] * 2 + s[m + 1:]


def strip_edges(s):
    """Drop the first and the last character."""
    return s[1:-1] if len(s) >= 2 else ''


def letters_to_digits(s):
    """Replace each letter by its position in the alphabet modulo 10 (a=1, j=0); other characters unchanged."""
    out = []
    for ch in s:
        if ch.isalpha():
            out.append(str((ord(ch.lower()) - ord('a') + 1) % 10))
        else:
            out.append(ch)
    return ''.join(out)


def append_length(s):
    """Append the number of characters to the string."""
    return s + str(len(s))


def sandwich(s, ch):
    """Put the same fixed text at both ends of the string."""
    return ch + s + ch


def every_other(s):
    """Keep every other character, starting with the first."""
    return s[::2]


def repeat_last(s, n):
    """Append the last character repeated n times."""
    if not s:
        return s
    return s + s[-1] * n


def reverse_pairs(s):
    """Split into blocks of two characters and reverse the order of the blocks."""
    blocks = [s[i:i + 2] for i in range(0, len(s), 2)]
    return ''.join(reversed(blocks))


def sort_desc(s):
    """Sort the characters in descending order."""
    return ''.join(sorted(s, reverse=True))


def swap_ends(s):
    """Swap the first and the last character."""
    if len(s) < 2:
        return s
    return s[-1] + s[1:-1] + s[0]


# ---------------------------------------------------------------------------
# Opaque renaming (verbatim) — names leak nothing about the operation
# ---------------------------------------------------------------------------

func_name_mapping = {
    "deterministic_shuffle": 'func_0',
    "repeat_str": 'func_1',
    "remove_vowels": 'func_2',
    "sort_chars": 'func_3',
    "reverse_words": 'func_4',
    "add_prefix": 'func_5',
    "add_suffix": 'func_6',
    "interlace_str": 'func_7',
    "rotate_str": 'func_8',
    "mirror_str": 'func_9',
    "alternate_case": 'func_10',
    "shift_chars": 'func_11',
    "vowel_to_number": 'func_12',
    "insert_separator": 'func_13',
    "duplicate_every_char": 'func_14',
    "fancy_brackets": 'func_15',
    "compress_repeats": 'func_16',
    "recursive_reverse": 'func_17',
    "loop_concat": 'func_18',
    "while_rotate": 'func_19',
    "recursive_interlace": 'func_20',
    "loop_filter_nonalpha": 'func_21',
    "verify_even_length": 'func_22',
    "backchain_add_digit": 'func_23',
    "backchain_palindrome": 'func_24',
    # paper50 extension (func_25..func_49): 13 train, then 12 eval
    "swap_pairs": 'func_25',
    "rotate_halves": 'func_26',
    "double_vowels": 'func_27',
    "count_prefix": 'func_28',
    "dedup_chars": 'func_29',
    "interleave_reverse": 'func_30',
    "halve_string": 'func_31',
    "wrap_brackets": 'func_32',
    "caesar_back": 'func_33',
    "repeat_first": 'func_34',
    "mark_vowels": 'func_35',
    "zigzag": 'func_36',
    "move_max_end": 'func_37',
    "upper_vowels": 'func_38',
    "remove_consonants": 'func_39',
    "double_middle": 'func_40',
    "strip_edges": 'func_41',
    "letters_to_digits": 'func_42',
    "append_length": 'func_43',
    "sandwich": 'func_44',
    "every_other": 'func_45',
    "repeat_last": 'func_46',
    "reverse_pairs": 'func_47',
    "sort_desc": 'func_48',
    "swap_ends": 'func_49',
}

# Alternative OPAQUE, NON-NUMERIC names (name-collision ablation, HISTORY §17):
# same `func_` prefix, letter tokens instead of digits — isolates "digit-token
# neighbour confusion" (func_10→func_11 etc.). Select with
# COMPOSITIONAL_NAME_SCHEME=alt (read once at import). FUNC_RE_STR / FUNC_ORDER
# are the scheme-aware regex + canonical sort order every consumer must use.
_ALT_TOKENS = ["qzk", "wrm", "vex", "hjd", "tolf", "brug", "lsiw", "kacy", "dmov", "nupx",
               "gethy", "rybon", "sfin", "cowl", "xque", "mafo", "ubjet", "ykher", "pidz",
               "enrov", "javt", "owgis", "aqes", "ilcum", "umket",
               # paper50 extension (func_25..func_49)
               "jol", "koga", "ivop", "cedi", "tajo", "hul", "daqu", "par", "iqog", "ulof", "wucih", "sizem", "axaq",
               "sajuw", "ogeg", "wom", "nodo", "ocaz", "kef", "mexap", "atah", "upic", "upaz", "iqup", "gakuf"]
# Second letter scheme (different random assignment) to check that an `alt` effect is not one
# lucky name→op assignment. COMPOSITIONAL_NAME_SCHEME=alt2.
_ALT2_TOKENS = ["ubiz", "osub", "xojum", "daj", "qotu", "emon", "hocif", "zeqi", "eqah", "zedu",
                "hevul", "sirov", "demad", "viwus", "azes", "vux", "reben", "fapoc", "lafud", "jiva",
                "sotox", "qos", "apeq", "imig", "uzuw",
                # paper50 extension (func_25..func_49)
                "duvi", "kam", "exag", "xuj", "nuca", "mar", "quc", "huj", "wol", "ceq", "aqun", "vevu", "teto",
                "qobab", "qawos", "xoji", "jeguc", "bac", "muf", "lux", "uwuq", "idiv", "kev", "foq", "dugu"]
NAME_SCHEME = os.environ.get("COMPOSITIONAL_NAME_SCHEME", "num")
assert NAME_SCHEME in ("num", "alt", "alt2"), f"COMPOSITIONAL_NAME_SCHEME={NAME_SCHEME!r}"
if NAME_SCHEME == "alt":
    func_name_mapping = {op: f"func_{tok}" for op, tok in zip(list(func_name_mapping), _ALT_TOKENS)}
elif NAME_SCHEME == "alt2":
    func_name_mapping = {op: f"func_{tok}" for op, tok in zip(list(func_name_mapping), _ALT2_TOKENS)}
assert len(set(func_name_mapping.values())) == len(func_name_mapping), "duplicate opaque names"
FUNC_RE_STR = r"func_\d+" if NAME_SCHEME == "num" else r"func_[a-z]+"
# Every op the module knows (50), real name -> callable; pools below pick subsets.
ALL_OPS = {name: globals()[name] for name in func_name_mapping}
FUNC_ORDER = {fn: i for i, fn in enumerate(func_name_mapping.values())}
GCD_FUNC = func_name_mapping["deterministic_shuffle"]   # the one op whose body needs `from math import gcd`

# ---------------------------------------------------------------------------
# Paper pool (baseline) — verbatim split from string_data.py
# ---------------------------------------------------------------------------

PAPER_EVAL_SET = {
    "deterministic_shuffle": deterministic_shuffle,
    "remove_vowels": remove_vowels,
    "add_suffix": add_suffix,
    "interlace_str": interlace_str,
    "rotate_str": rotate_str,
    "alternate_case": alternate_case,
    "vowel_to_number": vowel_to_number,
    "duplicate_every_char": duplicate_every_char,
    "compress_repeats": compress_repeats,
    "loop_concat": loop_concat,
    "loop_filter_nonalpha": loop_filter_nonalpha,
    "backchain_palindrome": backchain_palindrome,
}

PAPER_TRAIN_SET = {
    "repeat_str": repeat_str,
    "sort_chars": sort_chars,
    "reverse_words": reverse_words,
    "add_prefix": add_prefix,
    "mirror_str": mirror_str,
    "shift_chars": shift_chars,
    "insert_separator": insert_separator,
    "fancy_brackets": fancy_brackets,
    "recursive_reverse": recursive_reverse,
    "while_rotate": while_rotate,
    "recursive_interlace": recursive_interlace,
    "verify_even_length": verify_even_length,
    "backchain_add_digit": backchain_add_digit,
}

PAPER_ALL_SET = {k: v for k, v in chain(PAPER_TRAIN_SET.items(), PAPER_EVAL_SET.items())}

# ---------------------------------------------------------------------------
# Length-preserving pool (deep track) — |output| == |input| at any depth.
# Subset of the 25; train/eval assignment inherited from the paper split.
# ---------------------------------------------------------------------------

LENPRES_NAMES = [
    "sort_chars",            # paper train  (reorder)
    "shift_chars",           # paper train  (substitute, param)
    "recursive_reverse",     # paper train  (reorder)
    "while_rotate",          # paper train  (reorder, param)  == rotate_str
    "deterministic_shuffle",  # paper eval  (reorder)
    "rotate_str",            # paper eval   (reorder, param)  == while_rotate
    "alternate_case",        # paper eval   (substitute)
    "vowel_to_number",       # paper eval   (substitute)
]

LENPRES_TRAIN = {n: PAPER_ALL_SET[n] for n in LENPRES_NAMES if n in PAPER_TRAIN_SET}
LENPRES_EVAL = {n: PAPER_ALL_SET[n] for n in LENPRES_NAMES if n in PAPER_EVAL_SET}
LENPRES_ALL = {n: PAPER_ALL_SET[n] for n in LENPRES_NAMES}

# Numeric-constant specs for parameterized ops: (argname, low, high) inclusive.
# Ranges match string_data.random_expr. String-literal params handled in the
# generator, not here.
PARAM_SPECS = {
    "rotate_str": ("n", 1, 3),
    "shift_chars": ("shift", 1, 5),
    "while_rotate": ("n", 1, 3),
    "repeat_str": ("n", 2, 4),
    "loop_concat": ("n", 2, 4),
    "backchain_add_digit": ("depth", 1, 3),
    "backchain_palindrome": ("depth", 1, 3),
    # paper50 extension
    "wrap_brackets": ("n", 1, 3),
    "caesar_back": ("shift", 1, 5),
    "repeat_first": ("n", 2, 4),
    "repeat_last": ("n", 2, 4),
}

# Argument specs of the EXTENSION ops for the generator (the original 25 are rendered by
# generate_data.random_expr_paper's verbatim if-chain, which must stay byte-identical):
# None = unary; ("int", lo, hi) = numeric constant; ("lit", lo, hi) = random letter literal.
OP_ARGS = {
    "swap_pairs": None, "rotate_halves": None, "double_vowels": None, "count_prefix": None,
    "dedup_chars": None, "interleave_reverse": None, "halve_string": None,
    "wrap_brackets": ("int", 1, 3), "caesar_back": ("int", 1, 5), "repeat_first": ("int", 2, 4),
    "mark_vowels": None, "zigzag": None, "move_max_end": None,
    "upper_vowels": None, "remove_consonants": None, "double_middle": None, "strip_edges": None,
    "letters_to_digits": None, "append_length": None, "sandwich": ("lit", 1, 2), "every_other": None,
    "repeat_last": ("int", 2, 4), "reverse_pairs": None, "sort_desc": None, "swap_ends": None,
}

# Length-preserving ops that take a numeric constant.
LENPRES_PARAM = {"rotate_str", "shift_chars", "while_rotate"}

# ---------------------------------------------------------------------------
# Pool registry
# ---------------------------------------------------------------------------

# paper50: the paper pool plus the 25 extension ops (13 -> train, 12 -> eval): n-scaling test
# of the O(#ops) claim (RESULTS_PROVENANCE "H0/H1 RESULTS" -> next step 1).
PAPER50_NEW_TRAIN = ["swap_pairs", "rotate_halves", "double_vowels", "count_prefix", "dedup_chars", "interleave_reverse", "halve_string", "wrap_brackets", "caesar_back", "repeat_first", "mark_vowels", "zigzag", "move_max_end"]
PAPER50_NEW_EVAL = ["upper_vowels", "remove_consonants", "double_middle", "strip_edges", "letters_to_digits", "append_length", "sandwich", "every_other", "repeat_last", "reverse_pairs", "sort_desc", "swap_ends"]
PAPER50_TRAIN_SET = {**PAPER_TRAIN_SET, **{n: ALL_OPS[n] for n in PAPER50_NEW_TRAIN}}
PAPER50_EVAL_SET = {**PAPER_EVAL_SET, **{n: ALL_OPS[n] for n in PAPER50_NEW_EVAL}}
PAPER50_ALL_SET = {**PAPER50_TRAIN_SET, **PAPER50_EVAL_SET}

POOLS = {
    "paper": {"train": PAPER_TRAIN_SET, "eval": PAPER_EVAL_SET, "all": PAPER_ALL_SET},
    "paper50": {"train": PAPER50_TRAIN_SET, "eval": PAPER50_EVAL_SET, "all": PAPER50_ALL_SET},
    "lenpres": {"train": LENPRES_TRAIN, "eval": LENPRES_EVAL, "all": LENPRES_ALL},
}


def get_ops(pool, split):
    """Return the ``{name: fn}`` dict for a pool/split.

    pool  in {"paper", "lenpres"}; split in {"train", "eval", "all"}.
    Stage 1 (atomic-skill learning) typically uses split="all".
    """
    if pool not in POOLS:
        raise ValueError(f"unknown pool {pool!r}; choices: {list(POOLS)}")
    if split not in POOLS[pool]:
        raise ValueError(f"unknown split {split!r}; choices: {list(POOLS[pool])}")
    return POOLS[pool][split]


if __name__ == "__main__":
    for pool, splits in POOLS.items():
        print(f"[{pool}]")
        for split, d in splits.items():
            print(f"  {split:6s} ({len(d):2d}): {sorted(d)}")
    assert set(LENPRES_NAMES) <= set(PAPER_ALL_SET), "lenpres must be subset of paper"
    assert set(LENPRES_TRAIN) | set(LENPRES_EVAL) == set(LENPRES_ALL)
    assert not (set(LENPRES_TRAIN) & set(LENPRES_EVAL)), "train/eval must be disjoint"
    print("OK: lenpres is a disjoint-split subset of the paper pool")
