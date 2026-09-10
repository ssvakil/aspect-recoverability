"""
Data loader for the Aspect Recoverability pilot.

WHY THIS IS NOT A RANDOM SAMPLE
    The pilot needs at least MIN_MENTIONS_PER_MONTH aspect mentions per
    product-month. A random sample of reviews spreads thinly across millions of
    products, so no product reaches that threshold and the pilot returns zero
    shocks for a reason that has nothing to do with the hypothesis.

    Instead this script selects the densest products and takes ALL their
    reviews. That preserves longitudinal density, which is the resource the
    study actually consumes.

WHAT THIS COSTS
    The selected products are not representative of the category. Findings
    generalise to heavily-reviewed products only. This is a real limitation and
    belongs in the manuscript, not in a footnote.

USAGE
    python load_amazon.py --selftest
    python load_amazon.py --category All_Beauty --scan 300000 --products 200
"""

import argparse
import json
import os
import sys
from collections import Counter

import pandas as pd

DATASET = "McAuley-Lab/Amazon-Reviews-2023"

# Fields as published: rating, title, text, asin, parent_asin, user_id,
# timestamp (milliseconds since epoch), helpful_vote, verified_purchase.
KEEP_FIELDS = ["parent_asin", "user_id", "timestamp", "text", "rating",
               "verified_purchase"]


def ms_to_timestamp(series):
    """Convert millisecond epochs to pandas timestamps, coercing bad values."""
    numeric = pd.to_numeric(series, errors="coerce")
    return pd.to_datetime(numeric, unit="ms", errors="coerce")


def scan_product_counts(stream, limit):
    """
    Pass one: count reviews per product over the first `limit` records.

    NOTE ON ORDER: the stream is not guaranteed to be randomly ordered. If it
    is grouped by product or sorted by time, an early cut-off biases which
    products look dense. The counts here are therefore a heuristic for finding
    candidates, not an estimate of true product popularity.
    """
    counts = Counter()
    seen = 0
    for rec in stream:
        pa = rec.get("parent_asin")
        if pa:
            counts[pa] += 1
        seen += 1
        if seen >= limit:
            break
    return counts, seen


def collect_for_products(stream, wanted, limit=None):
    """Pass two: keep every review belonging to the selected products."""
    wanted = set(wanted)
    rows = []
    seen = 0
    for rec in stream:
        seen += 1
        if rec.get("parent_asin") in wanted:
            rows.append({k: rec.get(k) for k in KEEP_FIELDS})
        if limit and seen >= limit:
            break
    return pd.DataFrame(rows), seen


def clean(df):
    """Type conversion and the data-integrity checks required by protocol §2."""
    report = {"input_rows": len(df)}
    if df.empty:
        return df, report

    df = df.copy()
    df["timestamp"] = ms_to_timestamp(df["timestamp"])
    report["bad_timestamps"] = int(df["timestamp"].isna().sum())
    df = df[df["timestamp"].notna()]

    report["missing_text"] = int(df["text"].isna().sum())
    df = df[df["text"].notna() & (df["text"].astype(str).str.len() > 0)]

    before = len(df)
    df = df.drop_duplicates(subset=["parent_asin", "user_id", "timestamp", "text"])
    report["duplicates_removed"] = before - len(df)

    report["output_rows"] = len(df)
    if len(df):
        report["date_min"] = str(df["timestamp"].min().date())
        report["date_max"] = str(df["timestamp"].max().date())
        report["products"] = int(df["parent_asin"].nunique())
        report["users"] = int(df["user_id"].nunique())
    return df, report


def repeat_review_rate(df, product_col="parent_asin", user_col="user_id"):
    """
    Share of user-product pairs with more than one review.

    The claim that recovery cannot be separated from turnover rests on this
    number being small. It was measured for MobileRec but not, in the first
    version of this analysis, for Amazon. Reporting it for only one corpus
    weakens a claim made about reviewing behaviour in general.
    """
    if df.empty:
        return dict(pairs=0, repeat=0, rate=float("nan"), computable=False)
    pairs = df.groupby([product_col, user_col]).size()
    repeat = int((pairs > 1).sum())
    return dict(pairs=int(len(pairs)), repeat=repeat,
                rate=float(repeat / len(pairs)),
                computable=bool(len(pairs) and repeat / len(pairs) >= 0.02))


def density_report(df, top=10):
    """Reviews per product-month for the selected products."""
    if df.empty:
        return pd.DataFrame()
    d = df.copy()
    d["month"] = d["timestamp"].dt.to_period("M")
    pm = d.groupby(["parent_asin", "month"]).size().rename("reviews")
    per_product = pm.groupby("parent_asin").agg(
        months=("size"), median_per_month=("median"), max_per_month=("max")
    )
    return per_product.sort_values("median_per_month", ascending=False).head(top)


