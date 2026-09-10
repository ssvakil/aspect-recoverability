"""
Feasibility pilot for the Aspect Recoverability study.

PURPOSE
    Decide whether the data can support the planned survival analysis BEFORE
    committing to full extraction. This script answers one question only:
    how many analysable aspect shock events exist?

    It deliberately does NOT try to be accurate at aspect extraction. A lexicon
    is used because event *density* is what we are estimating, not extraction
    quality. Accurate ABSA comes after category selection.

USAGE
    python feasibility_pilot.py --selftest          # run built-in tests, no data needed
    python feasibility_pilot.py --data PATH --category CATEGORY

DEPENDENCIES
    pandas, numpy, scipy
"""

import argparse
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm

# ---------------------------------------------------------------------------
# Protocol parameters. These mirror Section 5 of the pre-registration.
# Changing them here without recording a deviation defeats the purpose.
# ---------------------------------------------------------------------------

BASELINE_MONTHS = 6        # trailing window defining pre-shock level
SHOCK_SD = 1.0             # drop threshold in SD units
SHOCK_MIN_MONTHS = 2       # sustained duration for a drop to count as a shock
RECOVERY_FRACTION = 0.90   # return level, as fraction of baseline
RECOVERY_MIN_MONTHS = 3    # sustained duration for recovery to count
RECOVERY_HORIZON = 18      # months after onset within which recovery is sought
MIN_MENTIONS_PER_MONTH = 30

PILOT_ASPECTS = {
    "quality":     ["quality", "well made", "cheaply made", "flimsy", "solid"],
    "battery":     ["battery", "charge", "charging", "power lasts"],
    "design":      ["design", "look", "looks", "style", "aesthetic"],
    "price":       ["price", "expensive", "cheap", "overpriced", "value for money"],
    "delivery":    ["delivery", "shipping", "arrived", "shipment"],
    "packaging":   ["packaging", "package", "box", "wrapped"],
    "performance": ["performance", "fast", "slow", "lag", "works well"],
    "durability":  ["durability", "broke", "broken", "stopped working", "lasted"],
    "usability":   ["easy to use", "difficult to use", "intuitive", "confusing"],
    "support":     ["customer service", "support", "warranty", "returns"],
}

POSITIVE_CUES = ["good", "great", "excellent", "love", "perfect", "happy",
                 "works well", "recommend", "solid", "easy"]
NEGATIVE_CUES = ["bad", "poor", "terrible", "awful", "hate", "broke", "broken",
                 "disappointed", "waste", "stopped working", "flimsy", "useless"]


# ---------------------------------------------------------------------------
# Core detection logic
# ---------------------------------------------------------------------------

@dataclass
class ShockEvent:
    product_id: str
    aspect: str
    onset_index: int          # position in the series where the shock begins
    baseline: float
    depth_sd: float
    outcome: str              # "recovered" | "non_recovered" | "censored"
    months_to_recovery: float # np.nan when not recovered
    followup_months: int


def detect_shocks(series, baseline_months=BASELINE_MONTHS, shock_sd=SHOCK_SD,
                  shock_min_months=SHOCK_MIN_MONTHS,
                  recovery_fraction=RECOVERY_FRACTION,
                  recovery_min_months=RECOVERY_MIN_MONTHS,
                  horizon=RECOVERY_HORIZON):
    """
    Detect negative shocks in one monthly sentiment series and classify each.

    series: 1-D sequence of monthly aspect sentiment values, already filtered
            to qualifying months. Must be contiguous in time.

    Returns a list of dicts, one per shock.

    Censoring rule (pre-registration 5.1): a shock is labelled non_recovered
    ONLY when the full horizon was observed. Shocks with a shorter follow-up
    are censored, never counted as non-recovered. Omitting this inflates
    apparent irreversibility because late shocks can never be seen to recover.
    """
    s = np.asarray(series, dtype=float)
    n = len(s)
    shocks = []
    i = baseline_months
    while i < n:
        window = s[i - baseline_months:i]
        baseline = window.mean()
        sd = window.std(ddof=1) if baseline_months > 1 else 0.0
        if sd == 0 or np.isnan(sd):
            i += 1
            continue

        threshold = baseline - shock_sd * sd
        # a shock requires shock_min_months consecutive months below threshold
        run = 0
        while i + run < n and s[i + run] < threshold:
            run += 1
        if run < shock_min_months:
            i += 1
            continue

        onset = i
        recovery_level = baseline * recovery_fraction if baseline > 0 else baseline + abs(baseline) * (1 - recovery_fraction)
        followup = n - onset - 1

        outcome, months_to_recovery = _classify_recovery(
            s, onset, recovery_level, recovery_min_months, horizon, followup
        )

        shocks.append(dict(
            onset_index=onset,
            baseline=baseline,
            depth_sd=(baseline - s[onset:onset + run].min()) / sd,
            outcome=outcome,
            months_to_recovery=months_to_recovery,
            followup_months=followup,
        ))
        # move past this shock episode so overlapping detections do not double count
        i = onset + max(run, 1)
    return shocks


