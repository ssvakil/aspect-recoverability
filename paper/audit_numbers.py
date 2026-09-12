"""
Numeric audit of the manuscript.

WHY THIS EXISTS
    A 25-page paper with a dozen interdependent parameters has roughly sixty to
    a hundred places where a number appears. Changing one parameter by hand
    means visiting all of them, and the record shows that does not happen
    reliably: correcting R in one section left it stale in seven others, and
    moving from 30 to 999 bootstrap replicates left the old p-values in a
    figure while the text called them superseded.

    This script does not fix anything. It reads the manuscript, extracts the
    numbers we care about, and reports where the text disagrees with the values
    the analysis produced. Anything it flags is either a stale figure or a
    number that needs a comment explaining why it differs.

WHAT IT CANNOT DO
    It checks values it knows about. A number nobody thought to register here
    is invisible to it, so a clean report is evidence of consistency on the
    registered set, not proof of correctness.

USAGE
    python audit_numbers.py --tex manuscript.tex
"""

import argparse
import re
import sys

# ---------------------------------------------------------------------------
# Canonical values. Each is the figure the analysis produced, with the command
# that produced it. If a value changes, it changes here and the audit finds
# every place the text still carries the old one.
# ---------------------------------------------------------------------------

CANON = {
    # balanced_panel_check.py --scan 500000
    "R_mobile":        (34.8,   "74,780 / 2,150 balanced-panel category-months"),
    "R_amazon":        (6.9,    "82,041 / 11,925 product-months"),
    "denom_75":        (2150,   "logged category-months at 75% presence"),
    "denom_50":        (2291,   "logged category-months at 50% presence"),
    "qualifying_75":   (955,    "qualifying category-months at 75% presence"),
    "share_75":        (44.4,   "955 / 2,150"),
    "share_unbal":     (77.8,   "1,788 / 2,299 unbalanced, same window"),
    "apps_75":         (657,    "apps retained at 75% presence"),
    "rows_75":         (74780,  "reviews in the balanced panel"),
    "categories_75":   (46,     "categories surviving at 75% presence"),

    # followup_analyses.py --reps 999
    "boot_reps":       (999,    "bootstrap replicates"),
    "star_observed":   (23,     "threshold-rule detections, star rating"),
    "star_null_mean":  (28.39,  "block bootstrap null mean, star"),
    "star_null_sd":    (3.77,   "block bootstrap null SD, star"),
    "star_ratio":      (0.81,   "23 / 28.39"),
    "star_p":          (0.95,   "empirical p, star, threshold rule"),
    "lex_observed":    (29,     "threshold-rule detections, lexicon"),
    "lex_null_mean":   (26.19,  "block bootstrap null mean, lexicon"),
    "lex_ratio":       (1.11,   "29 / 26.19"),
    "pelt_observed":   (6,      "PELT change points, star"),
    "pelt_null_mean":  (1.77,   "PELT null mean, star"),
    "pelt_ratio":      (3.40,   "6 / 1.77"),
    "pelt_p":          (0.015,  "empirical p, PELT, star, uncorrected"),
    "pelt_p_bonf":     (0.060,  "0.015 x 4 tests"),
    "km_median_star":  (3.0,    "Kaplan-Meier median, star"),
    "km_median_lex":   (15.0,   "Kaplan-Meier median, lexicon"),

    # aspect_level_run.py
    "aspect_cells":    (7084,   "non-empty category x aspect x month cells"),
    "aspect_possible": (22080,  "46 x 10 x 48"),
    "aspect_qualifying": (0,    "aspect cells reaching the threshold"),

    # cohort rates
    "rate_item":       (0.059,  "user-item repeat rate, percent"),
    "rate_category":   (1.638,  "user-category repeat rate, percent"),
    "rate_aspect":     (1.390,  "user-aspect repeat rate, percent"),
    "amazon_repeat":   (0.159,  "Amazon user-product repeat rate, percent"),

    # positive control
    "pc_fpr":          (1.00,   "false positive rate per clean series"),
    "pc_power_2sd":    (0.67,   "power at 2 SD, 3 months"),

    # power arithmetic
    "events_hr20":     (65,     "Schoenfeld events for HR = 2.0"),
    "events_hr15":     (191,    "Schoenfeld events for HR = 1.5"),
    "min_detectable_hr": (3.50, "smallest HR detectable with 20 events"),
}