def months_above_threshold(df, threshold=30):
    """
    How many product-months clear the mention threshold. If this is near zero,
    the pilot cannot run regardless of the hypothesis, and the right response
    is a different sampling strategy, not a lower threshold.
    """
    if df.empty:
        return dict(product_months=0, above=0, share=float("nan"))
    d = df.copy()
    d["month"] = d["timestamp"].dt.to_period("M")
    pm = d.groupby(["parent_asin", "month"]).size()
    return dict(product_months=int(len(pm)),
                above=int((pm >= threshold).sum()),
                share=float((pm >= threshold).mean()))


def open_stream(config):
    """
    Open a streaming iterator over one config, trying each loading route in
    turn and reporting which one worked.

    Route 1 is the normal call. It fails on datasets>=4 when the repository
    still contains a legacy loading script, even though parquet files exist.
    Route 2 bypasses the script by reading the converted parquet branch
    directly. Paths are discovered from the hub rather than assumed, because a
    hard-coded path that silently matches the wrong files would be worse than
    an error.
    """
    from datasets import load_dataset

    errors = []

    # Route 1: standard load
    try:
        ds = load_dataset(DATASET, config, split="full", streaming=True)
        print("  loader route: standard load_dataset")
        return ds
    except Exception as e:
        errors.append(f"standard: {type(e).__name__}: {e}")

    # Route 2: parquet conversion branch, paths discovered from the hub
    try:
        from huggingface_hub import HfApi
        api = HfApi()
        files = api.list_repo_files(DATASET, repo_type="dataset",
                                    revision="refs/convert/parquet")
        matches = [f for f in files
                   if f.startswith(config + "/") and f.endswith(".parquet")]
        if not matches:
            raise FileNotFoundError(
                f"no parquet files found under '{config}/' on the conversion "
                f"branch; available prefixes: "
                f"{sorted({f.split('/')[0] for f in files})[:10]}")
        urls = [f"hf://datasets/{DATASET}@refs/convert/parquet/{f}"
                for f in matches]
        print(f"  loader route: parquet branch ({len(urls)} files)")
        return load_dataset("parquet", data_files=urls, split="train",
                            streaming=True)
    except Exception as e:
        errors.append(f"parquet branch: {type(e).__name__}: {e}")

    raise RuntimeError(
        "could not open the dataset. Routes tried:\n  - " +
        "\n  - ".join(errors) +
        "\n\nIf both failed, try: pip install 'datasets<4'"
    )


def load(category, scan_limit, n_products, collect_limit, out_path):
    config = f"raw_review_{category}"
    print(f"Dataset: {DATASET}\nConfig:  {config}\n")

    print(f"Pass 1: scanning up to {scan_limit:,} records for dense products...")
    stream = open_stream(config)
    counts, seen = scan_product_counts(stream, scan_limit)
    print(f"  records scanned: {seen:,}")
    print(f"  distinct products seen: {len(counts):,}")

    if not counts:
        print("  no products found - check the category name")
        return None

    top = [pa for pa, _ in counts.most_common(n_products)]
    top_counts = [c for _, c in counts.most_common(n_products)]
    print(f"  selected top {len(top)} products")
    print(f"  reviews in scan for these: max {max(top_counts)}, "
          f"min {min(top_counts)}")

    if max(top_counts) < 50:
        print("\n  WARNING: even the densest product has few reviews in this scan.")
        print("  Increase --scan, or pick a larger category. Proceeding anyway.")

    print(f"\nPass 2: collecting all reviews for the selected products...")
    stream = open_stream(config)
    df, seen2 = collect_for_products(stream, top, collect_limit)
    print(f"  records scanned: {seen2:,}")
    print(f"  reviews kept: {len(df):,}")

    df, rep = clean(df)
    print("\nCleaning report:")
    for k, v in rep.items():
        print(f"  {k}: {v}")

    print("\nDensity of selected products (top 10 by median reviews/month):")
    print(density_report(df).to_string() if len(df) else "  (empty)")

    rr = repeat_review_rate(df)
    print(f"\nUser-product pairs: {rr['pairs']:,}")
    print(f"  pairs with more than one review: {rr['repeat']:,} ({rr['rate']:.3%})")
    print(f"  cohort recovery computable: {rr['computable']}")

    mat = months_above_threshold(df)
    print(f"\nProduct-months total: {mat['product_months']:,}")
    print(f"Product-months with >=30 reviews: {mat['above']:,} "
          f"({mat['share']:.1%})")
    if mat["above"] < 50:
        print("\n  CRITICAL: too few dense product-months for shock detection.")
        print("  Do NOT lower the threshold to compensate. Increase --scan,")
        print("  or move to a category with heavier reviewing.")

    df.to_parquet(out_path, index=False)
    print(f"\nSaved: {out_path}")

    with open(out_path.replace(".parquet", "_report.json"), "w") as f:
        json.dump({"category": category, "cleaning": rep,
                   "density": mat, "repeat_review": rr,
                   "n_products": len(top)}, f, indent=2)
    return df


