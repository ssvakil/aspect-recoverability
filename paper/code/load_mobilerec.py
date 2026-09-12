"""
MobileRec loader for the Aspect Recoverability pilot.

WHY THIS SCRIPT INSPECTS BEFORE IT LOADS
    Two facts about MobileRec are unverified: whether an app version field
    exists, and whether the same user reviews the same app more than once.
    Both were assumptions behind choosing this dataset. The script therefore
    prints the real schema and the real repeat rate FIRST, and refuses to
    proceed silently if either assumption fails.

    Note that 5-core here means each user reviewed five DISTINCT apps. That is
    not the same as reviewing one app repeatedly, which is what cohort recovery
    requires. The two are easy to confuse and the difference decides whether
    the cohort analysis is possible at all.

USAGE
    python load_mobilerec.py --selftest
    python load_mobilerec.py --inspect
    python load_mobilerec.py --apps 300 --scan 2000000
"""

import argparse
import json
import sys
from collections import Counter

import pandas as pd

DATASET = "recmeapp/mobilerec"

# The repository holds two files. app_meta describes apps and contains no
# reviews; the interactions file is the one this study needs. Loading the
# wrong one produces a valid dataframe with no user, time, or text columns,
# which is why resolve_columns reports unresolved roles rather than guessing.
INTERACTIONS = "interactions/mobilerec_final.csv"
APP_META = "app_meta/app_meta.csv"

# Column names are NOT assumed. They are discovered by --inspect and mapped
# here. Guessing them would risk silently loading the wrong field.
CANDIDATE_COLS = {
    "user": ["uid", "user_id", "userId", "user"],
    "app": ["app_package", "package", "app_id", "appId", "pkg"],
    "time": ["timestamp", "time", "date", "review_time", "at"],
    "text": ["review", "review_text", "text", "content", "body"],
    "rating": ["rating", "score", "stars"],
    "version": ["version", "app_version", "reviewCreatedVersion", "ver"],
}


def resolve_columns(columns):
    """
    Map dataset columns onto the roles the pilot needs.
    Returns (mapping, missing_roles). Nothing is guessed: a role is only
    filled when a candidate name matches exactly.
    """
    lower = {c.lower(): c for c in columns}
    mapping, missing = {}, []
    for role, candidates in CANDIDATE_COLS.items():
        hit = next((lower[c.lower()] for c in candidates if c.lower() in lower), None)
        if hit:
            mapping[role] = hit
        else:
            missing.append(role)
    return mapping, missing


def parse_time(series):
    """
    Parse timestamps without assuming a unit. Millisecond and second epochs
    differ by a factor of 1000, and picking wrong shifts every date by decades
    while still producing valid-looking output.
    """
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().mean() > 0.9:
        median = numeric.median()
        # Rough discriminator: second epochs for recent years are ~1e9,
        # millisecond epochs ~1e12.
        unit = "ms" if median > 1e11 else "s"
        return pd.to_datetime(numeric, unit=unit, errors="coerce"), unit
    return pd.to_datetime(series, errors="coerce", format="mixed"), "string"


