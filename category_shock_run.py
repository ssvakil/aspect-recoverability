"""
Category-level shock detection on a balanced MobileRec panel.

WHAT CHANGED FROM THE ORIGINAL DESIGN
    The unit of analysis is now (app_category, month), not (product, aspect,
    month). This is a different research question and the pre-registration does
    not cover it. Treat everything here as exploratory until a new protocol is
    written and locked.

WHAT IS STILL NOT POSSIBLE
    Cohort recovery. Repeat user-app pairs run at 0.06%, so sentiment returning
    after a shock cannot be attributed to the original reviewers rather than to
    different people arriving. Any recovery measured here is population-level
    only, and the manuscript must say so rather than implying otherwise.

WHAT A CATEGORY SHOCK IS NOT
    A drop averaged over hundreds of apps is not a product defect. Plausible
    alternative causes include store ranking changes, OS releases, seasonal
    effects, and shifts in which apps dominate the category. None of these are
    perception change. Alternative explanations must be addressed before any
    causal reading.

USAGE
    python category_shock_run.py --selftest
    python category_shock_run.py --scan 500000 --presence 0.75
"""

import argparse
import sys

import pandas as pd
import numpy as np

sys.path.insert(0, ".")
sys.path.insert(0, "src")

from feasibility_pilot import (          # noqa: E402
    detect_shocks, crude_polarity, tag_aspects, censoring_summary,
    events_required, events_per_parameter, epp_verdict, null_comparison,
    sensitivity_grid, BASELINE_MONTHS, SHOCK_MIN_MONTHS,
)

SOURCE = "hf://datasets/recmeapp/mobilerec/interactions/mobilerec_final.csv"
WINDOW_START = "2018-01"
WINDOW_END = "2021-12"
MIN_REVIEWS_PER_MONTH = 30


def load_stream(scan):
    from datasets import load_dataset
    ds = load_dataset("csv", data_files=SOURCE, split="train", streaming=True)
    return pd.DataFrame([r for _, r in zip(range(scan), ds)])


def build_balanced(df, presence=0.75):
    """Restrict to apps present across most of the window."""
    d = df.copy()
    d["month"] = pd.to_datetime(d["formated_date"], errors="coerce").dt.to_period("M")
    d = d[d["month"].notna()]
    d = d[(d["month"] >= pd.Period(WINDOW_START)) & (d["month"] <= pd.Period(WINDOW_END))]
    if d.empty:
        return d, 0
    n_months = d["month"].nunique()
    pres = d.groupby("app_package")["month"].nunique()
    keep = pres[pres >= n_months * presence].index
    return d[d["app_package"].isin(keep)].copy(), len(keep)


def category_series(d, use_rating=False, min_reviews=MIN_REVIEWS_PER_MONTH):
    """
    Monthly sentiment per category.

    Two measures are built deliberately. `rating` is objective and needs no
    model; `polarity` comes from the pilot lexicon and is crude. If the two
    disagree about where shocks fall, the lexicon is the suspect, not the data.
    """
    d = d.copy()
    if "month" not in d.columns:
        d["month"] = pd.to_datetime(d["formated_date"], errors="coerce").dt.to_period("M")
        d = d[d["month"].notna()]
    if use_rating:
        d["value"] = pd.to_numeric(d["rating"], errors="coerce")
    else:
        d["value"] = d["review"].map(crude_polarity)
    d = d[d["value"].notna()]
    g = d.groupby(["app_category", "month"]).agg(
        value=("value", "mean"), n=("value", "size")).reset_index()
    return g[g["n"] >= min_reviews].reset_index(drop=True)


def contiguous_runs(months, values):
    segs, cur, prev = [], [], None
    for m, v in zip(months, values):
        if prev is not None and (m - prev).n != 1:
            if cur:
                segs.append(np.array(cur))
            cur = []
        cur.append(v)
        prev = m
    if cur:
        segs.append(np.array(cur))
    return segs


def run_detection(series_df, label):
    """Detect shocks in each category's contiguous dense runs."""
    records, segments = [], []
    for cat, g in series_df.groupby("app_category"):
        g = g.sort_values("month")
        for seg in contiguous_runs(g["month"].tolist(), g["value"].tolist()):
            if len(seg) <= BASELINE_MONTHS + SHOCK_MIN_MONTHS:
                continue
            segments.append((cat, label, seg))
            for sh in detect_shocks(seg):
                sh["category"] = cat
                records.append(sh)
    return pd.DataFrame(records), segments