# ---------------------------------------------------------------------------

def _selftest():
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    print("Self-tests for load_amazon:\n")

    # timestamp conversion, including the published example value
    ts = ms_to_timestamp(pd.Series([1588687728923, "1588615855070", None, "abc"]))
    check("millisecond epoch converts to 2020", ts[0].year == 2020,
          f"(got {ts[0]})")
    check("string epochs also convert", ts[1].year == 2020)
    check("null becomes NaT", pd.isna(ts[2]))
    check("garbage becomes NaT rather than raising", pd.isna(ts[3]))

    # a seconds-epoch value must NOT silently look plausible
    wrong = ms_to_timestamp(pd.Series([1588687728]))
    check("seconds-epoch lands in 1970, so the error is visible",
          wrong[0].year == 1970, f"(got {wrong[0]})")

    # scan picks the densest products
    recs = ([{"parent_asin": "A"}] * 30 + [{"parent_asin": "B"}] * 10 +
            [{"parent_asin": "C"}] * 5)
    counts, seen = scan_product_counts(iter(recs), 1000)
    check("scan counts all records", seen == 45)
    check("scan ranks densest product first", counts.most_common(1)[0][0] == "A")

    # scan respects its limit
    _, seen = scan_product_counts(iter(recs), 10)
    check("scan stops at limit", seen == 10)

    # collection keeps only wanted products
    recs = [{"parent_asin": p, "user_id": f"u{i}", "timestamp": 1588687728923,
             "text": "battery great", "rating": 5, "verified_purchase": True}
            for i, p in enumerate(["A", "B", "A", "C", "A"])]
    df, _ = collect_for_products(iter(recs), {"A"})
    check("collection keeps only selected products", len(df) == 3, f"(got {len(df)})")
    check("collection keeps required fields",
          set(KEEP_FIELDS).issubset(df.columns))

    # cleaning removes duplicates and bad rows
    raw = pd.DataFrame({
        "parent_asin": ["A", "A", "A", "A"],
        "user_id": ["u1", "u1", "u2", "u3"],
        "timestamp": [1588687728923, 1588687728923, 1588687728923, None],
        "text": ["good", "good", "bad", "ok"],
        "rating": [5, 5, 1, 3],
        "verified_purchase": [True] * 4,
    })
    cleaned, rep = clean(raw)
    check("bad timestamp dropped", rep["bad_timestamps"] == 1)
    check("exact duplicate removed", rep["duplicates_removed"] == 1)
    check("two rows survive", len(cleaned) == 2, f"(got {len(cleaned)})")

    # repeat-review rate
    single = pd.DataFrame({"parent_asin": ["A"] * 20,
                           "user_id": [f"u{i}" for i in range(20)]})
    rep_rate = repeat_review_rate(single)
    check("all-singleton data gives zero repeat rate", rep_rate["rate"] == 0.0)
    check("all-singleton data is not computable", rep_rate["computable"] is False)

    repeated = pd.DataFrame({"parent_asin": ["A"] * 20,
                             "user_id": [f"u{i % 4}" for i in range(20)]})
    rr2 = repeat_review_rate(repeated)
    check("repeated data gives full repeat rate", rr2["rate"] == 1.0,
          f"(got {rr2['rate']})")
    check("repeated data is computable", rr2["computable"] is True)

    # THE DECISIVE DIAGNOSTIC: a thin random-style sample must be reported as
    # having almost no dense product-months, while a concentrated sample must
    # be reported as dense. This is the check that prevents a false negative.
    thin = pd.DataFrame({
        "parent_asin": [f"P{i}" for i in range(500)],
        "timestamp": pd.to_datetime(["2020-06-15"] * 500),
    })
    dense = pd.DataFrame({
        "parent_asin": ["P1"] * 500,
        "timestamp": pd.to_datetime(["2020-06-15"] * 500),
    })
    check("thin sample reports no dense product-months",
          months_above_threshold(thin)["above"] == 0)
    check("concentrated sample reports dense product-months",
          months_above_threshold(dense)["above"] == 1)

    print()
    if failures:
        print(f"{len(failures)} test(s) FAILED: {failures}")
        return 1
    print("All load_amazon self-tests passed.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--category", default="All_Beauty",
                    help="e.g. All_Beauty, Electronics, Cell_Phones_and_Accessories")
    ap.add_argument("--scan", type=int, default=300000,
                    help="records to scan when looking for dense products")
    ap.add_argument("--products", type=int, default=200)
    ap.add_argument("--collect", type=int, default=2000000,
                    help="cap on records scanned during collection")
    ap.add_argument("--out", default="pilot_data.parquet")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(_selftest())

    load(args.category, args.scan, args.products, args.collect, args.out)


if __name__ == "__main__":
    main()