def _classify_recovery(s, onset, recovery_level, recovery_min_months, horizon, followup):
    """Return (outcome, months_to_recovery) for a single shock at `onset`."""
    n = len(s)
    limit = min(onset + horizon + 1, n)
    consecutive = 0
    for t in range(onset + 1, limit):
        if s[t] >= recovery_level:
            consecutive += 1
            if consecutive >= recovery_min_months:
                # recovery confirmed; onset of recovery is the first of the run
                recovery_month = t - recovery_min_months + 1
                return "recovered", float(recovery_month - onset)
        else:
            consecutive = 0

    # no recovery observed within what we could see
    if followup >= horizon:
        return "non_recovered", np.nan
    return "censored", np.nan


# ---------------------------------------------------------------------------
# Power calculation
# ---------------------------------------------------------------------------

def events_required(hazard_ratio, alpha=0.05, power=0.80, exposed_fraction=0.5):
    """
    Schoenfeld's formula for the number of EVENTS (not observations) needed to
    detect a given hazard ratio in a Cox model.

        d = (z_{1-a/2} + z_{1-b})^2 / (p (1-p) (ln HR)^2)

    Note this returns events. The number of shock episodes needed is larger,
    since censored episodes contribute person-time but not events.
    """
    if hazard_ratio <= 0 or hazard_ratio == 1:
        raise ValueError("hazard_ratio must be positive and different from 1")
    z_a = norm.ppf(1 - alpha / 2)
    z_b = norm.ppf(power)
    p = exposed_fraction
    return (z_a + z_b) ** 2 / (p * (1 - p) * np.log(hazard_ratio) ** 2)


def episodes_required(hazard_ratio, event_fraction, **kwargs):
    """Convert required events into required episodes given an observed event rate."""
    if not 0 < event_fraction <= 1:
        raise ValueError("event_fraction must be in (0, 1]")
    return events_required(hazard_ratio, **kwargs) / event_fraction


# ---------------------------------------------------------------------------
# Lightweight pilot extraction
# ---------------------------------------------------------------------------

def tag_aspects(text):
    """Return the set of pilot aspects mentioned in a review. Lexicon-based."""
    if not isinstance(text, str):
        return set()
    lowered = text.lower()
    return {a for a, cues in PILOT_ASPECTS.items() if any(c in lowered for c in cues)}


def crude_polarity(text):
    """Crude polarity in [-1, 1]. Pilot only; not used for final analysis."""
    if not isinstance(text, str):
        return 0.0
    lowered = text.lower()
    pos = sum(c in lowered for c in POSITIVE_CUES)
    neg = sum(c in lowered for c in NEGATIVE_CUES)
    if pos + neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


def build_monthly_series(df, text_col="text", time_col="timestamp",
                         product_col="parent_asin",
                         min_mentions=MIN_MENTIONS_PER_MONTH):
    """
    Build product x aspect x month mean sentiment, dropping months below the
    mention threshold. Months are NOT interpolated: a dropped month breaks the
    series, and detect_shocks must be run on contiguous segments only.
    """
    rows = []
    for _, r in df.iterrows():
        aspects = tag_aspects(r[text_col])
        if not aspects:
            continue
        pol = crude_polarity(r[text_col])
        for a in aspects:
            rows.append((r[product_col], a, pd.Timestamp(r[time_col]).to_period("M"), pol))

    if not rows:
        return pd.DataFrame(columns=["product", "aspect", "month", "sentiment", "n"])

    long = pd.DataFrame(rows, columns=["product", "aspect", "month", "polarity"])
    agg = long.groupby(["product", "aspect", "month"]).agg(
        sentiment=("polarity", "mean"), n=("polarity", "size")
    ).reset_index()
    return agg[agg["n"] >= min_mentions].reset_index(drop=True)


def contiguous_segments(months, values):
    """Split a series into runs of consecutive months. Returns list of arrays."""
    segments, current = [], []
    prev = None
    for m, v in zip(months, values):
        if prev is not None and (m - prev).n != 1:
            if current:
                segments.append(np.array(current))
            current = []
        current.append(v)
        prev = m
    if current:
        segments.append(np.array(current))
    return segments


def run_pilot(df, **kwargs):
    """Full pilot: returns a DataFrame of shock events with outcomes."""
    agg = build_monthly_series(df, **kwargs)
    records = []
    for (product, aspect), g in agg.groupby(["product", "aspect"]):
        g = g.sort_values("month")
        for seg in contiguous_segments(g["month"].tolist(), g["sentiment"].tolist()):
            if len(seg) <= BASELINE_MONTHS + SHOCK_MIN_MONTHS:
                continue
            for sh in detect_shocks(seg):
                sh.update(product=product, aspect=aspect)
                records.append(sh)
    return pd.DataFrame(records)