def inspect(n=5000):
    """Print the real schema and a density preview. Changes nothing."""
    from datasets import load_dataset

    print(f"Dataset: {DATASET}\n")
    ds = load_dataset("csv", data_files=f"hf://datasets/{DATASET}/{INTERACTIONS}", split="train", streaming=True)
    rows = []
    for i, rec in enumerate(ds):
        rows.append(rec)
        if i + 1 >= n:
            break
    df = pd.DataFrame(rows)

    print(f"Records inspected: {len(df):,}\n")
    print("Columns present:")
    for c in df.columns:
        sample = df[c].dropna().iloc[0] if df[c].notna().any() else "(all null)"
        sample = str(sample)[:70]
        print(f"  {c:<28} e.g. {sample}")

    mapping, missing = resolve_columns(df.columns)
    print("\nRole mapping:")
    for role, col in mapping.items():
        print(f"  {role:<10} -> {col}")
    if missing:
        print(f"\n  UNRESOLVED ROLES: {missing}")
        if "version" in missing:
            print("  No version field. The ground-truth advantage that motivated")
            print("  this dataset does not exist here and would have to come")
            print("  from elsewhere. This changes what the study can claim.")
        if any(r in missing for r in ("user", "app", "time", "text")):
            print("  A required role is missing; the pilot cannot run as designed.")

    if "time" in mapping:
        parsed, unit = parse_time(df[mapping["time"]])
        print(f"\nTimestamp unit inferred: {unit}")
        if parsed.notna().any():
            print(f"  range: {parsed.min()} to {parsed.max()}")
            if parsed.min().year < 1990 or parsed.max().year > 2030:
                print("  WARNING: implausible dates - unit inference is wrong")

    if "user" in mapping and "app" in mapping:
        pairs = df.groupby([mapping["app"], mapping["user"]]).size()
        repeat = (pairs > 1).sum()
        print(f"\nUser-app pairs in sample: {len(pairs):,}")
        print(f"  pairs reviewed more than once: {repeat:,} "
              f"({repeat/len(pairs):.2%})")
        if repeat / len(pairs) < 0.02:
            print("  Cohort recovery will NOT be computable: users do not")
            print("  return to the same app. 5-core means five DISTINCT apps,")
            print("  which is a different thing.")

    return df


def scan_app_counts(stream, limit, app_col):
    counts, seen = Counter(), 0
    for rec in stream:
        a = rec.get(app_col)
        if a:
            counts[a] += 1
        seen += 1
        if seen >= limit:
            break
    return counts, seen


def collect_for_apps(stream, wanted, mapping, limit=None):
    wanted = set(wanted)
    rows, seen = [], 0
    for rec in stream:
        seen += 1
        if rec.get(mapping["app"]) in wanted:
            rows.append({role: rec.get(col) for role, col in mapping.items()})
        if limit and seen >= limit:
            break
    return pd.DataFrame(rows), seen


def monthly_density(df, threshold=30):
    """Product-months clearing the mention threshold, before aspect splitting."""
    if df.empty:
        return dict(app_months=0, above=0, share=float("nan"))
    d = df.copy()
    d["month"] = d["time"].dt.to_period("M")
    am = d.groupby(["app", "month"]).size()
    return dict(app_months=int(len(am)), above=int((am >= threshold).sum()),
                share=float((am >= threshold).mean()),
                median_per_month=float(am.median()))


