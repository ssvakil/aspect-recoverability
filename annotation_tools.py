"""
Annotation sampler and scorer.

WHAT THIS MEASURES AND WHY IT MATTERS
    The density bound reads j <= Rm/T. R and T are known; m is not, and every
    single-number statement in the manuscript silently sets m = 1. This script
    replaces that assumption with a measurement.

    The same annotation validates the lexicon, which the protocol required and
    which was never done. One annotation pass closes both gaps, because the
    labels needed are identical: which aspects does this review actually
    mention?

DEFINITION OF m, FIXED HERE BEFORE ANY LABELLING
    m is the mean number of DISTINCT aspects a review mentions. A review that
    discusses battery life twice contributes one, not two. A review mentioning
    no aspect in the taxonomy contributes zero and is included in the mean;
    excluding such reviews would inflate m and is the most likely way to get
    this measurement wrong.

    Two means are reported because they answer different questions:
      m_all      over every sampled review, including those naming no aspect
      m_nonzero  over reviews naming at least one
    The bound uses m_all, since the denominator of R already counts every
    review in the panel.

BLINDING
    The sheet does not show lexicon output. An annotator who sees the machine
    label agrees with it more often, and the resulting kappa measures
    suggestibility rather than agreement.

USAGE
    python annotation_tools.py --selftest
    python annotation_tools.py sample --scan 500000 --n 300
    python annotation_tools.py score --sheet annotation_sheet_filled.csv
    python annotation_tools.py score --sheet a.csv --sheet2 b.csv
"""

import argparse
import json
import sys
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
sys.path.insert(0, "src")

from feasibility_pilot import PILOT_ASPECTS, tag_aspects       # noqa: E402
from category_shock_run import load_stream, build_balanced      # noqa: E402

ASPECTS = sorted(PILOT_ASPECTS)


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------

def stratified_sample(df, n=300, strata=("app_category",), seed=0):
    """
    Draw n rows spread across strata as evenly as the data allow.

    Proportional allocation would give the largest categories most of the
    sample and leave small ones with none, which defeats the purpose: we want
    to see whether m varies across categories, and that needs coverage, not
    representativeness. Allocation is therefore as equal as possible, with
    remainder distributed to the largest strata. The consequence is that the
    sample mean is not an unbiased estimate of the panel mean unless reweighted,
    and `score` reports both the unweighted and the reweighted figure.
    """
    df = df.dropna(subset=["review"]).copy()
    if df.empty:
        return df
    groups = list(df.groupby(list(strata)))
    if not groups:
        return df.head(0)

    base, extra = divmod(n, len(groups))
    sizes = {k: base for k, _ in groups}
    for k, g in sorted(groups, key=lambda kv: -len(kv[1]))[:extra]:
        sizes[k] += 1

    rng = np.random.default_rng(seed)
    picked, shortfall = [], 0
    for k, g in groups:
        want = sizes[k]
        take = min(want, len(g))
        shortfall += want - take
        if take:
            picked.append(g.sample(take, random_state=int(rng.integers(1 << 31))))
    out = pd.concat(picked) if picked else df.head(0)

    # redistribute any shortfall from strata that were too small
    if shortfall and len(out) < n:
        rest = df.drop(index=out.index, errors="ignore")
        if len(rest):
            out = pd.concat([out, rest.sample(min(shortfall, len(rest)),
                                              random_state=seed)])
    return out.sample(frac=1, random_state=seed).reset_index(drop=True)


def build_sheet(sample, path="annotation_sheet.csv"):
    """
    Write a blind annotation sheet: one row per review, one column per aspect,
    to be filled with 1 or 0. No lexicon output is included.
    """
    sheet = pd.DataFrame({
        "id": range(1, len(sample) + 1),
        "category": sample["app_category"].values,
        "month": sample["month"].astype(str).values if "month" in sample else "",
        "review": sample["review"].values,
    })
    for a in ASPECTS:
        sheet[a] = ""
    sheet["none_of_these"] = ""
    sheet.to_csv(path, index=False)

    guide = path.replace(".csv", "_INSTRUCTIONS.md")
    with open(guide, "w") as f:
        f.write(INSTRUCTIONS)
    return sheet, guide