def report(shocks):
    """Print the decision-relevant summary."""
    if shocks.empty:
        print("No shock events detected. Data is not usable under current thresholds.")
        return

    print(f"Total shock episodes: {len(shocks)}")
    print("\nBy outcome:")
    print(shocks["outcome"].value_counts().to_string())
    print("\nBy aspect:")
    print(pd.crosstab(shocks["aspect"], shocks["outcome"]).to_string())

    print("\nClustering (relevant for standard errors):")
    per_product = shocks.groupby("product").size()
    print(f"  distinct products: {per_product.size}")
    print(f"  max shocks in one product: {per_product.max()}")
    print(f"  products with >1 shock: {(per_product > 1).sum()}")
    if per_product.max() > 1:
        print("  -> observations are clustered; use cluster-robust SE or a frailty model")

    analysable = (shocks["outcome"] != "censored").sum()
    print(f"\nAnalysable (non-censored) episodes: {analysable}")
    for hr in (1.5, 2.0):
        need = events_required(hr)
        print(f"  events needed to detect HR={hr} at 80% power: {need:.0f}")
    print("\nNote: required EVENTS, not episodes. Divide by the observed event")
    print("rate to get the episode count needed. See episodes_required().")


# ---------------------------------------------------------------------------
# Self-tests. Every claim the detector makes is checked against a series whose
# correct answer is known by construction.
# ---------------------------------------------------------------------------

def _selftest():
    failures = []

    def check(name, condition, detail=""):
        if condition:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    print("Self-tests for detect_shocks:\n")

    # 1. A flat series must produce no shocks.
    flat = [0.5] * 30
    check("flat series yields no shocks", len(detect_shocks(flat)) == 0)

    # 2. Pure noise around a stable mean should rarely fire. Not never: a 1-SD
    #    threshold on noise will occasionally trigger. We check it is not rampant.
    rng = np.random.default_rng(0)
    noisy = 0.5 + rng.normal(0, 0.02, 60)
    n_noise = len(detect_shocks(noisy))
    check("noise produces few false shocks", n_noise <= 6, f"(got {n_noise})")

    # 3. A clear drop that then returns must be labelled recovered.
    s = [0.60, 0.62, 0.58, 0.61, 0.59, 0.60]      # baseline, sd ~0.015
    s += [0.20, 0.18]                              # shock
    s += [0.58, 0.59, 0.60]                        # recovery, 3 months
    s += [0.60] * 20                               # long follow-up
    res = detect_shocks(s)
    check("clear drop detected", len(res) == 1, f"(got {len(res)})")
    if res:
        check("drop then return -> recovered", res[0]["outcome"] == "recovered",
              f"(got {res[0]['outcome']})")
        check("time to recovery is 2 months", res[0]["months_to_recovery"] == 2.0,
              f"(got {res[0]['months_to_recovery']})")

    # 4. A drop that never returns, with full horizon observed -> non_recovered.
    s = [0.60, 0.62, 0.58, 0.61, 0.59, 0.60] + [0.20] * 20
    res = detect_shocks(s)
    check("permanent drop -> non_recovered",
          res and res[0]["outcome"] == "non_recovered",
          f"(got {res[0]['outcome'] if res else 'none'})")

    # 5. THE CRITICAL TEST. Same permanent drop, but truncated so that fewer
    #    than `horizon` months follow. Must be censored, not non_recovered.
    #    Getting this wrong is exactly what inflates irreversibility estimates.
    s_short = [0.60, 0.62, 0.58, 0.61, 0.59, 0.60] + [0.20] * 5
    res = detect_shocks(s_short)
    check("truncated drop -> censored, not non_recovered",
          res and res[0]["outcome"] == "censored",
          f"(got {res[0]['outcome'] if res else 'none'})")

    # 6. A one-month dip must not count: shock requires 2 sustained months.
    s = [0.60, 0.62, 0.58, 0.61, 0.59, 0.60, 0.20, 0.60, 0.61, 0.59] + [0.60] * 20
    check("single-month dip is not a shock", len(detect_shocks(s)) == 0,
          f"(got {len(detect_shocks(s))})")

    # 7. Recovery must be sustained. A single month touching the level is not
    #    recovery when RECOVERY_MIN_MONTHS is 3.
    s = [0.60, 0.62, 0.58, 0.61, 0.59, 0.60] + [0.20, 0.20]
    s += [0.58, 0.20, 0.20]                        # one good month only
    s += [0.20] * 20
    res = detect_shocks(s)
    check("momentary touch is not recovery",
          res and res[0]["outcome"] == "non_recovered",
          f"(got {res[0]['outcome'] if res else 'none'})")

    print("\nSelf-tests for power calculation:\n")

    # 8. Schoenfeld against a known value: HR=2, alpha=.05, power=.80, p=.5
    #    d = (1.959964 + 0.841621)^2 / (0.25 * ln(2)^2) = 65.4
    d = events_required(2.0)
    check("Schoenfeld HR=2 gives ~65 events", abs(d - 65.4) < 1.0, f"(got {d:.1f})")

    # 9. Smaller effects need more events.
    check("smaller HR needs more events", events_required(1.2) > events_required(2.0))

    # 10. Episodes exceed events when some episodes are censored.
    check("episodes exceed events under censoring",
          episodes_required(2.0, event_fraction=0.5) > events_required(2.0))

    # 11. Unbalanced exposure needs more events than balanced.
    check("unbalanced exposure costs power",
          events_required(2.0, exposed_fraction=0.1) > events_required(2.0, exposed_fraction=0.5))

    print("\nSelf-tests for series segmentation:\n")

    # 12. A gap in months must split the series, so shocks are not detected
    #     across a discontinuity.
    months = pd.period_range("2020-01", periods=3, freq="M").tolist()
    months += pd.period_range("2021-01", periods=3, freq="M").tolist()
    segs = contiguous_segments(months, [1, 2, 3, 4, 5, 6])
    check("gap splits series into two segments", len(segs) == 2, f"(got {len(segs)})")
    check("segments have correct lengths",
          len(segs) == 2 and len(segs[0]) == 3 and len(segs[1]) == 3)

    print()
    if failures:
        print(f"{len(failures)} test(s) FAILED: {failures}")
        return 1
    print("All self-tests passed.")
    return 0


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--data", help="parquet or csv of reviews for one category")
    ap.add_argument("--category", default="(unnamed)")
    ap.add_argument("--sample", type=int, default=50000)
    args = ap.parse_args()

    if args.selftest:
        sys.exit(_selftest())

    if not args.data:
        ap.error("--data is required unless --selftest is given")

    df = pd.read_parquet(args.data) if args.data.endswith(".parquet") else pd.read_csv(args.data)
    if len(df) > args.sample:
        df = df.sample(args.sample, random_state=0)

    print(f"Category: {args.category}")
    print(f"Reviews sampled: {len(df)}")
    shocks = run_pilot(df)
    report(shocks)