def load(n_apps, scan_limit, collect_limit, out_path):
    from datasets import load_dataset

    print("Step 1: resolving schema...")
    probe = load_dataset("csv", data_files=f"hf://datasets/{DATASET}/{INTERACTIONS}", split="train", streaming=True)
    first = next(iter(probe))
    mapping, missing = resolve_columns(first.keys())
    print(f"  mapping: {mapping}")
    required = [r for r in ("user", "app", "time", "text") if r in missing]
    if required:
        print(f"  ABORT: required roles missing: {required}")
        print(f"  columns available: {list(first.keys())}")
        return None
    if "version" in missing:
        print("  note: no version field; ground truth unavailable from this source")

    print(f"\nStep 2: scanning up to {scan_limit:,} records for dense apps...")
    stream = load_dataset("csv", data_files=f"hf://datasets/{DATASET}/{INTERACTIONS}", split="train", streaming=True)
    counts, seen = scan_app_counts(stream, scan_limit, mapping["app"])
    print(f"  records scanned: {seen:,}, distinct apps: {len(counts):,}")
    top = [a for a, _ in counts.most_common(n_apps)]
    top_counts = [c for _, c in counts.most_common(n_apps)]
    print(f"  selected {len(top)} apps; reviews in scan: "
          f"max {max(top_counts)}, min {min(top_counts)}")

    print(f"\nStep 3: collecting all reviews for those apps...")
    stream = load_dataset("csv", data_files=f"hf://datasets/{DATASET}/{INTERACTIONS}", split="train", streaming=True)
    df, seen2 = collect_for_apps(stream, top, mapping, collect_limit)
    print(f"  records scanned: {seen2:,}, kept: {len(df):,}")

    if df.empty:
        print("  nothing collected")
        return None

    df["time"], unit = parse_time(df["time"])
    print(f"  timestamp unit: {unit}")
    df = df[df["time"].notna() & df["text"].notna()]
    before = len(df)
    df = df.drop_duplicates(subset=["app", "user", "time", "text"])
    print(f"  duplicates removed: {before - len(df):,}")
    print(f"  final rows: {len(df):,}")
    print(f"  date range: {df['time'].min().date()} to {df['time'].max().date()}")

    dens = monthly_density(df)
    print(f"\nApp-months: {dens['app_months']:,}")
    print(f"  median reviews per app-month: {dens['median_per_month']:.0f}")
    print(f"  app-months with >=30 reviews: {dens['above']:,} "
          f"({dens['share']:.1%})")

    pairs = df.groupby(["app", "user"]).size()
    repeat_rate = (pairs > 1).mean()
    print(f"\nUser-app pairs: {len(pairs):,}")
    print(f"  reviewed more than once: {repeat_rate:.2%}")
    print(f"  cohort recovery computable: {repeat_rate >= 0.02}")

    # rename to the column names feasibility_pilot expects
    out = df.rename(columns={"app": "parent_asin", "user": "user_id",
                             "time": "timestamp"})
    out.to_parquet(out_path, index=False)
    print(f"\nSaved: {out_path}")

    with open(out_path.replace(".parquet", "_report.json"), "w") as f:
        json.dump({"density": dens, "repeat_rate": float(repeat_rate),
                   "n_apps": len(top), "rows": len(df),
                   "version_available": "version" not in missing}, f, indent=2)
    return out


def _selftest():
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    print("Self-tests for load_mobilerec:\n")

    m, miss = resolve_columns(["uid", "app_package", "timestamp", "review", "rating"])
    check("known columns resolve", m["user"] == "uid" and m["app"] == "app_package")
    check("absent version reported missing", "version" in miss)

    m, miss = resolve_columns(["UID", "PACKAGE", "TIME", "TEXT"])
    check("matching is case-insensitive", m.get("user") == "UID")

    m, miss = resolve_columns(["a", "b", "c"])
    check("unknown columns resolve nothing", m == {})
    check("all roles reported missing", len(miss) == len(CANDIDATE_COLS))

    # timestamp unit inference must not silently mislabel
    ms, unit = parse_time(pd.Series([1588687728923] * 10))
    check("millisecond epoch detected", unit == "ms" and ms[0].year == 2020,
          f"(unit={unit}, year={ms[0].year})")
    s, unit = parse_time(pd.Series([1588687728] * 10))
    check("second epoch detected", unit == "s" and s[0].year == 2020,
          f"(unit={unit}, year={s[0].year})")
    d, unit = parse_time(pd.Series(["2020-05-05"] * 10))
    check("date strings parsed", unit == "string" and d[0].year == 2020)

    # density: concentrated data is dense, spread data is not
    dense = pd.DataFrame({"app": ["A"] * 100,
                          "time": pd.to_datetime(["2020-06-15"] * 100)})
    thin = pd.DataFrame({"app": [f"A{i}" for i in range(100)],
                         "time": pd.to_datetime(["2020-06-15"] * 100)})
    check("dense sample has qualifying app-months",
          monthly_density(dense)["above"] == 1)
    check("thin sample has none", monthly_density(thin)["above"] == 0)

    print()
    if failures:
        print(f"{len(failures)} test(s) FAILED: {failures}")
        return 1
    print("All load_mobilerec self-tests passed.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--inspect", action="store_true")
    ap.add_argument("--apps", type=int, default=300)
    ap.add_argument("--scan", type=int, default=2000000)
    ap.add_argument("--collect", type=int, default=19300000)
    ap.add_argument("--out", default="mobilerec_pilot.parquet")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(_selftest())
    if args.inspect:
        inspect()
        return
    load(args.apps, args.scan, args.collect, args.out)


if __name__ == "__main__":
    main()