INSTRUCTIONS = f"""# Annotation instructions

Mark 1 if the review says something about the aspect, 0 otherwise. Leave
nothing blank. If a review mentions none of the aspects, mark `none_of_these`
as 1 and every aspect column 0.

## Aspects

{chr(10).join('- **' + a + '**' for a in ASPECTS)}

## Rules, in order of how often they matter

1. **Mention, not sentiment.** "Battery is fine" and "battery is terrible" both
   count as a battery mention. We are measuring what reviews talk about, not
   what they feel.

2. **Distinct aspects only.** A review complaining about battery three times
   still counts as one battery mention.

3. **The review must say it.** Do not infer. "This app is bad" is not a quality
   mention unless quality is what the reviewer is describing. When you find
   yourself constructing an argument for why a mention is present, mark 0.

4. **Some aspects rarely apply to apps.** `delivery` and `packaging` come from
   a taxonomy built for physical goods. Mark them 0 unless the review really
   discusses them, which for most app reviews it will not. Do not stretch them
   to mean "download speed" or "app size".

5. **A review can mention several aspects.** Mark all that apply. This is the
   whole point of the exercise: the mean number of aspects per review is the
   quantity being measured.

6. **Do not skip short reviews.** "Good app" mentions nothing and is a real
   zero. Dropping such rows would inflate the result.

## Two annotators

If two people annotate, work from identical copies and do not confer until
both are finished. Agreement computed after discussion measures the discussion.

## What this is for

The mean aspects per review, m, enters a bound that determines whether an
aspect-level time series analysis is possible at all. Your labels also serve as
the reference against which an automated extractor is scored.
"""


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def parse_sheet(sheet):
    """Extract the label matrix, validating that it was filled properly."""
    problems = []
    missing = [a for a in ASPECTS if a not in sheet.columns]
    if missing:
        raise ValueError(f"sheet is missing aspect columns: {missing}")

    labels = sheet[ASPECTS].apply(pd.to_numeric, errors="coerce")
    blank = int(labels.isna().sum().sum())
    if blank:
        problems.append(f"{blank} blank or non-numeric cells treated as 0")
    labels = labels.fillna(0).astype(int).clip(0, 1)

    if "none_of_these" in sheet.columns:
        none = pd.to_numeric(sheet["none_of_these"], errors="coerce").fillna(0)
        conflict = int(((none == 1) & (labels.sum(axis=1) > 0)).sum())
        if conflict:
            problems.append(f"{conflict} rows marked none_of_these yet carry aspects")
    return labels, problems


def estimate_m(labels):
    """Mean distinct aspects per review, both including and excluding zeros."""
    per_review = labels.sum(axis=1)
    n_zero = int((per_review == 0).sum())
    nonzero = per_review[per_review > 0]
    return dict(
        n=int(len(per_review)),
        m_all=float(per_review.mean()),
        m_nonzero=float(nonzero.mean()) if len(nonzero) else float("nan"),
        zero_aspect_reviews=n_zero,
        zero_share=float(n_zero / len(per_review)) if len(per_review) else float("nan"),
        max_aspects=int(per_review.max()) if len(per_review) else 0,
        distribution=Counter(per_review.tolist()),
    )


def cohen_kappa(a, b):
    """
    Cohen's kappa for two binary label vectors.

    Returns NaN when one rater used a single class throughout: kappa is
    undefined there, and reporting 0 would suggest chance agreement was
    measured when it was not.
    """
    a, b = np.asarray(a, dtype=int), np.asarray(b, dtype=int)
    n = len(a)
    if n == 0:
        return float("nan")
    po = float((a == b).mean())
    pa1, pb1 = a.mean(), b.mean()
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    if abs(1 - pe) < 1e-12:
        return float("nan")
    return (po - pe) / (1 - pe)