if __name__ == "__main__":
    main()


# ===========================================================================
# ADDITIONS v2: censoring breakdown, events-per-parameter, sensitivity grid,
# null controls, and category comparison.
# ===========================================================================

def censoring_summary(shocks):
    """Analysable events vs censored. The ratio matters as much as the count."""
    if shocks.empty:
        return dict(total=0, analysable=0, censored=0, censoring_rate=np.nan,
                    recovered=0, non_recovered=0)
    counts = shocks["outcome"].value_counts()
    rec = int(counts.get("recovered", 0))
    non = int(counts.get("non_recovered", 0))
    cen = int(counts.get("censored", 0))
    total = rec + non + cen
    return dict(total=total, analysable=rec + non, censored=cen,
                censoring_rate=cen / total if total else np.nan,
                recovered=rec, non_recovered=non)


def events_per_parameter(n_events, n_parameters):
    """
    EPP is the practical constraint reviewers check. Below ~10, Cox estimates
    are unreliable regardless of what the Schoenfeld formula says, because that
    formula assumes a single covariate of interest.
    """
    if n_parameters <= 0:
        raise ValueError("n_parameters must be positive")
    return n_events / n_parameters


def epp_verdict(epp):
    if epp >= 20:
        return "comfortable"
    if epp >= 10:
        return "acceptable, report as a limitation"
    return "INSUFFICIENT - reduce covariates or pool categories"


def sensitivity_grid(segments, sd_values=(0.75, 1.0, 1.25),
                     duration_values=(2, 3, 4)):
    """
    Recount shocks across detection settings. If events exist only in one cell,
    the finding is an artefact of that setting.
    `segments` is a list of (product, aspect, values) tuples.
    """
    rows = []
    for sd in sd_values:
        for dur in duration_values:
            total = analysable = 0
            for _, _, seg in segments:
                if len(seg) <= BASELINE_MONTHS + dur:
                    continue
                found = detect_shocks(seg, shock_sd=sd, shock_min_months=dur)
                total += len(found)
                analysable += sum(f["outcome"] != "censored" for f in found)
            rows.append(dict(shock_sd=sd, min_months=dur,
                             shocks=total, analysable=analysable))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Null controls
# ---------------------------------------------------------------------------

