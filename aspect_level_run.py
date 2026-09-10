"""
Aspect-level shock detection on the MobileRec balanced category panel.

WHY THIS EXISTS
    The category-level analysis reported earlier measured sentiment over whole
    reviews, not over specific attributes. That is product- and category-level
    sentiment, not aspect-level sentiment, and a study claiming the latter
    cannot rest on the former.

    This script closes that gap directly. It builds (category, aspect, month)
    series from the same balanced panel and asks the same questions: is there
    enough density, and are any detected shocks distinguishable from a block
    bootstrap null?

WHAT TO EXPECT
    Splitting a fixed monthly review volume across k aspects reduces mentions
    per cell. If the whole-review series were marginal, the aspect series will
    be worse. The point of running it is to measure how much worse rather than
    to assert it, and to make the claim in the title one the data support.

USAGE
    python aspect_level_run.py --selftest
    python aspect_level_run.py --scan 500000 --presence 0.75
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
sys.path.insert(0, "src")

from feasibility_pilot import (          # noqa: E402
    detect_shocks, crude_polarity, tag_aspects, censoring_summary,
    events_required, null_comparison, PILOT_ASPECTS,
    BASELINE_MONTHS, SHOCK_MIN_MONTHS, SHOCK_SD,
)
from category_shock_run import (          # noqa: E402
    load_stream, build_balanced, contiguous_runs, WINDOW_START, WINDOW_END,
)

MIN_MENTIONS = 30
SD_LEVELS = (0.75, 1.00, 1.25)
DUR_LEVELS = (2, 3, 4)


def aspect_series(balanced, min_mentions=MIN_MENTIONS):
    """
    Build (category, aspect, month) mean polarity, keeping only cells that
    clear the mention threshold.

    A review mentioning several aspects contributes to each. Mentions are
    therefore not a partition of reviews, and the sum of aspect mentions in a
    month can exceed that month's review count.
    """
    d = balanced.copy()
    if "month" not in d.columns:
        d["month"] = pd.to_datetime(d["formated_date"], errors="coerce").dt.to_period("M")
    d = d[d["month"].notna() & d["review"].notna()]

    rows = []
    for cat, month, text in zip(d["app_category"], d["month"], d["review"]):
        aspects = tag_aspects(text)
        if not aspects:
            continue
        pol = crude_polarity(text)
        for a in aspects:
            rows.append((cat, a, month, pol))

    if not rows:
        return pd.DataFrame(columns=["category", "aspect", "month", "value", "n"])

    long = pd.DataFrame(rows, columns=["category", "aspect", "month", "polarity"])
    agg = long.groupby(["category", "aspect", "month"]).agg(
        value=("polarity", "mean"), n=("polarity", "size")).reset_index()
    agg["qualifies"] = agg["n"] >= min_mentions
    return agg


def density_report(agg):
    """Density of aspect cells, and how it compares with the whole-review case."""
    if agg.empty:
        return dict(cells=0, qualifying=0, share=float("nan"),
                    median_mentions=float("nan"), aspects=0, categories=0)
    return dict(
        cells=int(len(agg)),
        qualifying=int(agg["qualifies"].sum()),
        share=float(agg["qualifies"].mean()),
        median_mentions=float(agg["n"].median()),
        aspects=int(agg["aspect"].nunique()),
        categories=int(agg["category"].nunique()),
    )


def per_aspect_table(agg):
    """Qualifying cells broken down by aspect, so sparsity is not averaged away."""
    if agg.empty:
        return pd.DataFrame()
    t = agg.groupby("aspect").agg(
        cells=("qualifies", "size"),
        qualifying=("qualifies", "sum"),
        median_mentions=("n", "median"),
    )
    t["share"] = t["qualifying"] / t["cells"]
    return t.sort_values("qualifying", ascending=False)


def build_segments(agg):
    """Contiguous qualifying runs per (category, aspect)."""
    if agg.empty:
        return []
    q = agg[agg["qualifies"]]
    segments = []
    for (cat, asp), g in q.groupby(["category", "aspect"]):
        g = g.sort_values("month")
        for seg in contiguous_runs(g["month"].tolist(), g["value"].tolist()):
            if len(seg) > BASELINE_MONTHS + SHOCK_MIN_MONTHS:
                segments.append((f"{cat}/{asp}", "aspect", seg))
    return segments


def run_detection(segments):
    records = []
    for name, _, seg in segments:
        for sh in detect_shocks(seg):
            sh["series"] = name
            records.append(sh)
    return pd.DataFrame(records)


def sensitivity_with_null(segments, n_reps=30, seed=0):
    """
    Sensitivity grid WITH a null comparison in every cell.

    Reporting shock counts across a parameter grid without the corresponding
    null does not establish that no cell yields a signal: a cell with more
    shocks may simply have a more permissive null. Each cell here carries its
    own observed-to-null ratio.
    """
    rng_seed = seed
    rows = []
    for sd in SD_LEVELS:
        for dur in DUR_LEVELS:
            observed = 0
            usable = []
            for name, kind, seg in segments:
                if len(seg) <= BASELINE_MONTHS + dur:
                    continue
                usable.append((name, kind, seg))
                observed += len(detect_shocks(seg, shock_sd=sd, shock_min_months=dur))
            if not usable:
                rows.append(dict(shock_sd=sd, min_months=dur, series=0,
                                 observed=0, null_mean=np.nan, null_sd=np.nan,
                                 ratio=np.nan, z=np.nan))
                continue
            nulls = []
            rng = np.random.default_rng(rng_seed)
            rng_seed += 1
            from feasibility_pilot import block_bootstrap_null
            for _ in range(n_reps):
                total = 0
                for _, _, seg in usable:
                    total += len(detect_shocks(block_bootstrap_null(seg, rng),
                                               shock_sd=sd, shock_min_months=dur))
                nulls.append(total)
            mu, sd_null = float(np.mean(nulls)), float(np.std(nulls))
            rows.append(dict(
                shock_sd=sd, min_months=dur, series=len(usable), observed=observed,
                null_mean=mu, null_sd=sd_null,
                ratio=observed / mu if mu else np.nan,
                z=(observed - mu) / sd_null if sd_null else np.nan,
            ))
    return pd.DataFrame(rows)


def run(scan, presence, out="aspect_level_results.json"):
    print(f"Streaming up to {scan:,} interactions...")
    df = load_stream(scan)
    print(f"  loaded {len(df):,} rows")

    bal, n_apps = build_balanced(df, presence)
    print(f"Balanced panel at presence >= {presence:.0%}: {n_apps:,} apps, "
          f"{len(bal):,} rows, window {WINDOW_START} to {WINDOW_END}")

    print(f"\nAspect taxonomy: {len(PILOT_ASPECTS)} aspects "
          f"({', '.join(sorted(PILOT_ASPECTS))})")

    agg = aspect_series(bal)
    d = density_report(agg)
    print(f"\nAspect cells (category x aspect x month): {d['cells']:,}")
    print(f"  categories {d['categories']}, aspects {d['aspects']}")
    print(f"  median mentions per cell: {d['median_mentions']:.0f}")
    print(f"  cells with >= {MIN_MENTIONS} mentions: {d['qualifying']:,} "
          f"({d['share']:.1%})")

    print("\nPer aspect:")
    t = per_aspect_table(agg)
    if not t.empty:
        print(t.to_string())

    segments = build_segments(agg)
    print(f"\nUsable aspect series (contiguous, long enough): {len(segments)}")

    if not segments:
        print("\nNo aspect series survives the density threshold.")
        print("Aspect-level detection cannot be attempted on this panel.")
        result = dict(density=d, segments=0, shocks=None, note="no usable series")
        with open(out, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nSaved: {out}")
        return result

    shocks = run_detection(segments)
    cs = censoring_summary(shocks)
    print(f"\nShock episodes: {cs['total']} "
          f"(recovered {cs['recovered']}, non-recovered {cs['non_recovered']}, "
          f"censored {cs['censored']})")
    print(f"Analysable: {cs['analysable']}  |  needed for HR=2.0: "
          f"{events_required(2.0):.0f}")

    nc = null_comparison(segments, n_reps=30)
    print(f"\nNull comparison: observed {nc['observed']}, "
          f"block null {nc['block_mean']:.1f} (sd {nc['block_sd']:.1f}), "
          f"ratio {nc['ratio_vs_block']:.2f}")

    print("\nSensitivity grid with per-cell null comparison:")
    grid = sensitivity_with_null(segments)
    print(grid.to_string(index=False))

    result = dict(density=d, segments=len(segments),
                  outcomes=cs, null=nc,
                  grid=grid.to_dict(orient="records"))
    with open(out, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nSaved: {out}")
    return result


# ---------------------------------------------------------------------------

def _selftest():
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    print("Self-tests for aspect_level_run:\n")
    months = pd.period_range(WINDOW_START, WINDOW_END, freq="M")

    # a review mentioning two aspects must contribute to both
    df = pd.DataFrame([dict(app_package="A", app_category="Games",
                            formated_date="2019-05-15",
                            review="battery great but price terrible", rating=3)] * 40)
    agg = aspect_series(df)
    asp = set(agg["aspect"])
    check("multi-aspect review contributes to each aspect",
          {"battery", "price"}.issubset(asp), f"(got {sorted(asp)})")
    check("each aspect cell has the full mention count",
          set(agg["n"]) == {40}, f"(got {sorted(set(agg['n']))})")

    # reviews with no recognised aspect are dropped, not counted as neutral
    plain = pd.DataFrame([dict(app_package="A", app_category="Games",
                               formated_date="2019-05-15",
                               review="fine", rating=4)] * 40)
    check("aspectless reviews produce no cells", aspect_series(plain).empty)

    # THE CENTRAL COMPARISON: splitting across aspects must reduce mentions
    # per cell relative to the whole-review series on the same reviews.
    rows = []
    for m in months[:12]:
        for i in range(60):
            # each review mentions exactly one of three aspects
            a = ["battery lasts", "price expensive", "design looks"][i % 3]
            rows.append(dict(app_package="A", app_category="Games",
                             formated_date=f"{m}-15", review=a, rating=4))
    split = pd.DataFrame(rows)
    agg2 = aspect_series(split)
    per_cell = agg2.groupby("month")["n"].sum().iloc[0]
    max_cell = agg2["n"].max()
    check("aspect split preserves total mentions", per_cell == 60,
          f"(got {per_cell})")
    check("each aspect cell holds a fraction of the month's reviews",
          max_cell < 60, f"(max cell {max_cell} of 60)")
    check("mentions per cell approximately divide by the aspect count",
          abs(max_cell - 20) <= 1, f"(got {max_cell}, expected ~20)")

    # threshold behaviour
    thin = pd.DataFrame([dict(app_package="A", app_category="Games",
                              formated_date="2019-05-15",
                              review="battery lasts", rating=4)] * 10)
    check("cells below the threshold do not qualify",
          not aspect_series(thin)["qualifies"].any())

    # segments require contiguity and minimum length
    rows = []
    for m in list(months[:4]) + list(months[8:14]):
        for _ in range(40):
            rows.append(dict(app_package="A", app_category="Games",
                             formated_date=f"{m}-15", review="battery lasts",
                             rating=4))
    gapped = pd.DataFrame(rows)
    segs = build_segments(aspect_series(gapped))
    check("gap splits series and short runs are dropped", len(segs) == 0,
          f"(got {len(segs)} segments)")

    # sensitivity grid carries a null in every cell
    rows = []
    for i, m in enumerate(months):
        v = 2 if 20 <= i < 26 else 5
        for _ in range(40):
            rows.append(dict(app_package="A", app_category="Games",
                             formated_date=f"{m}-15",
                             review=("battery broke terrible" if v == 2
                                     else "battery great works well"),
                             rating=v))
    shocked = pd.DataFrame(rows)
    segs = build_segments(aspect_series(shocked))
    check("injected aspect shock yields a usable series", len(segs) >= 1,
          f"(got {len(segs)})")
    if segs:
        grid = sensitivity_with_null(segs, n_reps=5)
        check("grid has 9 cells", len(grid) == 9, f"(got {len(grid)})")
        check("every cell carries a null mean",
              grid["null_mean"].notna().all() or (grid["series"] == 0).any())
        lenient = grid[(grid.shock_sd == 0.75) & (grid.min_months == 2)]["observed"].iloc[0]
        strict = grid[(grid.shock_sd == 1.25) & (grid.min_months == 4)]["observed"].iloc[0]
        check("stricter settings find no more shocks", strict <= lenient,
              f"(lenient {lenient}, strict {strict})")

    print()
    if failures:
        print(f"{len(failures)} test(s) FAILED: {failures}")
        return 1
    print("All aspect_level_run self-tests passed.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--scan", type=int, default=500000)
    ap.add_argument("--presence", type=float, default=0.75)
    ap.add_argument("--out", default="aspect_level_results.json")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(_selftest())
    run(args.scan, args.presence, args.out)


if __name__ == "__main__":
    main()
