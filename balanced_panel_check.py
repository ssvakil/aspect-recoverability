"""
Balanced panel check for MobileRec category-level series.

THE QUESTION THIS ANSWERS
    Aggregating to app_category raised qualifying unit-months from 0.2% to
    44.5%. That figure recomputes category membership every month, so it may
    reflect apps entering and leaving the category rather than any change in
    sentiment.

    A shock in a series whose members change monthly is not a shock in
    perception; it is a change in who is being averaged. This script restricts
    to apps present across most of the window and reports what survives.

DECISION RULE, STATED BEFORE RUNNING
    At the 75% presence threshold, the category route is worth pursuing only if
    a usable number of categories retain long continuous dense series. If apps
    collapse to a handful and qualifying months fall far below the unbalanced
    figure, the 44.5% was composition, not signal.

USAGE
    python balanced_panel_check.py --selftest
    python balanced_panel_check.py --scan 500000
"""

import argparse
import sys

import pandas as pd

SOURCE = ("hf://datasets/recmeapp/mobilerec/interactions/mobilerec_final.csv")
WINDOW_START = "2018-01"
WINDOW_END = "2021-12"
MENTION_THRESHOLD = 30


def build_panel(df, presence_threshold, window_start=WINDOW_START,
                window_end=WINDOW_END, threshold=MENTION_THRESHOLD):
    """
    Restrict to apps present in at least `presence_threshold` of the window's
    months, then report category-level density over the survivors.
    """
    d = df.copy()
    d["month"] = pd.to_datetime(d["formated_date"], errors="coerce").dt.to_period("M")
    d = d[d["month"].notna()]
    d = d[(d["month"] >= pd.Period(window_start)) &
          (d["month"] <= pd.Period(window_end))]
    if d.empty:
        return dict(window_months=0, apps_kept=0, rows=0, category_months=0,
                    qualifying=0, share=float("nan"), categories=0,
                    median_months_per_category=0)

    window_months = d["month"].nunique()
    presence = d.groupby("app_package")["month"].nunique()
    kept = presence[presence >= window_months * presence_threshold].index
    b = d[d["app_package"].isin(kept)]

    if b.empty:
        return dict(window_months=window_months, apps_kept=0, rows=0,
                    category_months=0, qualifying=0, share=float("nan"),
                    categories=0, median_months_per_category=0)

    g = b.groupby(["app_category", "month"]).size()
    per_cat = g.groupby(level=0).size()
    return dict(
        window_months=window_months,
        apps_kept=int(len(kept)),
        rows=int(len(b)),
        category_months=int(len(g)),
        qualifying=int((g >= threshold).sum()),
        share=float((g >= threshold).mean()),
        categories=int(per_cat.size),
        median_months_per_category=int(per_cat.median()),
    )


def longest_dense_run(df, presence_threshold, threshold=MENTION_THRESHOLD):
    """
    The binding constraint is not total qualifying months but the longest
    CONTINUOUS run of qualifying months, since shock detection needs a baseline
    window, the shock itself, and a follow-up horizon back to back.
    """
    d = df.copy()
    d["month"] = pd.to_datetime(d["formated_date"], errors="coerce").dt.to_period("M")
    d = d[d["month"].notna()]
    d = d[(d["month"] >= pd.Period(WINDOW_START)) & (d["month"] <= pd.Period(WINDOW_END))]
    if d.empty:
        return pd.DataFrame()

    window_months = d["month"].nunique()
    presence = d.groupby("app_package")["month"].nunique()
    kept = presence[presence >= window_months * presence_threshold].index
    b = d[d["app_package"].isin(kept)]
    if b.empty:
        return pd.DataFrame()

    g = b.groupby(["app_category", "month"]).size()
    rows = []
    for cat, s in g.groupby(level=0):
        s = s.droplevel(0).sort_index()
        best = run = 0
        prev = None
        for m, n in s.items():
            ok = n >= threshold
            contiguous = prev is None or (m - prev).n == 1
            run = run + 1 if (ok and contiguous) else (1 if ok else 0)
            best = max(best, run)
            prev = m
        rows.append(dict(category=cat, months=len(s), longest_dense_run=best))
    return pd.DataFrame(rows).sort_values("longest_dense_run", ascending=False)