def shuffle_null(values, rng):
    """
    Plain permutation. WARNING: this destroys autocorrelation, which inflates
    the local baseline SD and mechanically suppresses shock detection. It is
    therefore a BIASED null that favours the alternative. Reported for
    comparison only; block_bootstrap_null is the honest control.
    """
    v = np.array(values, dtype=float)
    return rng.permutation(v)


def block_bootstrap_null(values, rng, block=6):
    """
    Circular block bootstrap. Preserves short-range autocorrelation while
    randomising where episodes fall in time. This is the appropriate null:
    it asks whether shocks are more frequent than a process with the same
    local smoothness but no real events.
    """
    v = np.array(values, dtype=float)
    n = len(v)
    if n < block:
        return v.copy()
    out = []
    while len(out) < n:
        start = rng.integers(0, n)
        out.extend(v[(start + i) % n] for i in range(block))
    return np.array(out[:n])


def null_comparison(segments, n_reps=50, seed=0):
    """
    Compare observed shock counts against both nulls.
    Returns observed count and the null distributions' means.
    """
    rng = np.random.default_rng(seed)

    observed = sum(len(detect_shocks(seg)) for _, _, seg in segments
                   if len(seg) > BASELINE_MONTHS + SHOCK_MIN_MONTHS)

    shuffle_counts, block_counts = [], []
    for _ in range(n_reps):
        s_total = b_total = 0
        for _, _, seg in segments:
            if len(seg) <= BASELINE_MONTHS + SHOCK_MIN_MONTHS:
                continue
            s_total += len(detect_shocks(shuffle_null(seg, rng)))
            b_total += len(detect_shocks(block_bootstrap_null(seg, rng)))
        shuffle_counts.append(s_total)
        block_counts.append(b_total)

    return dict(
        observed=observed,
        shuffle_mean=float(np.mean(shuffle_counts)),
        shuffle_sd=float(np.std(shuffle_counts)),
        block_mean=float(np.mean(block_counts)),
        block_sd=float(np.std(block_counts)),
        ratio_vs_block=observed / np.mean(block_counts) if np.mean(block_counts) else np.inf,
    )


# ---------------------------------------------------------------------------
# Category comparison
# ---------------------------------------------------------------------------

def category_profile(shocks, agg):
    """
    Report the components separately. A single weighted score hides the
    trade-offs and the weights are not defensible to a reviewer, so the
    composite is provided only as a tiebreaker.
    """
    if shocks.empty:
        return dict(analysable=0, products=0, aspects=0, median_depth=np.nan,
                    max_per_product=0)
    cs = censoring_summary(shocks)
    return dict(
        analysable=cs["analysable"],
        censoring_rate=cs["censoring_rate"],
        products=shocks["product"].nunique(),
        aspects=shocks["aspect"].nunique(),
        median_series_length=float(agg.groupby(["product", "aspect"]).size().median()),
        max_per_product=int(shocks.groupby("product").size().max()),
    )


def _selftest_v2():
    failures = []

    def check(name, condition, detail=""):
        if condition:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    print("Self-tests for v2 additions:\n")

    # censoring summary arithmetic
    df = pd.DataFrame({"outcome": ["recovered"] * 3 + ["non_recovered"] * 2 + ["censored"] * 5})
    cs = censoring_summary(df)
    check("censoring summary totals", cs["total"] == 10 and cs["analysable"] == 5)
    check("censoring rate correct", abs(cs["censoring_rate"] - 0.5) < 1e-9)

    # events per parameter
    check("EPP arithmetic", abs(events_per_parameter(245, 12) - 20.416) < 0.01)
    check("EPP verdict low", "INSUFFICIENT" in epp_verdict(events_per_parameter(50, 12)))
    check("EPP verdict high", epp_verdict(25.0) == "comfortable")

    # block bootstrap preserves length and value multiset roughly
    rng = np.random.default_rng(1)
    v = np.arange(24, dtype=float)
    b = block_bootstrap_null(v, rng, block=6)
    check("block bootstrap preserves length", len(b) == len(v))
    check("block bootstrap draws from original values", set(b).issubset(set(v)))

    # shuffle preserves the exact multiset
    s = shuffle_null(v, rng)
    check("shuffle preserves multiset", sorted(s) == sorted(v))

    # THE KEY DIAGNOSTIC: on an autocorrelated series with no real shocks,
    # plain shuffle should find FEWER shocks than the block bootstrap, because
    # shuffling inflates local SD. This demonstrates the bias we warned about.
    rng = np.random.default_rng(7)
    # AR(1) series, smooth, no injected shocks
    ar = [0.5]
    for _ in range(200):
        ar.append(0.8 * ar[-1] + 0.2 * 0.5 + rng.normal(0, 0.03))
    ar = np.array(ar)
    segs = [("p", "a", ar)]
    nc = null_comparison(segs, n_reps=30, seed=3)
    check("shuffle null finds fewer shocks than block null (documents the bias)",
          nc["shuffle_mean"] < nc["block_mean"],
          f"(shuffle {nc['shuffle_mean']:.1f} vs block {nc['block_mean']:.1f})")

    # sensitivity grid shape and monotonicity in threshold
    grid = sensitivity_grid(segs)
    check("grid has 9 cells", len(grid) == 9, f"(got {len(grid)})")
    lenient = grid[(grid.shock_sd == 0.75) & (grid.min_months == 2)]["shocks"].iloc[0]
    strict = grid[(grid.shock_sd == 1.25) & (grid.min_months == 4)]["shocks"].iloc[0]
    check("stricter settings find no more shocks", strict <= lenient,
          f"(lenient {lenient}, strict {strict})")

    print()
    if failures:
        print(f"{len(failures)} v2 test(s) FAILED: {failures}")
        return 1
    print("All v2 self-tests passed.")
    return 0