# Values that must NOT appear: superseded figures from earlier runs.
FORBIDDEN = {
    "33.9":   "R computed on the 2,208 theoretical maximum; use 34.8",
    "1.13m":  "bound at the old R; use 1.16m",
    "3.39m":  "bound at the old R; use 3.48m",
    "2{,}151": "denominator recovered by division; the logged value is 2,150",
    "27.8":   "null mean from the 30-replicate run; use 28.39",
    "30 replicates": "superseded by 999",
    "z = -1.33": "normal approximation from the 30-replicate run",
}


def strip_comments(tex):
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", ln) for ln in tex.splitlines())


def find_forbidden(tex):
    """Superseded values still present outside an explicit 'earlier version' note."""
    hits = []
    for bad, why in FORBIDDEN.items():
        for m in re.finditer(re.escape(bad), tex):
            # A generous window: the sentence that excuses a superseded value
            # often begins well before the value itself.
            ctx = tex[max(0, m.start() - 600):m.end() + 200]
            excused = any(p in ctx for p in
                          ("earlier version", "superseded", "an earlier draft",
                           "previously", "we once", "old"))
            hits.append(dict(value=bad, reason=why, excused=excused,
                             context=" ".join(ctx.split())[:150]))
    return hits


def check_present(tex):
    """Canonical values that the text should carry somewhere."""
    missing = []
    for key, (val, src) in CANON.items():
        pats = []
        if isinstance(val, int):
            pats += [rf"\b{val}\b", rf"\b{val:,}\b".replace(",", r"\{,\}")]
        else:
            # A value may be typeset with or without trailing zeros: 3.4, 3.40,
            # 15, 15.0 are the same number and only one of them is searched for
            # unless the pattern allows both.
            s = f"{val}"
            trimmed = s.rstrip("0").rstrip(".")
            for form in {s, trimmed, f"{val:.2f}", f"{val:.3f}"}:
                pats.append(re.escape(form))
            if float(val).is_integer():
                pats.append(rf"\b{int(val)}\b")
        if not any(re.search(p, tex) for p in pats):
            missing.append((key, val, src))
    return missing


def derived_checks():
    """Relationships that must hold among the canonical values."""
    c = {k: v for k, (v, _) in CANON.items()}
    out = []

    def rel(name, lhs, rhs, tol=0.02):
        out.append((name, abs(lhs - rhs) <= tol, f"{lhs:.4f} vs {rhs:.4f}"))

    rel("share_75 = qualifying / denominator",
        c["share_75"] / 100, c["qualifying_75"] / c["denom_75"], 0.001)
    rel("R_mobile = rows / denominator",
        c["R_mobile"], c["rows_75"] / c["denom_75"], 0.05)
    rel("star_ratio = observed / null", c["star_ratio"],
        c["star_observed"] / c["star_null_mean"], 0.01)
    rel("lex_ratio = observed / null", c["lex_ratio"],
        c["lex_observed"] / c["lex_null_mean"], 0.01)
    rel("pelt_ratio = observed / null", c["pelt_ratio"],
        c["pelt_observed"] / c["pelt_null_mean"], 0.02)
    rel("Bonferroni = p x 4", c["pelt_p_bonf"], c["pelt_p"] * 4, 0.001)
    rel("aspect cells below possible",
        1.0 if c["aspect_cells"] < c["aspect_possible"] else 0.0, 1.0, 0.0)
    rel("category rate exceeds item rate",
        1.0 if c["rate_category"] > c["rate_item"] else 0.0, 1.0, 0.0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex", default="manuscript.tex")
    args = ap.parse_args()

    tex = strip_comments(open(args.tex).read())
    problems = 0

    print("=" * 68)
    print("Internal consistency of the canonical values")
    print("=" * 68)
    for name, ok, detail in derived_checks():
        print(f"  {'OK  ' if ok else 'FAIL'}  {name}   {detail}")
        if not ok:
            problems += 1

    print("\n" + "=" * 68)
    print("Superseded values still in the text")
    print("=" * 68)
    hits = find_forbidden(tex)
    unexcused = [h for h in hits if not h["excused"]]
    if not hits:
        print("  none found")
    for h in hits:
        tag = "noted" if h["excused"] else "STALE"
        print(f"  {tag}  {h['value']}: {h['reason']}")
        if not h["excused"]:
            print(f"         ...{h['context']}...")
    problems += len(unexcused)

    print("\n" + "=" * 68)
    print("Canonical values absent from the text")
    print("=" * 68)
    missing = check_present(tex)
    if not missing:
        print("  none: every registered value appears")
    for key, val, src in missing:
        print(f"  ABSENT  {key} = {val}   ({src})")

    print("\n" + "=" * 68)
    print(f"{problems} problem(s) requiring attention")
    print("Registered values:", len(CANON),
          "| this audit cannot see numbers it does not know about")
    print("=" * 68)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
