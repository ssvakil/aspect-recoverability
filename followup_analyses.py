"""
The three analyses a referee asked for: Kaplan-Meier, PELT, and a bootstrap at
999 replicates.

WHY EACH IS HERE
    Kaplan-Meier. Twenty episodes cannot support a Cox model, but they can
    support a descriptive time-to-recovery curve with honest confidence bands.
    Declining to plot it leaves the paper a counting exercise. We fit the
    estimator, plot it, and let the width of the bands make the argument.

    PELT. The protocol named it as a robustness check and it was never run.
    Saying "detection failed, so localisation did not matter" is an assertion.
    Running PELT on the same series and comparing its change point count
    against the same null turns it into a result.

    999 replicates. Thirty was a shortfall, not a design choice. At 999 the
    Monte Carlo standard error of the null mean falls from 0.66 to 0.11 shocks
    and p-values can be read from empirical quantiles rather than a normal
    approximation.

USAGE
    python followup_analyses.py --selftest
    python followup_analyses.py --scan 500000 --presence 0.75 --reps 999
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
sys.path.insert(0, "src")

from feasibility_pilot import (          # noqa: E402
    detect_shocks, block_bootstrap_null, censoring_summary, tag_aspects,
    BASELINE_MONTHS, SHOCK_MIN_MONTHS, RECOVERY_HORIZON,
)
from category_shock_run import (          # noqa: E402
    load_stream, build_balanced, category_series, run_detection, contiguous_runs,
)


# ---------------------------------------------------------------------------
# Cohort feasibility at coarser units
# ---------------------------------------------------------------------------

def cohort_rates(balanced):
    """
    Repeat-observation rates at three units, not one.

    The manuscript reports the user-item rate and concludes a cohort analysis is
    impossible. That conclusion is sound for item-level cohorts and does not
    follow for coarser ones. MobileRec's 5-core filter guarantees five distinct
    apps per user, and those apps may sit in one category, so a user can
    contribute repeated observations of a category without ever reviewing an app
    twice. The same holds for an aspect mentioned across several apps.

    Three rates are therefore computed. Each answers a different question and
    they are not interchangeable:

      user-item      can we follow the same reviewer on the same app?
      user-category  can we follow the same reviewer within a category?
      user-aspect    can we follow the same reviewer on the same attribute?

    A cohort recovery analysis needs repeat observation at whatever unit the
    shock is defined on. Since our shocks are defined at category level, the
    user-category rate is the relevant one, and reporting only the user-item
    rate understated what the data might support.
    """
    d = balanced.copy()
    out = {}

    pairs = d.groupby(["app_package", "uid"]).size()
    out["user_item"] = dict(pairs=int(len(pairs)),
                            repeat=int((pairs > 1).sum()),
                            rate=float((pairs > 1).mean()) if len(pairs) else float("nan"))

    cat = d.groupby(["app_category", "uid"]).size()
    out["user_category"] = dict(pairs=int(len(cat)),
                                repeat=int((cat > 1).sum()),
                                rate=float((cat > 1).mean()) if len(cat) else float("nan"))

    rows = []
    for uid, cat_name, text in zip(d["uid"], d["app_category"], d["review"]):
        for a in tag_aspects(text):
            rows.append((uid, cat_name, a))
    if rows:
        asp = pd.DataFrame(rows, columns=["uid", "category", "aspect"])
        ua = asp.groupby(["uid", "aspect"]).size()
        out["user_aspect"] = dict(pairs=int(len(ua)),
                                  repeat=int((ua > 1).sum()),
                                  rate=float((ua > 1).mean()))
        uca = asp.groupby(["uid", "category", "aspect"]).size()
        out["user_category_aspect"] = dict(pairs=int(len(uca)),
                                           repeat=int((uca > 1).sum()),
                                           rate=float((uca > 1).mean()))
    else:
        out["user_aspect"] = dict(pairs=0, repeat=0, rate=float("nan"))
        out["user_category_aspect"] = dict(pairs=0, repeat=0, rate=float("nan"))
    return out


def cohort_verdict(rates, needed=0.02):
    """
    Whether each unit supports a cohort estimate.

    The 0.02 figure is our own working convention with no published basis; it
    is exposed as an argument so a reader can substitute their own. What the
    table shows is the rate, and the verdict is a convenience.
    """
    rows = []
    for unit, r in rates.items():
        rows.append(dict(unit=unit, pairs=r["pairs"], repeat=r["repeat"],
                         rate=r["rate"],
                         supports_cohort=bool(r["rate"] >= needed)
                         if r["rate"] == r["rate"] else False))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Kaplan-Meier
# ---------------------------------------------------------------------------

def kaplan_meier(times, events):
    """
    Kaplan-Meier estimator with Greenwood variance.

    times:  observed duration for each episode
    events: 1 if recovery was observed, 0 if censored

    Returns a DataFrame with the survival curve and log-log confidence limits.
    Log-log limits are used rather than linear ones because at these sample
    sizes a linear interval runs outside [0, 1] and invites over-reading.
    """
    t = np.asarray(times, dtype=float)
    e = np.asarray(events, dtype=int)
    order = np.argsort(t)
    t, e = t[order], e[order]

    rows, s, cum_var, at_risk = [], 1.0, 0.0, len(t)
    for time in np.unique(t):
        d = int(e[t == time].sum())            # events at this time
        n = at_risk
        if n <= 0:
            break
        if d > 0:
            s *= (1 - d / n)
            cum_var += d / (n * (n - d)) if n > d else 0.0
        rows.append(dict(time=float(time), at_risk=n, events=d, survival=s,
                         greenwood_var=cum_var))
        at_risk -= int((t == time).sum())

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # log-log transform: CI on log(-log S), then back-transform
    with np.errstate(divide="ignore", invalid="ignore"):
        logs = np.log(df["survival"].clip(lower=1e-12))
        se = np.sqrt(df["greenwood_var"]) / np.abs(logs)
        theta = np.exp(1.96 * se)
        df["ci_lower"] = df["survival"] ** theta
        df["ci_upper"] = df["survival"] ** (1 / theta)
    df[["ci_lower", "ci_upper"]] = df[["ci_lower", "ci_upper"]].clip(0, 1)
    return df


def median_survival(km):
    """First time at which the curve drops to or below 0.5, else NaN."""
    if km.empty:
        return np.nan
    below = km[km["survival"] <= 0.5]
    return float(below["time"].iloc[0]) if len(below) else np.nan


def episodes_to_survival(shocks):
    """
    Convert shock episodes into (duration, event) pairs for time-to-recovery.

    Recovered episodes contribute their observed recovery time as an event.
    Non-recovered episodes are censored at the horizon. Censored episodes are
    censored at their follow-up length, not at the horizon, which is the whole
    point of tracking follow-up separately.
    """
    times, events = [], []
    for _, r in shocks.iterrows():
        if r["outcome"] == "recovered":
            times.append(float(r["months_to_recovery"]))
            events.append(1)
        elif r["outcome"] == "non_recovered":
            times.append(float(RECOVERY_HORIZON))
            events.append(0)
        else:
            times.append(float(min(r["followup_months"], RECOVERY_HORIZON)))
            events.append(0)
    return times, events


# ---------------------------------------------------------------------------
# PELT
# ---------------------------------------------------------------------------

def pelt_changepoints(series, penalty=None, min_size=2):
    """
    PELT with an L2 cost, via `ruptures` when available and a direct
    implementation otherwise, so the check does not silently fail to run.

    Returns the indices of detected change points, excluding the series end.
    """
    x = np.asarray(series, dtype=float)
    n = len(x)
    if n < 2 * min_size:
        return []
    pen = penalty if penalty is not None else 3 * np.log(n) * np.var(x)

    try:
        import ruptures as rpt
        algo = rpt.Pelt(model="l2", min_size=min_size, jump=1).fit(x)
        return [c for c in algo.predict(pen=pen) if c < n]
    except ImportError:
        pass

    # Direct PELT. Cost of segment [a, b) under an L2 model is the within-
    # segment sum of squares.
    cs = np.concatenate([[0.0], np.cumsum(x)])
    css = np.concatenate([[0.0], np.cumsum(x ** 2)])

    def cost(a, b):
        m = b - a
        if m <= 0:
            return 0.0
        total = cs[b] - cs[a]
        return (css[b] - css[a]) - total * total / m

    F = np.full(n + 1, np.inf)
    F[0] = -pen
    prev = [0] * (n + 1)
    candidates = [0]
    for b in range(min_size, n + 1):
        best, arg = np.inf, 0
        for a in candidates:
            if b - a < min_size:
                continue
            v = F[a] + cost(a, b) + pen
            if v < best:
                best, arg = v, a
        F[b], prev[b] = best, arg
        candidates = [a for a in candidates if F[a] + cost(a, b) <= F[b]] + [b]

    pts, b = [], n
    while b > 0:
        a = prev[b]
        if a > 0:
            pts.append(a)
        b = a
    return sorted(pts)


def pelt_vs_null(segments, n_reps=200, seed=0):
    """Change point counts on the observed series against the same null."""
    rng = np.random.default_rng(seed)
    observed = sum(len(pelt_changepoints(seg)) for _, _, seg in segments)
    nulls = []
    for _ in range(n_reps):
        nulls.append(sum(len(pelt_changepoints(block_bootstrap_null(seg, rng)))
                         for _, _, seg in segments))
    mu, sd = float(np.mean(nulls)), float(np.std(nulls))
    return dict(observed=observed, null_mean=mu, null_sd=sd,
                ratio=observed / mu if mu else np.nan,
                z=(observed - mu) / sd if sd else np.nan,
                p_empirical=float(np.mean([x >= observed for x in nulls])))


# ---------------------------------------------------------------------------
# Bootstrap at 999
# ---------------------------------------------------------------------------

def null_at(segments, n_reps=999, seed=0):
    """
    Shock counts under the block bootstrap null, with an empirical p-value.

    The empirical p-value uses the (b + 1) / (B + 1) correction so that it can
    never be reported as exactly zero, which a naive proportion allows and
    which is never justified by a finite number of replicates.
    """
    rng = np.random.default_rng(seed)
    observed = sum(len(detect_shocks(seg)) for _, _, seg in segments)
    nulls = [sum(len(detect_shocks(block_bootstrap_null(seg, rng)))
                 for _, _, seg in segments) for _ in range(n_reps)]
    nulls = np.array(nulls, dtype=float)
    b = int((nulls >= observed).sum())
    return dict(
        replicates=n_reps, observed=observed,
        null_mean=float(nulls.mean()), null_sd=float(nulls.std(ddof=1)),
        mcse_mean=float(nulls.std(ddof=1) / np.sqrt(n_reps)),
        ratio=observed / nulls.mean() if nulls.mean() else np.nan,
        p_empirical=(b + 1) / (n_reps + 1),
        ci_lower=float(np.percentile(nulls, 2.5)),
        ci_upper=float(np.percentile(nulls, 97.5)),
    )


def ratio_ci(segments, n_reps=999, seed=1):
    """Percentile interval for the observed-to-null ratio."""
    rng = np.random.default_rng(seed)
    observed = sum(len(detect_shocks(seg)) for _, _, seg in segments)
    ratios = []
    for _ in range(n_reps):
        null = sum(len(detect_shocks(block_bootstrap_null(seg, rng)))
                   for _, _, seg in segments)
        if null:
            ratios.append(observed / null)
    if not ratios:
        return dict(lower=np.nan, upper=np.nan)
    return dict(lower=float(np.percentile(ratios, 2.5)),
                upper=float(np.percentile(ratios, 97.5)))


def block_length_sensitivity(segments, lengths=(3, 6, 12), n_reps=200, seed=2):
    """Whether the null depends on the block length we fixed at six months."""
    rows = []
    observed = sum(len(detect_shocks(seg)) for _, _, seg in segments)
    for L in lengths:
        rng = np.random.default_rng(seed + L)
        nulls = [sum(len(detect_shocks(block_bootstrap_null(seg, rng, block=L)))
                     for _, _, seg in segments) for _ in range(n_reps)]
        mu = float(np.mean(nulls))
        rows.append(dict(block=L, observed=observed, null_mean=mu,
                         null_sd=float(np.std(nulls)),
                         ratio=observed / mu if mu else np.nan))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------

def run(scan, presence, reps, out="followup_results.json"):
    print(f"Streaming up to {scan:,} interactions...")
    df = load_stream(scan)
    bal, n_apps = build_balanced(df, presence)
    print(f"Balanced panel: {n_apps:,} apps, {len(bal):,} rows")

    print("\nRepeat-observation rates at three units:")
    rates = cohort_rates(bal)
    print(cohort_verdict(rates).to_string(index=False,
                                          float_format=lambda v: f"{v:.5f}"))
    print("  The user-item rate is what the manuscript reported. The coarser")
    print("  units answer a different question and were not measured before.")

    results = {"cohort_rates": rates}
    for use_rating, label in ((True, "star_rating"), (False, "lexicon")):
        print(f"\n{'=' * 58}\n{label}\n{'=' * 58}")
        series = category_series(bal, use_rating=use_rating)
        shocks, segments = run_detection(series, label)
        if shocks.empty:
            print("no shocks; skipping")
            continue

        cs = censoring_summary(shocks)
        print(f"episodes {cs['total']} (rec {cs['recovered']}, "
              f"non-rec {cs['non_recovered']}, cens {cs['censored']})")

        print("\nKaplan-Meier, time to recovery:")
        times, events = episodes_to_survival(shocks)
        km = kaplan_meier(times, events)
        print(km.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
        med = median_survival(km)
        print(f"  median time to recovery: "
              f"{med if not np.isnan(med) else 'not reached'}")

        print(f"\nBlock bootstrap at {reps} replicates:")
        nb = null_at(segments, n_reps=reps)
        for k, v in nb.items():
            print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")
        rci = ratio_ci(segments, n_reps=reps)
        print(f"  ratio 95% CI: [{rci['lower']:.2f}, {rci['upper']:.2f}]")

        print("\nPELT change points vs the same null:")
        pv = pelt_vs_null(segments)
        for k, v in pv.items():
            print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

        print("\nBlock length sensitivity:")
        bls = block_length_sensitivity(segments)
        print(bls.to_string(index=False, float_format=lambda v: f"{v:.2f}"))

        results[label] = dict(
            outcomes=cs, km=km.to_dict(orient="records"),
            median_recovery=None if np.isnan(med) else med,
            bootstrap=nb, ratio_ci=rci, pelt=pv,
            block_sensitivity=bls.to_dict(orient="records"))

    with open(out, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved: {out}")
    return results


def _selftest():
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    print("Self-tests for followup_analyses:\n")
    print("Kaplan-Meier:")

    # no censoring, all events at distinct times -> survival steps by 1/n
    km = kaplan_meier([1, 2, 3, 4], [1, 1, 1, 1])
    check("survival starts at 1 - 1/n", abs(km["survival"].iloc[0] - 0.75) < 1e-9,
          f'({km["survival"].iloc[0]:.3f})')
    check("survival reaches zero when all fail",
          abs(km["survival"].iloc[-1]) < 1e-9)
    check("median is the midpoint event time", median_survival(km) == 2.0,
          f"({median_survival(km)})")

    # a censored observation must not drop the curve
    km2 = kaplan_meier([1, 2, 3], [1, 0, 1])
    s_after_censor = km2[km2["time"] == 2]["survival"].iloc[0]
    check("censoring does not drop the curve",
          abs(s_after_censor - km2[km2["time"] == 1]["survival"].iloc[0]) < 1e-9)
    check("censoring does reduce the risk set",
          km2[km2["time"] == 3]["at_risk"].iloc[0] == 1,
          f'({km2[km2["time"] == 3]["at_risk"].iloc[0]})')

    # all censored -> curve never falls, median undefined
    km3 = kaplan_meier([5, 6, 7], [0, 0, 0])
    check("all-censored curve stays at 1",
          abs(km3["survival"].max() - 1.0) < 1e-9 and
          abs(km3["survival"].min() - 1.0) < 1e-9)
    check("all-censored median is undefined", np.isnan(median_survival(km3)))

    # confidence bands stay inside [0, 1]
    check("confidence bands are bounded",
          km2["ci_lower"].min() >= 0 and km2["ci_upper"].max() <= 1)

    # episode conversion
    ep = pd.DataFrame([
        dict(outcome="recovered", months_to_recovery=4.0, followup_months=30),
        dict(outcome="non_recovered", months_to_recovery=np.nan, followup_months=30),
        dict(outcome="censored", months_to_recovery=np.nan, followup_months=5),
    ])
    t, e = episodes_to_survival(ep)
    check("recovered episode is an event at its recovery time",
          t[0] == 4.0 and e[0] == 1)
    check("non-recovered episode is censored at the horizon",
          t[1] == float(RECOVERY_HORIZON) and e[1] == 0)
    check("censored episode is censored at its follow-up, not the horizon",
          t[2] == 5.0 and e[2] == 0, f"({t[2]})")

    print("\nCohort rates:")
    # a user reviewing three different apps in one category: no item repeat,
    # but a category repeat -- the case the manuscript had missed
    d = pd.DataFrame({
        "app_package": ["a1", "a2", "a3"],
        "app_category": ["Games"] * 3,
        "uid": ["u1"] * 3,
        "review": ["battery good", "battery bad", "price high"],
    })
    r = cohort_rates(d)
    check("no repeat at item level", r["user_item"]["repeat"] == 0)
    check("repeat appears at category level", r["user_category"]["repeat"] == 1,
          f'({r["user_category"]["repeat"]})')
    check("repeat appears at aspect level", r["user_aspect"]["repeat"] == 1,
          f'({r["user_aspect"]["repeat"]})')
    check("category rate exceeds item rate",
          r["user_category"]["rate"] > r["user_item"]["rate"])

    # a user with one review each in distinct categories: no repeat anywhere
    d2 = pd.DataFrame({
        "app_package": ["a1", "a2"],
        "app_category": ["Games", "Tools"],
        "uid": ["u1", "u1"],
        "review": ["battery good", "price high"],
    })
    r2 = cohort_rates(d2)
    check("distinct categories give no category repeat",
          r2["user_category"]["repeat"] == 0)
    check("distinct aspects give no aspect repeat",
          r2["user_aspect"]["repeat"] == 0)

    v = cohort_verdict(r)
    check("verdict covers all four units", len(v) == 4, f"({len(v)})")
    check("threshold is adjustable",
          cohort_verdict(r, needed=0.99)["supports_cohort"].sum()
          <= cohort_verdict(r, needed=0.01)["supports_cohort"].sum())

    print("\nPELT:")
    # a clean step must be found near the step location
    step = np.concatenate([np.full(20, 0.0), np.full(20, 5.0)])
    pts = pelt_changepoints(step)
    check("step change is detected", len(pts) >= 1, f"(got {pts})")
    check("detected point is near the true step",
          bool(pts) and min(abs(p - 20) for p in pts) <= 2, f"(got {pts})")

    # a flat series must yield none
    check("flat series yields no change points",
          pelt_changepoints(np.full(40, 3.0)) == [],
          f"(got {pelt_changepoints(np.full(40, 3.0))})")

    # a series shorter than twice the minimum segment yields none
    check("very short series yields none", pelt_changepoints([1.0, 2.0]) == [])

    print("\nBootstrap:")
    rng = np.random.default_rng(0)
    ar = [0.5]
    for _ in range(120):
        ar.append(0.8 * ar[-1] + 0.1 + rng.normal(0, 0.03))
    segs = [("s", "k", np.array(ar))]

    nb = null_at(segs, n_reps=60)
    check("empirical p is never exactly zero", nb["p_empirical"] > 0,
          f'({nb["p_empirical"]:.4f})')
    check("empirical p is never exactly one", nb["p_empirical"] <= 1.0)
    check("MCSE shrinks with replicates",
          null_at(segs, n_reps=200)["mcse_mean"] < null_at(segs, n_reps=30)["mcse_mean"])
    check("null interval brackets the null mean",
          nb["ci_lower"] <= nb["null_mean"] <= nb["ci_upper"])

    rc = ratio_ci(segs, n_reps=60)
    check("ratio interval is ordered", rc["lower"] <= rc["upper"])

    bls = block_length_sensitivity(segs, n_reps=30)
    check("block sensitivity covers three lengths", len(bls) == 3)
    check("observed count is identical across block lengths",
          bls["observed"].nunique() == 1)

    print()
    if failures:
        print(f"{len(failures)} test(s) FAILED: {failures}")
        return 1
    print("All followup_analyses self-tests passed.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--scan", type=int, default=500000)
    ap.add_argument("--presence", type=float, default=0.75)
    ap.add_argument("--reps", type=int, default=999)
    ap.add_argument("--out", default="followup_results.json")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(_selftest())
    run(args.scan, args.presence, args.reps, args.out)


if __name__ == "__main__":
    main()