# ===========================================================================
# ADDITIONS v3: product lifecycle position and cohort vs population recovery.
#
# Both address the same construct-validity threat: that apparent "recovery"
# is a change in WHO is reviewing rather than a change in what reviewers think.
# ===========================================================================

def lifecycle_position(shock_month, first_review_month):
    """Months between a product's first review and a shock's onset."""
    return (shock_month - first_review_month).n


def lifecycle_profile(shocks_with_age, bins=(0, 6, 12, 24, 48, 999)):
    """
    Distribution of product age at shock. If shocks cluster in one age band,
    shocks are lifecycle-driven and product age must be controlled.
    """
    if shocks_with_age.empty:
        return pd.DataFrame()
    labels = [f"{bins[i]}-{bins[i+1]}m" for i in range(len(bins) - 1)]
    binned = pd.cut(shocks_with_age["product_age_at_shock"], bins=bins,
                    labels=labels, right=False)
    out = binned.value_counts().sort_index().rename("shocks").to_frame()
    out["share"] = out["shocks"] / out["shocks"].sum()
    return out


def lifecycle_concentration(shocks_with_age):
    """
    Herfindahl-style concentration of shocks across age bands, in [0,1].
    Near 1/k means shocks are spread evenly; near 1 means one band dominates.
    """
    prof = lifecycle_profile(shocks_with_age)
    if prof.empty:
        return np.nan
    return float((prof["share"] ** 2).sum())


def cohort_feasibility(reviews, product_col="parent_asin", user_col="user_id",
                       time_col="timestamp"):
    """
    Before computing cohort recovery, check it is computable at all.

    On marketplaces where most users review a product once, the pre-shock
    cohort will not reappear after the shock and cohort recovery is undefined.
    Reporting this is itself a finding: it means population-level recovery
    CANNOT be distinguished from population turnover in that data.
    """
    df = reviews.copy()
    df["month"] = pd.to_datetime(df[time_col]).dt.to_period("M")
    per_user_product = df.groupby([product_col, user_col]).size()
    repeat = (per_user_product > 1).sum()
    total = len(per_user_product)
    return dict(
        user_product_pairs=int(total),
        pairs_with_repeat_reviews=int(repeat),
        repeat_rate=float(repeat / total) if total else np.nan,
        computable=bool(total and repeat / total >= 0.02),
    )


def cohort_vs_population_recovery(reviews, product, aspect, onset_month,
                                  baseline_months=BASELINE_MONTHS,
                                  horizon=RECOVERY_HORIZON,
                                  product_col="parent_asin",
                                  user_col="user_id", time_col="timestamp",
                                  text_col="text"):
    """
    Split post-shock sentiment into two sources.

    population: everyone reviewing after the shock
    cohort:     only users who also reviewed during the pre-shock baseline

    If population recovers but cohort does not, the recovery is turnover, not
    perception change, and the recoverability claim must be narrowed.
    Returns None when the cohort is too small to estimate.
    """
    df = reviews[reviews[product_col] == product].copy()
    if df.empty:
        return None
    df["month"] = pd.to_datetime(df[time_col]).dt.to_period("M")
    df["polarity"] = df[text_col].map(crude_polarity)
    df["has_aspect"] = df[text_col].map(lambda t: aspect in tag_aspects(t))
    df = df[df["has_aspect"]]
    if df.empty:
        return None

    pre = df[(df["month"] < onset_month) &
             (df["month"] >= onset_month - baseline_months)]
    post = df[(df["month"] > onset_month) &
              (df["month"] <= onset_month + horizon)]
    if pre.empty or post.empty:
        return None

    cohort_users = set(pre[user_col])
    post_cohort = post[post[user_col].isin(cohort_users)]

    return dict(
        baseline=float(pre["polarity"].mean()),
        population_post=float(post["polarity"].mean()),
        cohort_post=float(post_cohort["polarity"].mean()) if len(post_cohort) else np.nan,
        n_pre=int(len(pre)),
        n_post=int(len(post)),
        n_post_cohort=int(len(post_cohort)),
        cohort_estimable=bool(len(post_cohort) >= 10),
    )