def report(shocks, segments, label):
    print(f"\n{'=' * 60}\nMEASURE: {label}\n{'=' * 60}")
    print(f"Usable category series: {len(segments)}")

    if shocks.empty:
        print("No shocks detected.")
        return

    cs = censoring_summary(shocks)
    print(f"Shock episodes: {cs['total']}")
    print(f"  recovered {cs['recovered']}, non-recovered {cs['non_recovered']}, "
          f"censored {cs['censored']}")
    print(f"  censoring rate: {cs['censoring_rate']:.1%}")

    print("\nBy category:")
    print(pd.crosstab(shocks["category"], shocks["outcome"]).to_string())

    per_cat = shocks.groupby("category").size()
    print(f"\nClustering: {per_cat.size} categories, "
          f"max {per_cat.max()} shocks in one category")
    if per_cat.max() > 1:
        print("  -> cluster-robust SE or a frailty model required")

    n_events = cs["analysable"]
    print(f"\nAnalysable episodes: {n_events}")
    for hr in (1.5, 2.0):
        print(f"  events needed for HR={hr} at 80% power: {events_required(hr):.0f}")
    for k in (3, 6):
        epp = events_per_parameter(n_events, k)
        print(f"  EPP with {k} parameters: {epp:.1f} ({epp_verdict(epp)})")

    print("\nNull comparison (block bootstrap is the honest control):")
    nc = null_comparison(segments, n_reps=30)
    print(f"  observed {nc['observed']}, "
          f"block-bootstrap null {nc['block_mean']:.1f} (sd {nc['block_sd']:.1f}), "
          f"shuffle null {nc['shuffle_mean']:.1f}")
    print(f"  ratio vs block null: {nc['ratio_vs_block']:.2f}")
    if nc["ratio_vs_block"] < 1.5:
        print("  WARNING: observed shocks are close to what the null produces.")
        print("  Detection may be reflecting noise rather than real events.")

    print("\nSensitivity grid:")
    print(sensitivity_grid(segments).to_string(index=False))


def run(scan, presence):
    print(f"Streaming up to {scan:,} interactions...")
    df = load_stream(scan)
    print(f"  loaded {len(df):,} rows")

    bal, n_apps = build_balanced(df, presence)
    print(f"\nBalanced panel at presence >= {presence:.0%}: "
          f"{n_apps:,} apps, {len(bal):,} rows")

    pairs = bal.groupby(["app_package", "uid"]).size()
    print(f"Repeat user-app pairs: {(pairs > 1).mean():.3%} "
          f"-> cohort recovery {'possible' if (pairs > 1).mean() >= 0.02 else 'NOT possible'}")

    for use_rating, label in ((True, "star rating"), (False, "lexicon polarity")):
        series = category_series(bal, use_rating=use_rating)
        print(f"\nCategory-months for {label}: {len(series)}")
        shocks, segments = run_detection(series, label)
        report(shocks, segments, label)


def _selftest():
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    print("Self-tests for category_shock_run:\n")

    months = pd.period_range(WINDOW_START, WINDOW_END, freq="M")

    rows = []
    for m in months:
        for _ in range(40):
            rows.append(dict(app_package="A", app_category="Games",
                             formated_date=f"{m}-15", rating=5,
                             review="great works well", uid="u1"))
    for m in months[:2]:
        for _ in range(40):
            rows.append(dict(app_package="B", app_category="Games",
                             formated_date=f"{m}-15", rating=5,
                             review="great works well", uid="u2"))
    df = pd.DataFrame(rows)

    bal, n = build_balanced(df, 0.9)
    check("transient app excluded", n == 1, f"(got {n})")
    check("persistent app rows kept", len(bal) == len(months) * 40)

    s = category_series(bal, use_rating=True)
    check("series built for one category", len(s) == len(months), f"(got {len(s)})")
    check("mean rating correct", abs(s["value"].iloc[0] - 5.0) < 1e-9)

    thin = pd.DataFrame([dict(app_package="A", app_category="Games",
                              formated_date="2019-05-15", rating=5,
                              review="ok", uid="u1")] * 10)
    check("sparse month dropped", len(category_series(thin, use_rating=True)) == 0)

    # contiguous runs split at gaps
    ms = list(pd.period_range("2020-01", periods=3, freq="M")) + \
         list(pd.period_range("2021-01", periods=3, freq="M"))
    check("gap splits runs", len(contiguous_runs(ms, [1, 2, 3, 4, 5, 6])) == 2)

    # END-TO-END: inject a real shock and confirm it is found
    rows = []
    for i, m in enumerate(months):
        r = 2 if 20 <= i < 26 else 5      # sustained drop then recovery
        for _ in range(40):
            rows.append(dict(app_package="A", app_category="Games",
                             formated_date=f"{m}-15", rating=r,
                             review="x", uid="u1"))
    shocked = pd.DataFrame(rows)
    bal2, _ = build_balanced(shocked, 0.9)
    s2 = category_series(bal2, use_rating=True)
    found, segs = run_detection(s2, "test")
    check("injected shock is detected", len(found) >= 1, f"(got {len(found)})")
    check("segments returned for null testing", len(segs) == 1)

    # and a flat series must yield nothing
    flat = pd.DataFrame([dict(app_package="A", app_category="Games",
                              formated_date=f"{m}-15", rating=5,
                              review="x", uid="u1")
                         for m in months for _ in range(40)])
    b3, _ = build_balanced(flat, 0.9)
    f3, _ = run_detection(category_series(b3, use_rating=True), "test")
    check("flat series yields no shocks", len(f3) == 0, f"(got {len(f3)})")

    print()
    if failures:
        print(f"{len(failures)} test(s) FAILED: {failures}")
        return 1
    print("All category_shock_run self-tests passed.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--scan", type=int, default=500000)
    ap.add_argument("--presence", type=float, default=0.75)
    args = ap.parse_args()
    if args.selftest:
        sys.exit(_selftest())
    run(args.scan, args.presence)


if __name__ == "__main__":
    main()