def score_lexicon(sheet, labels):
    """Per-aspect agreement between the human labels and the lexicon."""
    machine = pd.DataFrame(
        [{a: int(a in tag_aspects(t)) for a in ASPECTS} for t in sheet["review"]],
        index=labels.index)
    rows = []
    for a in ASPECTS:
        h, mch = labels[a].values, machine[a].values
        tp = int(((h == 1) & (mch == 1)).sum())
        fp = int(((h == 0) & (mch == 1)).sum())
        fn = int(((h == 1) & (mch == 0)).sum())
        rows.append(dict(
            aspect=a, human=int(h.sum()), lexicon=int(mch.sum()),
            tp=tp, fp=fp, fn=fn,
            precision=tp / (tp + fp) if tp + fp else float("nan"),
            recall=tp / (tp + fn) if tp + fn else float("nan"),
            kappa=cohen_kappa(h, mch)))
    return pd.DataFrame(rows), machine


def bound_with_m(m, R_values=(("MobileRec category", 33.9), ("Amazon product", 6.9)),
                 T_values=(10, 20, 30)):
    """The density bound evaluated at a measured m rather than assumed."""
    rows = []
    for name, R in R_values:
        for T in T_values:
            rows.append(dict(panel=name, R=R, T=T, m=m, j_max=R * m / T,
                             aspects_supported=int(R * m / T)))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------

def cmd_sample(args):
    print(f"Streaming up to {args.scan:,} interactions...")
    df = load_stream(args.scan)
    bal, n_apps = build_balanced(df, args.presence)
    print(f"Balanced panel: {n_apps:,} apps, {len(bal):,} reviews")

    sample = stratified_sample(bal, n=args.n, seed=args.seed)
    sheet, guide = build_sheet(sample, args.out)
    print(f"\nSampled {len(sheet)} reviews across "
          f"{sheet['category'].nunique()} categories")
    print(sheet["category"].value_counts().head(10).to_string())
    print(f"\nWrote: {args.out}")
    print(f"Wrote: {guide}")
    print("\nFill the aspect columns with 1 or 0, then run:")
    print(f"  python annotation_tools.py score --sheet {args.out}")