def run(scan):
    from datasets import load_dataset

    print(f"Streaming up to {scan:,} interactions...")
    ds = load_dataset("csv", data_files=SOURCE, split="train", streaming=True)
    rows = [r for _, r in zip(range(scan), ds)]
    df = pd.DataFrame(rows)
    print(f"  loaded: {len(df):,} rows\n")

    print(f"Window: {WINDOW_START} to {WINDOW_END}, threshold {MENTION_THRESHOLD} "
          f"reviews per category-month\n")

    print("Unbalanced (all apps, membership recomputed monthly):")
    base = build_panel(df, presence_threshold=0.0)
    print(f"  categories {base['categories']}, category-months {base['category_months']:,}, "
          f"qualifying {base['qualifying']:,} ({base['share']:.1%})\n")

    print("Balanced panels:")
    for thr in (0.5, 0.75, 0.9):
        r = build_panel(df, thr)
        print(f"  presence >= {thr:.0%}: apps {r['apps_kept']:,}, rows {r['rows']:,}, "
              f"categories {r['categories']}, qualifying {r['qualifying']:,} "
              f"({r['share']:.1%})")

    print("\nLongest continuous dense run per category (presence >= 75%):")
    runs = longest_dense_run(df, 0.75)
    if runs.empty:
        print("  none")
    else:
        print(runs.head(15).to_string(index=False))
        need = 26  # 6 baseline + 2 shock + 18 horizon
        usable = (runs["longest_dense_run"] >= need).sum()
        print(f"\n  categories with a run of at least {need} months: {usable}")
        if usable == 0:
            print("  No category supports a full shock-and-recovery window.")
            print("  The category route does not rescue the design.")


def _selftest():
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    print("Self-tests for balanced_panel_check:\n")

    months = pd.period_range(WINDOW_START, WINDOW_END, freq="M")

    # App A present every month; app B present only in the first three.
    rows = []
    for m in months:
        for i in range(40):
            rows.append(dict(app_package="A", app_category="Games",
                             formated_date=f"{m}-15"))
    for m in months[:3]:
        for i in range(40):
            rows.append(dict(app_package="B", app_category="Games",
                             formated_date=f"{m}-15"))
    df = pd.DataFrame(rows)

    loose = build_panel(df, 0.0)
    strict = build_panel(df, 0.9)
    check("both apps counted when unbalanced", loose["rows"] > strict["rows"],
          f"(loose {loose['rows']}, strict {strict['rows']})")
    check("transient app dropped at 90% presence", strict["apps_kept"] == 1,
          f"(got {strict['apps_kept']})")
    check("persistent app retained", strict["rows"] == len(months) * 40,
          f"(got {strict['rows']})")

    # THE DECISIVE CASE: density that exists only because of turnover.
    # Each month a different app contributes, so no app is ever persistent.
    rows = []
    for i, m in enumerate(months):
        for _ in range(40):
            rows.append(dict(app_package=f"app{i}", app_category="Games",
                             formated_date=f"{m}-15"))
    churn = pd.DataFrame(rows)
    unbal = build_panel(churn, 0.0)
    bal = build_panel(churn, 0.75)
    check("turnover looks dense when unbalanced", unbal["qualifying"] > 0,
          f"(got {unbal['qualifying']})")
    check("turnover vanishes under balancing", bal["qualifying"] == 0,
          f"(got {bal['qualifying']})")

    # Continuous run detection
    rows = []
    for m in months[:10]:
        for _ in range(40):
            rows.append(dict(app_package="A", app_category="Games",
                             formated_date=f"{m}-15"))
    for m in months[10:12]:          # two sparse months break the run
        for _ in range(5):
            rows.append(dict(app_package="A", app_category="Games",
                             formated_date=f"{m}-15"))
    for m in months[12:20]:
        for _ in range(40):
            rows.append(dict(app_package="A", app_category="Games",
                             formated_date=f"{m}-15"))
    broken = pd.DataFrame(broken_rows := rows)
    runs = longest_dense_run(broken, 0.5)
    check("sparse months break the run", not runs.empty and
          runs.iloc[0]["longest_dense_run"] == 10,
          f"(got {runs.iloc[0]['longest_dense_run'] if not runs.empty else 'none'})")

    print()
    if failures:
        print(f"{len(failures)} test(s) FAILED: {failures}")
        return 1
    print("All balanced_panel_check self-tests passed.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--scan", type=int, default=500000)
    args = ap.parse_args()
    if args.selftest:
        sys.exit(_selftest())
    run(args.scan)


if __name__ == "__main__":
    main()