def turnover_warning(result):
    """Interpret one cohort-vs-population result."""
    if result is None or not result["cohort_estimable"]:
        return "cohort not estimable - recovery cannot be attributed"
    base, pop, coh = result["baseline"], result["population_post"], result["cohort_post"]
    level = RECOVERY_FRACTION * base
    pop_rec, coh_rec = pop >= level, coh >= level
    if pop_rec and not coh_rec:
        return "TURNOVER: population recovered, original cohort did not"
    if pop_rec and coh_rec:
        return "genuine: both recovered"
    if not pop_rec and coh_rec:
        return "unusual: cohort recovered but population did not"
    return "neither recovered"


def _selftest_v3():
    failures = []

    def check(name, condition, detail=""):
        if condition:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    print("Self-tests for v3 additions:\n")

    m0 = pd.Period("2020-01", freq="M")
    check("lifecycle position arithmetic",
          lifecycle_position(pd.Period("2021-03", freq="M"), m0) == 14)

    # concentration: all shocks in one band -> high; spread -> low
    concentrated = pd.DataFrame({"product_age_at_shock": [2, 3, 4, 1, 5] * 4})
    spread = pd.DataFrame({"product_age_at_shock": [2, 8, 15, 30, 60] * 4})
    check("concentrated shocks give high concentration",
          lifecycle_concentration(concentrated) > 0.9,
          f"(got {lifecycle_concentration(concentrated):.2f})")
    check("spread shocks give lower concentration",
          lifecycle_concentration(spread) < lifecycle_concentration(concentrated))

    # cohort feasibility: single-review users -> not computable
    single = pd.DataFrame({
        "parent_asin": ["A"] * 50,
        "user_id": [f"u{i}" for i in range(50)],
        "timestamp": pd.date_range("2020-01-01", periods=50, freq="D"),
    })
    check("all-single-review data flagged not computable",
          cohort_feasibility(single)["computable"] is False)

    repeated = pd.DataFrame({
        "parent_asin": ["A"] * 50,
        "user_id": [f"u{i % 10}" for i in range(50)],
        "timestamp": pd.date_range("2020-01-01", periods=50, freq="D"),
    })
    check("repeat-review data flagged computable",
          cohort_feasibility(repeated)["computable"] is True)

    # THE KEY TEST: construct a turnover scenario and confirm it is caught.
    # Pre-shock cohort stays negative afterwards; new users are positive.
    rows = []
    for i in range(20):  # pre-shock: cohort is happy
        rows.append(("A", f"old{i}", "2020-06-15", "battery great works well"))
    for i in range(20):  # post-shock: same cohort is unhappy
        rows.append(("A", f"old{i}", "2021-03-15", "battery broke terrible"))
    # Enough new happy users that the POPULATION mean clears the recovery bar
    # while the cohort mean does not. This is the turnover signature.
    for i in range(400):
        rows.append(("A", f"new{i}", "2021-03-15", "battery great works well"))
    rev = pd.DataFrame(rows, columns=["parent_asin", "user_id", "timestamp", "text"])

    res = cohort_vs_population_recovery(rev, "A", "battery",
                                        pd.Period("2020-12", freq="M"))
    check("turnover scenario is estimable", res is not None and res["cohort_estimable"])
    if res:
        check("population post is higher than cohort post",
              res["population_post"] > res["cohort_post"],
              f"(pop {res['population_post']:.2f}, cohort {res['cohort_post']:.2f})")
        check("turnover is flagged", turnover_warning(res).startswith("TURNOVER"),
              f"(got '{turnover_warning(res)}')")

    # Genuine recovery scenario: cohort itself returns to positive.
    rows = []
    for i in range(20):
        rows.append(("B", f"old{i}", "2020-06-15", "battery great works well"))
    for i in range(20):
        rows.append(("B", f"old{i}", "2021-03-15", "battery great works well"))
    rev2 = pd.DataFrame(rows, columns=["parent_asin", "user_id", "timestamp", "text"])
    res2 = cohort_vs_population_recovery(rev2, "B", "battery",
                                         pd.Period("2020-12", freq="M"))
    check("genuine recovery not flagged as turnover",
          res2 and turnover_warning(res2) == "genuine: both recovered",
          f"(got '{turnover_warning(res2) if res2 else 'none'}')")

    print()
    if failures:
        print(f"{len(failures)} v3 test(s) FAILED: {failures}")
        return 1
    print("All v3 self-tests passed.")
    return 0