def cmd_score(args):
    sheet = pd.read_csv(args.sheet)
    labels, problems = parse_sheet(sheet)
    if problems:
        print("Sheet issues:")
        for p in problems:
            print(f"  - {p}")

    est = estimate_m(labels)
    print(f"\n{'=' * 56}\nm, mean distinct aspects per review\n{'=' * 56}")
    print(f"  reviews annotated      {est['n']}")
    print(f"  m_all                  {est['m_all']:.3f}   <- use this in the bound")
    print(f"  m_nonzero              {est['m_nonzero']:.3f}")
    print(f"  reviews naming none    {est['zero_aspect_reviews']} "
          f"({est['zero_share']:.1%})")
    print(f"  most aspects in one    {est['max_aspects']}")
    print("  distribution:", dict(sorted(est["distribution"].items())))

    print(f"\n{'=' * 56}\nDensity bound at the measured m\n{'=' * 56}")
    print(bound_with_m(est["m_all"]).to_string(index=False,
                                               float_format=lambda v: f"{v:.2f}"))

    print(f"\n{'=' * 56}\nLexicon against human labels\n{'=' * 56}")
    per_aspect, machine = score_lexicon(sheet, labels)
    print(per_aspect.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    overall = cohen_kappa(labels.values.ravel(), machine.values.ravel())
    print(f"\n  pooled kappa across all aspect decisions: {overall:.3f}")
    if not np.isnan(overall):
        verdict = ("substantial" if overall >= 0.6 else
                   "moderate" if overall >= 0.4 else "poor")
        print(f"  agreement: {verdict}")
        if overall < 0.6:
            print("  Below the 0.6 the protocol required. The lexicon measure")
            print("  should stay out of the main results.")

    result = dict(m=est, pooled_kappa=None if np.isnan(overall) else overall,
                  per_aspect=per_aspect.to_dict(orient="records"))

    if args.sheet2:
        sheet2 = pd.read_csv(args.sheet2)
        labels2, _ = parse_sheet(sheet2)
        if len(labels2) != len(labels):
            print("\n  second sheet has a different row count; skipping")
        else:
            print(f"\n{'=' * 56}\nInter-annotator agreement\n{'=' * 56}")
            ks = {a: cohen_kappa(labels[a].values, labels2[a].values)
                  for a in ASPECTS}
            for a, k in sorted(ks.items(), key=lambda kv: -(kv[1] if kv[1] == kv[1] else -9)):
                print(f"  {a:<14} {k:.3f}" if k == k else f"  {a:<14} undefined")
            pooled = cohen_kappa(labels.values.ravel(), labels2.values.ravel())
            print(f"\n  pooled inter-annotator kappa: {pooled:.3f}")
            est2 = estimate_m(labels2)
            print(f"  m_all annotator 1: {est['m_all']:.3f}, "
                  f"annotator 2: {est2['m_all']:.3f}")
            result["inter_annotator"] = dict(
                pooled=pooled, per_aspect={k: (None if v != v else v)
                                           for k, v in ks.items()},
                m_all_2=est2["m_all"])

    with open(args.out, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nSaved: {args.out}")


# ---------------------------------------------------------------------------

def _selftest():
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    print("Self-tests for annotation_tools:\n")
    print("Sampling:")

    df = pd.DataFrame({
        "app_category": ["A"] * 100 + ["B"] * 50 + ["C"] * 3,
        "review": ["text"] * 153,
        "month": ["2020-01"] * 153,
    })
    s = stratified_sample(df, n=30, seed=0)
    check("sample reaches the requested size", len(s) == 30, f"(got {len(s)})")
    check("every stratum is represented", s["app_category"].nunique() == 3,
          f'(got {s["app_category"].nunique()})')
    counts = s["app_category"].value_counts()
    check("a tiny stratum is not over-drawn", counts.get("C", 0) <= 3,
          f'(got {counts.get("C", 0)})')
    check("allocation is near-equal, not proportional",
          counts["A"] < 20, f'(A got {counts["A"]} of 30)')

    s2 = stratified_sample(df, n=30, seed=0)
    check("sampling is reproducible from the seed",
          list(s["review"].index) == list(s2["review"].index))

    # asking for more than exists must not loop or duplicate
    small = pd.DataFrame({"app_category": ["A"] * 5, "review": ["x"] * 5,
                          "month": ["2020-01"] * 5})
    s3 = stratified_sample(small, n=50)
    check("oversized request is capped at the data", len(s3) == 5,
          f"(got {len(s3)})")

    print("\nm estimation:")
    lab = pd.DataFrame([
        {a: 0 for a in ASPECTS},                       # names nothing
        {**{a: 0 for a in ASPECTS}, "battery": 1},     # one aspect
        {**{a: 0 for a in ASPECTS}, "battery": 1, "price": 1},   # two
    ])
    est = estimate_m(lab)
    check("m_all includes reviews naming nothing",
          abs(est["m_all"] - 1.0) < 1e-9, f'({est["m_all"]})')
    check("m_nonzero excludes them",
          abs(est["m_nonzero"] - 1.5) < 1e-9, f'({est["m_nonzero"]})')
    check("zero-aspect reviews are counted", est["zero_aspect_reviews"] == 1)
    check("m_all is never above m_nonzero", est["m_all"] <= est["m_nonzero"])

    # THE KEY PROPERTY: dropping empty reviews inflates m, which is the
    # easiest way to get this measurement wrong
    est_dropped = estimate_m(lab[lab.sum(axis=1) > 0])
    check("dropping empty reviews inflates m", est_dropped["m_all"] > est["m_all"],
          f'({est_dropped["m_all"]:.2f} vs {est["m_all"]:.2f})')

    print("\nKappa:")
    check("identical labels give kappa 1",
          abs(cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) - 1.0) < 1e-9)
    check("opposite labels give negative kappa",
          cohen_kappa([1, 1, 0, 0], [0, 0, 1, 1]) < 0)
    k = cohen_kappa([1, 1, 0, 0, 1, 0], [1, 0, 0, 0, 1, 1])
    check("partial agreement lies between", -1 < k < 1, f"({k:.3f})")
    check("constant rater gives undefined, not zero",
          np.isnan(cohen_kappa([1, 1, 1, 1], [1, 1, 1, 1])),
          f"({cohen_kappa([1,1,1,1],[1,1,1,1])})")
    check("empty input gives NaN", np.isnan(cohen_kappa([], [])))

    print("\nSheet handling:")
    good = pd.DataFrame({"review": ["battery great", "nothing here"],
                         **{a: [0, 0] for a in ASPECTS}})
    good.loc[0, "battery"] = 1
    good["none_of_these"] = [0, 1]
    lb, pr = parse_sheet(good)
    check("clean sheet raises no problems", pr == [], f"({pr})")
    check("labels parse to the right shape", lb.shape == (2, len(ASPECTS)))

    blanks = good.copy()
    blanks["price"] = blanks["price"].astype(object)
    blanks.loc[1, "price"] = ""
    _, pr2 = parse_sheet(blanks)
    check("blank cells are reported", any("blank" in p for p in pr2), f"({pr2})")

    bad = good.copy(); bad.loc[1, "battery"] = 1
    _, pr3 = parse_sheet(bad)
    check("none_of_these conflict is reported",
          any("none_of_these" in p for p in pr3), f"({pr3})")

    missing_col = good.drop(columns=["battery"])
    try:
        parse_sheet(missing_col)
        check("missing aspect column raises", False)
    except ValueError:
        check("missing aspect column raises", True)

    print("\nLexicon scoring:")
    sheet = pd.DataFrame({"review": ["battery lasts long", "price is high",
                                     "nothing relevant here"]})
    labels = pd.DataFrame([{a: 0 for a in ASPECTS} for _ in range(3)])
    labels.loc[0, "battery"] = 1
    labels.loc[1, "price"] = 1
    per, machine = score_lexicon(sheet, labels)
    check("scoring covers every aspect", len(per) == len(ASPECTS))
    brow = per[per["aspect"] == "battery"].iloc[0]
    check("lexicon agreement is detected on a clear case", brow["tp"] == 1,
          f'(tp={brow["tp"]})')
    check("counts are consistent",
          bool((per["tp"] + per["fn"] == per["human"]).all()))

    print("\nBound at a measured m:")
    b = bound_with_m(2.0)
    mob30 = b[(b.panel == "MobileRec category") & (b["T"] == 30)].iloc[0]
    check("bound scales linearly with m",
          abs(mob30["j_max"] - 33.9 * 2 / 30) < 1e-9, f'({mob30["j_max"]:.3f})')
    check("a larger m supports more aspects",
          bound_with_m(3.0).iloc[0]["j_max"] > bound_with_m(1.0).iloc[0]["j_max"])
    amz = b[(b.panel == "Amazon product") & (b["T"] == 30)].iloc[0]
    check("Amazon stays below one aspect even at m = 2",
          amz["j_max"] < 1, f'({amz["j_max"]:.3f})')

    print()
    if failures:
        print(f"{len(failures)} test(s) FAILED: {failures}")
        return 1
    print("All annotation_tools self-tests passed.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    ap.add_argument("--selftest", action="store_true")

    p1 = sub.add_parser("sample")
    p1.add_argument("--scan", type=int, default=500000)
    p1.add_argument("--presence", type=float, default=0.75)
    p1.add_argument("--n", type=int, default=300)
    p1.add_argument("--seed", type=int, default=0)
    p1.add_argument("--out", default="annotation_sheet.csv")

    p2 = sub.add_parser("score")
    p2.add_argument("--sheet", required=True)
    p2.add_argument("--sheet2")
    p2.add_argument("--out", default="annotation_results.json")

    args = ap.parse_args()
    if args.selftest or args.cmd is None:
        sys.exit(_selftest())
    if args.cmd == "sample":
        cmd_sample(args)
    else:
        cmd_score(args)


if __name__ == "__main__":
    main()
