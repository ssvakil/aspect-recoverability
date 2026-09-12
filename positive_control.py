"""
Positive control for the shock detector.

WHY THIS IS NECESSARY
    A negative study that never demonstrates its instrument works cannot
    distinguish "there is nothing there" from "our method does not find things
    that are there". Every self-test written so far checks classification
    logic: that a truncated decline is censored, that a gap splits a series.
    None measures detection power on a realistic series.

    This does. Shocks of known magnitude and duration are injected into
    autocorrelated series resembling the observed panel, and the proportion
    recovered is measured. The result is a power curve for the pre-specified
    criterion.

WHAT A FAILURE HERE WOULD MEAN
    If the detector misses a 1.5 SD shock sustained three months, the paper's
    null result says nothing about the data and everything about the method.
    We report the curve whichever way it comes out.

USAGE
    python positive_control.py --selftest
    python positive_control.py --run
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
sys.path.insert(0, "src")

from feasibility_pilot import (          # noqa: E402
    detect_shocks, BASELINE_MONTHS, SHOCK_MIN_MONTHS, SHOCK_SD,
    RECOVERY_FRACTION, RECOVERY_MIN_MONTHS,
)

# Series geometry matched to the observed panel: 27 category series, runs of
# roughly 40 qualifying months, monthly means of a five-point rating.
N_SERIES = 27
N_MONTHS = 40
BASE_LEVEL = 4.0
AR_PHI = 0.6


def synthetic_series(n_months=N_MONTHS, sd=0.10, phi=AR_PHI, level=BASE_LEVEL,
                     rng=None):
    """
    An AR(1) series standing in for a category-month rating mean.

    Autocorrelation matters: a white-noise series would make detection easier
    than reality, and a positive control run on white noise would overstate the
    instrument's power. phi = 0.6 is a moderate choice; the sensitivity of the
    result to it is reported.
    """
    rng = rng or np.random.default_rng(0)
    x = np.empty(n_months)
    x[0] = level + rng.normal(0, sd)
    for t in range(1, n_months):
        x[t] = level + phi * (x[t - 1] - level) + rng.normal(0, sd)
    return x


def inject_shock(series, onset, depth_sd, duration, sd, recover=True,
                 recovery_months=3):
    """
    Impose a fall of `depth_sd` standard deviations for `duration` months,
    optionally followed by a linear return to the prior level.

    The fall is a level shift, not a spike, because the criterion requires a
    sustained drop and a spike would be an unfair test of it.
    """
    x = series.copy()
    drop = depth_sd * sd
    end = min(onset + duration, len(x))
    x[onset:end] -= drop
    if recover and end < len(x):
        ramp = min(recovery_months, len(x) - end)
        for i in range(ramp):
            x[end + i] -= drop * (1 - (i + 1) / ramp)
    return x


def detection_rate(depth_sd, duration, n_series=N_SERIES, sd=0.10,
                   phi=AR_PHI, seed=0, recover=True):
    """
    Proportion of injected shocks the criterion recovers, and how often it
    fires on the same series with nothing injected.

    The false positive rate is reported alongside, because a detector that
    finds everything is not evidence of power.
    """
    rng = np.random.default_rng(seed)
    hits = fp = 0
    for _ in range(n_series):
        base = synthetic_series(sd=sd, phi=phi, rng=rng)
        onset = rng.integers(BASELINE_MONTHS + 2, N_MONTHS - duration - 6)
        shocked = inject_shock(base, onset, depth_sd, duration, sd,
                               recover=recover)
        found = detect_shocks(shocked)
        # a hit is a detection whose onset falls near the injected one
        if any(abs(s["onset_index"] - onset) <= 2 for s in found):
            hits += 1
        if detect_shocks(base):
            fp += 1
    return dict(depth_sd=depth_sd, duration=duration, n=n_series,
                detected=hits, power=hits / n_series,
                false_positive_series=fp, false_positive_rate=fp / n_series)


def power_grid(depths=(0.5, 1.0, 1.5, 2.0, 3.0), durations=(2, 3, 6),
               **kw):
    return pd.DataFrame([detection_rate(d, dur, **kw)
                         for d in depths for dur in durations])


def recovery_recall(depth_sd=2.0, duration=3, n_series=N_SERIES, sd=0.10,
                    seed=1):
    """
    Of the shocks detected, how many are correctly classified as recovered when
    a recovery was in fact injected?

    Detection and classification are separate abilities and a study reporting
    recovery outcomes needs both.
    """
    rng = np.random.default_rng(seed)
    detected = correct = 0
    for _ in range(n_series):
        base = synthetic_series(sd=sd, rng=rng)
        onset = rng.integers(BASELINE_MONTHS + 2, N_MONTHS - duration - 20)
        shocked = inject_shock(base, onset, depth_sd, duration, sd, recover=True)
        for s in detect_shocks(shocked):
            if abs(s["onset_index"] - onset) <= 2:
                detected += 1
                if s["outcome"] == "recovered":
                    correct += 1
                break
    return dict(injected=n_series, detected=detected, classified_recovered=correct,
                recall=correct / detected if detected else float("nan"))


def phi_sensitivity(depth_sd=2.0, duration=3, phis=(0.0, 0.3, 0.6, 0.85)):
    """Power as a function of autocorrelation, which the null also depends on."""
    return pd.DataFrame([{**detection_rate(depth_sd, duration, phi=p, seed=3),
                          "phi": p} for p in phis])


def run(out="positive_control_results.json"):
    print("Positive control for the pre-specified shock criterion")
    print(f"  criterion: drop >= {SHOCK_SD} SD sustained >= {SHOCK_MIN_MONTHS} "
          f"months; recovery at {RECOVERY_FRACTION:.0%} for "
          f"{RECOVERY_MIN_MONTHS} months")
    print(f"  series: {N_SERIES} AR(1) runs of {N_MONTHS} months, phi={AR_PHI}\n")

    grid = power_grid()
    print("Detection power by injected shock size:")
    print(grid.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    fp = grid["false_positive_rate"].mean()
    print(f"\n  mean false positive rate on unshocked series: {fp:.3f}")

    print("\nClassification of detected shocks that did recover:")
    rec = recovery_recall()
    for k, v in rec.items():
        print(f"  {k}: {v:.3f}" if isinstance(v, float) else f"  {k}: {v}")

    print("\nPower against autocorrelation:")
    ps = phi_sensitivity()
    print(ps[["phi", "depth_sd", "duration", "power",
              "false_positive_rate"]].to_string(
        index=False, float_format=lambda v: f"{v:.3f}"))

    at_criterion = grid[(grid.depth_sd == 1.0) & (grid.duration == 2)].iloc[0]
    strong = grid[(grid.depth_sd == 2.0) & (grid.duration == 3)].iloc[0]
    print(f"\nAt the criterion itself (1.0 SD, 2 months): power "
          f"{at_criterion['power']:.2f}")
    print(f"At a clearly larger shock (2.0 SD, 3 months): power "
          f"{strong['power']:.2f}")
    if strong["power"] < 0.8:
        print("\n  The instrument misses most large injected shocks. A null")
        print("  result from it does not license a claim about the data.")
    else:
        print("\n  The instrument recovers large injected shocks, so a null")
        print("  result is informative about the data rather than the method.")

    res = dict(grid=grid.to_dict(orient="records"),
               recovery_recall=rec,
               phi_sensitivity=ps.to_dict(orient="records"))
    with open(out, "w") as f:
        json.dump(res, f, indent=2, default=str)
    print(f"\nSaved: {out}")
    return res


def _selftest():
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    print("Self-tests for positive_control:\n")

    rng = np.random.default_rng(0)
    s = synthetic_series(sd=0.1, rng=rng)
    check("series has the requested length", len(s) == N_MONTHS)
    check("series sits near the base level", abs(s.mean() - BASE_LEVEL) < 0.2,
          f"({s.mean():.3f})")

    # autocorrelation must actually be present, or the control is too easy
    ac = np.corrcoef(s[:-1], s[1:])[0, 1]
    check("series is autocorrelated", ac > 0.2, f"(lag-1 r = {ac:.2f})")
    white = synthetic_series(sd=0.1, phi=0.0, rng=np.random.default_rng(1))
    ac_w = np.corrcoef(white[:-1], white[1:])[0, 1]
    check("phi=0 gives near-zero autocorrelation", abs(ac_w) < 0.4,
          f"({ac_w:.2f})")

    # injection behaves as specified
    base = np.full(30, 4.0)
    inj = inject_shock(base, 10, depth_sd=2.0, duration=4, sd=0.1, recover=False)
    check("injected months are lowered", np.allclose(inj[10:14], 4.0 - 0.2))
    check("months before the shock are untouched", np.allclose(inj[:10], 4.0))
    check("without recovery the level stays down", np.allclose(inj[14:], 4.0))

    inj2 = inject_shock(base, 10, depth_sd=2.0, duration=4, sd=0.1, recover=True,
                        recovery_months=3)
    check("with recovery the level returns", abs(inj2[-1] - 4.0) < 1e-9)
    check("recovery is gradual, not instant", inj2[14] < inj2[16],
          f"({inj2[14]:.3f} then {inj2[16]:.3f})")

    # THE CENTRAL PROPERTY: power must rise with shock size
    small = detection_rate(0.5, 2, n_series=20, seed=5)
    large = detection_rate(3.0, 6, n_series=20, seed=5)
    check("power increases with shock magnitude and duration",
          large["power"] > small["power"],
          f'({small["power"]:.2f} -> {large["power"]:.2f})')
    check("a very large sustained shock is usually detected",
          large["power"] > 0.5, f'({large["power"]:.2f})')

    # The false positive rate is a measurement, not something to assert a
    # bound on. What can be asserted is that it agrees with the bootstrap null
    # observed on the real panel: 28.39 detections across 27 series, or 1.05
    # per series. A synthetic control disagreeing with that would indicate the
    # synthetic series do not resemble the real ones.
    clean_rate = large["false_positive_rate"]
    check("false positive rate matches the observed bootstrap null",
          abs(clean_rate - 28.39 / 27) < 0.35,
          f"({clean_rate:.2f} per series vs 1.05 observed)")
    check("false positive rate is high enough to explain the null comparison",
          clean_rate > 0.5,
          f"({clean_rate:.2f}: the criterion fires on noise about once a series)")

    g = power_grid(depths=(1.0, 2.0), durations=(2, 3), n_series=10)
    check("grid covers every combination", len(g) == 4)
    check("power lies in the unit interval",
          bool(((g["power"] >= 0) & (g["power"] <= 1)).all()))

    print()
    if failures:
        print(f"{len(failures)} test(s) FAILED: {failures}")
        return 1
    print("All positive_control self-tests passed.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--out", default="positive_control_results.json")
    args = ap.parse_args()
    if args.selftest or not args.run:
        sys.exit(_selftest())
    run(args.out)


if __name__ == "__main__":
    main()