# ===========================================================================
# ADDITION v3.1: Recovery Attribution Ratio.
#
# A raw ratio of post-shock sentiments is numerically unstable: when the
# population barely recovers, the denominator approaches zero and the ratio
# explodes. Instead each group is scored as the FRACTION OF THE SHOCK GAP
# CLOSED, whose denominator is the shock depth and is strictly positive.
# ===========================================================================

def gap_closed(baseline, trough, post):
    """
    Fraction of the shock gap recovered, in the natural scale of the series.

    1.0 = fully back to baseline, 0.0 = still at the trough.
    Values may exceed 1 (overshoot) or fall below 0 (further decline).
    """
    depth = baseline - trough
    if depth <= 0:
        return np.nan          # not a shock; undefined
    return (post - trough) / depth


def recovery_attribution(baseline, trough, population_post, cohort_post,
                         min_population_closed=0.20):
    """
    Compare how much of the shock gap the original cohort closed versus the
    whole population.

    RAR near 1  -> the same customers came back; recovery is genuine
    RAR near 0  -> recovery is composition change, not perception change

    RAR is withheld when the population itself barely recovered, because the
    ratio is uninformative and unstable there. This is a deliberate refusal
    to report a number rather than a gap in the implementation.
    """
    pop_closed = gap_closed(baseline, trough, population_post)
    coh_closed = gap_closed(baseline, trough, cohort_post)

    out = dict(population_gap_closed=pop_closed, cohort_gap_closed=coh_closed,
               rar=np.nan, rar_reportable=False, note="")

    if np.isnan(pop_closed) or np.isnan(coh_closed):
        out["note"] = "undefined: no shock depth or cohort not estimable"
        return out
    if pop_closed < min_population_closed:
        out["note"] = (f"withheld: population closed only {pop_closed:.2f} of the gap; "
                       "ratio is unstable below the threshold")
        return out

    out["rar"] = coh_closed / pop_closed
    out["rar_reportable"] = True
    if out["rar"] < 0.5:
        out["note"] = "most of the recovery is population turnover"
    elif out["rar"] > 0.85:
        out["note"] = "recovery is largely the original customers"
    else:
        out["note"] = "mixed: both turnover and genuine return contribute"
    return out


def _selftest_v31():
    failures = []

    def check(name, condition, detail=""):
        if condition:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    print("Self-tests for v3.1 (recovery attribution):\n")

    # gap_closed basics
    check("full recovery closes the whole gap",
          abs(gap_closed(1.0, 0.0, 1.0) - 1.0) < 1e-9)
    check("no recovery closes none of the gap",
          abs(gap_closed(1.0, 0.0, 0.0)) < 1e-9)
    check("half recovery closes half the gap",
          abs(gap_closed(1.0, 0.0, 0.5) - 0.5) < 1e-9)
    check("overshoot exceeds 1", gap_closed(1.0, 0.0, 1.3) > 1.0)
    check("further decline goes negative", gap_closed(1.0, 0.0, -0.2) < 0)
    check("zero depth is undefined", np.isnan(gap_closed(1.0, 1.0, 1.0)))

    # turnover: population closes most of the gap, cohort closes almost none
    r = recovery_attribution(baseline=1.0, trough=-1.0,
                             population_post=0.8, cohort_post=-0.9)
    check("turnover is reportable", r["rar_reportable"])
    check("turnover gives low RAR", r["rar"] < 0.2, f"(got {r['rar']:.2f})")
    check("turnover note is correct", "turnover" in r["note"])

    # genuine: both close the gap similarly
    r = recovery_attribution(1.0, -1.0, population_post=0.8, cohort_post=0.75)
    check("genuine gives RAR near 1", 0.85 < r["rar"] < 1.05, f"(got {r['rar']:.2f})")
    check("genuine note is correct", "original customers" in r["note"])

    # THE STABILITY TEST: when the population barely recovers, the raw ratio
    # would explode. Confirm the guard fires instead of emitting a number.
    r = recovery_attribution(1.0, -1.0, population_post=-0.95, cohort_post=-0.5)
    check("unstable case is withheld, not reported", not r["rar_reportable"])
    check("withheld case has explanatory note", "withheld" in r["note"])
    check("withheld case returns NaN not a fabricated value", np.isnan(r["rar"]))

    # Demonstrate what the naive ratio would have produced in that same case,
    # to justify the guard in the manuscript.
    naive = (-0.5) / (-0.95)
    check("naive ratio would have looked plausible but is meaningless",
          0.4 < naive < 0.7, f"(naive={naive:.2f})")

    print()
    if failures:
        print(f"{len(failures)} v3.1 test(s) FAILED: {failures}")
        return 1
    print("All v3.1 self-tests passed.")
    return 0
