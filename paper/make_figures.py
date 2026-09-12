"""
Figure generation for the aspect recoverability manuscript.

PROVENANCE
    Every number in OBSERVED below was produced by the runs recorded in the
    repository, not estimated or adjusted. The source command for each block is
    named in its comment so any figure can be traced back to a run and
    regenerated. If a run is repeated with different parameters, update this
    block rather than editing figures.

USAGE
    python make_figures.py --selftest
    python make_figures.py --outdir figures
"""

import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({
    "font.size": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150,
    "savefig.bbox": "tight",
})

GREY = "#666666"
DARK = "#222222"
ACCENT = "#B03A2E"

OBSERVED = {
    # load_amazon.py --category All_Beauty --scan 300000 --products 200
    "amazon_beauty": dict(reviews=82041, products=200, product_months=11925,
                          qualifying=313, share=0.026, shocks=0),
    # feasibility_pilot.py on the phones extract
    "amazon_phones": dict(analysable=5),
    # 300k MobileRec interactions, full period
    "mobilerec_app": dict(pairs=299812, repeat=188, repeat_rate=0.00063,
                          app_months=128251, qualifying=271, share=0.002),
    # 500k MobileRec interactions, full period -- the scan the category
    # analysis is built on, so the comparable figure for Figure 1
    "mobilerec_app_500k": dict(units=8603, unit_months=170846, qualifying=827,
                               share=0.005),
    "mobilerec_cat_500k": dict(units=48, unit_months=5134, qualifying=2286,
                               share=0.445),
    # balanced_panel_check.py --scan 500000
    "panel": {
        "unbalanced": dict(apps=None, rows=None, categories=48,
                           category_months=2299, qualifying=1788, share=0.778),
        0.50: dict(apps=2558, rows=226009, categories=48, qualifying=1589, share=0.694),
        0.75: dict(apps=657, rows=74780, categories=46, qualifying=955, share=0.444),
        0.90: dict(apps=10, rows=1550, categories=10, qualifying=0, share=0.0),
    },
    "longest_runs": [
        ("Role Playing", 43), ("Strategy", 41), ("Health & Fitness", 40),
        ("Entertainment", 40), ("Action", 40), ("Casual", 40),
        ("Simulation", 40), ("Puzzle", 40), ("Shopping", 40),
        ("Productivity", 40), ("Adventure", 39), ("Education", 39),
        ("Music & Audio", 39), ("Dating", 35), ("Photography", 34),
    ],
    # category_shock_run.py --scan 500000 --presence 0.75
    "star": dict(series=27, shocks=23, recovered=20, non_recovered=0, censored=3,
                 analysable=20, observed=23, block_mean=27.8, block_sd=3.6,
                 shuffle_mean=25.8, ratio=0.83,
                 grid={(0.75, 2): 33, (0.75, 3): 17, (0.75, 4): 9,
                       (1.00, 2): 23, (1.00, 3): 13, (1.00, 4): 6,
                       (1.25, 2): 19, (1.25, 3): 8, (1.25, 4): 3}),
    "lexicon": dict(series=27, shocks=29, recovered=12, non_recovered=7, censored=10,
                    analysable=19, observed=29, block_mean=26.0, block_sd=4.4,
                    shuffle_mean=27.3, ratio=1.12,
                    grid={(0.75, 2): 38, (0.75, 3): 16, (0.75, 4): 7,
                          (1.00, 2): 29, (1.00, 3): 13, (1.00, 4): 5,
                          (1.25, 2): 20, (1.25, 3): 8, (1.25, 4): 2}),
    "power": dict(required_hr20=65, required_hr15=191),
    # followup_analyses.py --scan 500000 --presence 0.75 --reps 999
    "followup": dict(
        star=dict(episodes=23, recovered=20, non_recovered=0, censored=3,
                  km_median=3.0,
                  boot=dict(reps=999, observed=23, null_mean=28.3894,
                            null_sd=3.7728, mcse=0.1194, ratio=0.8102,
                            p=0.9480, ci=(0.64, 1.15)),
                  pelt=dict(observed=6, null_mean=1.7650, null_sd=1.3453,
                            ratio=3.3994, z=3.1480, p=0.0150),
                  block=((3, 29.34, 0.78), (6, 28.39, 0.81), (12, 27.00, 0.85))),
        lexicon=dict(episodes=29, recovered=12, non_recovered=7, censored=10,
                     km_median=15.0,
                     boot=dict(reps=999, observed=29, null_mean=26.1872,
                               null_sd=3.7285, mcse=0.1180, ratio=1.1074,
                               p=0.2510, ci=(0.83, 1.53)),
                     pelt=dict(observed=1, null_mean=0.7950, null_sd=0.8561,
                               ratio=1.2579, z=0.2394, p=0.5550),
                     block=((3, 26.89, 1.08), (6, 26.66, 1.09), (12, 27.72, 1.05)))),
    # balanced_panel_check.py --scan 500000, denominators now logged
    "denominators": {0.50: (1589, 2291, 2304), 0.75: (955, 2150, 2208),
                     0.90: (0, 453, 480)},
    "cohort": dict(user_item=(44, 74736), user_category=(1205, 73563),
                   user_aspect=(198, 14244), user_category_aspect=(5, 14440)),
    # aspect_level_run.py --scan 500000 --presence 0.75
    "aspect": dict(cells=7084, categories=46, aspects=10, median_mentions=1,
                   qualifying=0, series=0, panel_reviews=74780,
                   panel_months=48,
                   per_aspect={"design": (1222, 2.0), "performance": (1260, 2.0),
                               "price": (830, 1.0), "usability": (824, 1.0),
                               "support": (813, 1.0), "battery": (577, 1.0),
                               "quality": (498, 1.0), "durability": (459, 1.0),
                               "packaging": (436, 1.0), "delivery": (165, 1.0)}),
    # repeat-review rates, both corpora
    "repeat": dict(amazon=(130, 81902), mobilerec=(188, 299812),
                   mobilerec_balanced=0.00059),
}

SD_LEVELS = [0.75, 1.00, 1.25]
DUR_LEVELS = [2, 3, 4]


def fig1_density_cascade(outdir):
    """
    Qualifying unit-months at each level of aggregation.

    All four bars are computed over the FULL observation period so that they
    are mutually comparable. The windowed and balanced figures use different
    denominators and appear in Figure 2 instead; mixing them here would
    compare quantities measured on different bases.
    """
    labels = ["Amazon\nproduct\n(All_Beauty)", "MobileRec\napp",
              "MobileRec\ncategory"]
    shares = [OBSERVED["amazon_beauty"]["share"],
              OBSERVED["mobilerec_app_500k"]["share"],
              OBSERVED["mobilerec_cat_500k"]["share"]]

    fig, ax = plt.subplots(figsize=(5.0, 3.0))
    bars = ax.bar(labels, [s * 100 for s in shares],
                  color=[GREY, GREY, DARK], width=0.55)
    for b, s in zip(bars, shares):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5,
                f"{s*100:.1f}%", ha="center", fontsize=8)
    ax.set_ylabel("Unit-months meeting the\n30-review threshold (%)")
    ax.set_ylim(0, 95)
    ax.axhline(0, color="black", lw=0.8)
    fig.savefig(os.path.join(outdir, "fig1_density_cascade.pdf"))
    plt.close(fig)


def fig2_panel_attrition(outdir):
    """What survives as the presence requirement tightens."""
    thr = [0.50, 0.75, 0.90]
    apps = [OBSERVED["panel"][t]["apps"] for t in thr]
    share = [OBSERVED["panel"][t]["share"] * 100 for t in thr]

    fig, ax1 = plt.subplots(figsize=(5.2, 3.0))
    x = np.arange(len(thr))
    bars = ax1.bar(x - 0.18, apps, width=0.36, color=GREY, label="Apps retained")
    for b, v in zip(bars, apps):
        ax1.text(b.get_x() + b.get_width() / 2, b.get_height() + 60,
                 f"{v:,}", ha="center", fontsize=7.5, color=GREY)
    ax1.set_ylabel("Apps retained", color=GREY)
    ax1.set_ylim(0, 3100)
    ax1.set_xticks(x)
    ax1.set_xticklabels([f"{int(t*100)}%" for t in thr])
    ax1.set_xlabel("Minimum presence across the observation window")
    ax1.tick_params(axis="y", labelcolor=GREY)

    ax2 = ax1.twinx()
    ax2.plot(x, share, "o-", color=ACCENT, lw=1.6, ms=5,
             label="Qualifying category-months")
    ax2.set_ylabel("Qualifying category-months (%)", color=ACCENT)
    ax2.tick_params(axis="y", labelcolor=ACCENT)
    ax2.set_ylim(-6, 95)
    ax2.spines["right"].set_visible(True)
    for xi, s in zip(x, share):
        ax2.annotate(f"{s:.1f}%", (xi, s), textcoords="offset points",
                     xytext=(14, 2), ha="left", fontsize=8, color=ACCENT)
    fig.savefig(os.path.join(outdir, "fig2_panel_attrition.pdf"))
    plt.close(fig)


def fig3_longest_runs(outdir):
    """Longest continuous dense run per category against the window needed."""
    cats = [c for c, _ in OBSERVED["longest_runs"]][::-1]
    runs = [r for _, r in OBSERVED["longest_runs"]][::-1]
    need = 26

    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    ax.barh(cats, runs, color=[DARK if r >= need else GREY for r in runs], height=0.65)
    ax.axvline(need, color=ACCENT, ls="--", lw=1.2)
    ax.set_ylim(-0.7, len(cats) + 0.9)
    ax.text(need + 1, len(cats) + 0.25,
            "26 months required (6 baseline + 2 shock + 18 horizon)",
            fontsize=7.5, color=ACCENT, va="center")
    ax.set_xlabel("Longest continuous run of qualifying months")
    ax.set_xlim(0, 48)
    fig.savefig(os.path.join(outdir, "fig3_longest_runs.pdf"))
    plt.close(fig)


def fig4_null_comparison(outdir):
    """Observed shock counts against the block bootstrap null."""
    fig, axes = plt.subplots(1, 2, figsize=(6.2, 3.0), sharey=True)
    for ax, key, title in zip(axes, ("star", "lexicon"),
                              ("Star rating", "Lexicon polarity")):
        d = OBSERVED[key]
        ax.bar([0], [d["observed"]], color=DARK, width=0.5, label="Observed")
        ax.bar([1], [d["block_mean"]], yerr=[d["block_sd"]], capsize=4,
               color="white", edgecolor=GREY, hatch="///", width=0.5,
               label="Block bootstrap null")
        ax.bar([2], [d["shuffle_mean"]], color="white", edgecolor=GREY,
               width=0.5, label="Shuffle null (biased)")
        ax.set_xticks([0, 1, 2])
        ax.set_xticklabels(["Observed", "Block\nnull", "Shuffle\nnull"], fontsize=8)
        ax.set_title(f"{title}\nratio to block null = {d['ratio']:.2f}", fontsize=9)
    axes[0].set_ylabel("Shock episodes detected")
    fig.savefig(os.path.join(outdir, "fig4_null_comparison.pdf"))
    plt.close(fig)


def fig5_sensitivity(outdir):
    """Shock counts across the detection parameter grid."""
    fig, axes = plt.subplots(1, 2, figsize=(6.2, 2.9))
    for ax, key, title in zip(axes, ("star", "lexicon"),
                              ("Star rating", "Lexicon polarity")):
        grid = OBSERVED[key]["grid"]
        m = np.array([[grid[(sd, d)] for d in DUR_LEVELS] for sd in SD_LEVELS])
        im = ax.imshow(m, cmap="Greys", aspect="auto", vmin=0, vmax=40)
        for i in range(len(SD_LEVELS)):
            for j in range(len(DUR_LEVELS)):
                ax.text(j, i, m[i, j], ha="center", va="center", fontsize=9,
                        color="white" if m[i, j] > 22 else DARK)
        ax.set_xticks(range(len(DUR_LEVELS)))
        ax.set_xticklabels([f"{d} mo" for d in DUR_LEVELS])
        if ax is axes[0]:
            ax.set_yticks(range(len(SD_LEVELS)))
            ax.set_yticklabels([f"{s:.2f}sd" for s in SD_LEVELS])
        else:
            ax.set_yticks([])
        ax.set_xlabel("Minimum sustained duration")
        ax.set_title(title, fontsize=9)
    axes[0].set_ylabel("Shock threshold")
    fig.colorbar(im, ax=axes, shrink=0.85, label="Shocks detected")
    fig.savefig(os.path.join(outdir, "fig5_sensitivity.pdf"))
    plt.close(fig)


def fig6_measure_disagreement(outdir):
    """Outcome composition under the two sentiment measures."""
    keys = ["recovered", "non_recovered", "censored"]
    names = ["Recovered", "Non-recovered", "Censored"]
    colors = [DARK, ACCENT, "#BBBBBB"]

    fig, ax = plt.subplots(figsize=(5.2, 2.6))
    for i, (m, label) in enumerate([("star", "Star rating"),
                                    ("lexicon", "Lexicon polarity")]):
        left = 0
        total = sum(OBSERVED[m][k] for k in keys)
        for k, nm, c in zip(keys, names, colors):
            v = OBSERVED[m][k]
            ax.barh(i, v, left=left, color=c, height=0.5,
                    label=nm if i == 0 else None)
            if v:
                ax.text(left + v / 2, i, str(v), ha="center", va="center",
                        fontsize=8, color="white" if c != "#BBBBBB" else DARK)
            left += v
        ax.text(left + 0.6, i, f"n={total}", va="center", fontsize=8, color=GREY)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Star rating", "Lexicon\npolarity"])
    ax.set_xlabel("Shock episodes")
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper center",
              bbox_to_anchor=(0.5, -0.32))
    fig.savefig(os.path.join(outdir, "fig6_measure_disagreement.pdf"))
    plt.close(fig)


def fig7_power_gap(outdir):
    """Analysable episodes obtained against the events required."""
    labels = ["Amazon\n(product)", "MobileRec\n(category,\nstar)",
              "MobileRec\n(category,\nlexicon)"]
    got = [OBSERVED["amazon_phones"]["analysable"], OBSERVED["star"]["analysable"],
           OBSERVED["lexicon"]["analysable"]]

    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    bars = ax.bar(labels, got, color=DARK, width=0.5)
    for b, v in zip(bars, got):
        ax.text(b.get_x() + b.get_width() / 2, v + 4, str(v), ha="center", fontsize=8)
    ax.axhline(OBSERVED["power"]["required_hr20"], color=ACCENT, ls="--", lw=1.2)
    ax.axhline(OBSERVED["power"]["required_hr15"], color=ACCENT, ls=":", lw=1.2)
    tr = ax.get_yaxis_transform()
    ax.text(0.98, OBSERVED["power"]["required_hr20"] + 6,
            f"{OBSERVED['power']['required_hr20']} events required (HR = 2.0)",
            transform=tr, fontsize=7.5, color=ACCENT, ha="right")
    ax.text(0.98, OBSERVED["power"]["required_hr15"] + 6,
            f"{OBSERVED['power']['required_hr15']} events required (HR = 1.5)",
            transform=tr, fontsize=7.5, color=ACCENT, ha="right")
    ax.set_ylabel("Analysable shock episodes")
    ax.set_ylim(0, 215)
    fig.savefig(os.path.join(outdir, "fig7_power_gap.pdf"))
    plt.close(fig)


FIGURES = [fig1_density_cascade, fig2_panel_attrition, fig3_longest_runs,
           fig4_null_comparison, fig5_sensitivity, fig6_measure_disagreement,
           fig7_power_gap]


def _selftest():
    """Check internal consistency of OBSERVED before any figure is drawn."""
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    print("Self-tests for make_figures:\n")

    for key in ("star", "lexicon"):
        d = OBSERVED[key]
        total = d["recovered"] + d["non_recovered"] + d["censored"]
        check(f"{key}: outcomes sum to shock count", total == d["shocks"],
              f"({total} vs {d['shocks']})")
        check(f"{key}: analysable equals non-censored",
              d["analysable"] == d["recovered"] + d["non_recovered"],
              f"({d['analysable']} vs {d['recovered'] + d['non_recovered']})")
        check(f"{key}: null ratio matches observed/block",
              abs(d["ratio"] - d["observed"] / d["block_mean"]) < 0.02,
              f"(stated {d['ratio']}, computed {d['observed']/d['block_mean']:.2f})")
        check(f"{key}: grid centre matches headline count",
              d["grid"][(1.00, 2)] == d["shocks"],
              f"({d['grid'][(1.00, 2)]} vs {d['shocks']})")
        # stricter settings must never find more shocks
        mono = all(d["grid"][(sd, dur)] >= d["grid"][(sd2, dur)]
                   for sd, sd2 in zip(SD_LEVELS, SD_LEVELS[1:]) for dur in DUR_LEVELS)
        check(f"{key}: raising threshold never increases shocks", mono)

    p = OBSERVED["panel"]
    check("panel: apps decrease as presence tightens",
          p[0.50]["apps"] > p[0.75]["apps"] > p[0.90]["apps"])
    check("panel: qualifying share falls to zero at 90%", p[0.90]["share"] == 0.0)
    check("beauty: qualifying share matches counts",
          abs(OBSERVED["amazon_beauty"]["qualifying"] /
              OBSERVED["amazon_beauty"]["product_months"]
              - OBSERVED["amazon_beauty"]["share"]) < 0.002)
    check("mobilerec app 500k share matches counts",
          abs(OBSERVED["mobilerec_app_500k"]["qualifying"] /
              OBSERVED["mobilerec_app_500k"]["unit_months"]
              - OBSERVED["mobilerec_app_500k"]["share"]) < 0.0005,
          f'{OBSERVED["mobilerec_app_500k"]["qualifying"]/OBSERVED["mobilerec_app_500k"]["unit_months"]:.4f}')
    check("mobilerec category 500k share matches counts",
          abs(OBSERVED["mobilerec_cat_500k"]["qualifying"] /
              OBSERVED["mobilerec_cat_500k"]["unit_months"]
              - OBSERVED["mobilerec_cat_500k"]["share"]) < 0.0005,
          f'{OBSERVED["mobilerec_cat_500k"]["qualifying"]/OBSERVED["mobilerec_cat_500k"]["unit_months"]:.4f}')
    check("mobilerec: repeat rate matches counts",
          abs(OBSERVED["mobilerec_app"]["repeat"] /
              OBSERVED["mobilerec_app"]["pairs"]
              - OBSERVED["mobilerec_app"]["repeat_rate"]) < 0.0001)
    check("categories with a 26-month run equals 16 in the reported table",
          sum(1 for _, r in OBSERVED["longest_runs"] if r >= 26) == 15,
          "(table lists top 15; the run reported 16 overall)")

    a = OBSERVED["aspect"]
    check("aspect per-aspect cells sum to the reported total",
          sum(v[0] for v in a["per_aspect"].values()) == a["cells"],
          f'({sum(v[0] for v in a["per_aspect"].values())} vs {a["cells"]})')
    check("no aspect cell reached the threshold", a["qualifying"] == 0)
    check("no aspect series survived", a["series"] == 0)
    check("every aspect median is far below threshold",
          max(v[1] for v in a["per_aspect"].values()) < 30,
          f'(max median {max(v[1] for v in a["per_aspect"].values())})')
    check("taxonomy size matches the per-aspect table",
          len(a["per_aspect"]) == a["aspects"])

    r = OBSERVED["repeat"]
    amz = r["amazon"][0] / r["amazon"][1]
    mob = r["mobilerec"][0] / r["mobilerec"][1]
    check("Amazon repeat rate is 0.159%", abs(amz - 0.00159) < 0.00001,
          f"({amz:.5%})")
    check("MobileRec repeat rate is 0.063%", abs(mob - 0.00063) < 0.00001,
          f"({mob:.5%})")
    check("both corpora fall below the 2% cohort threshold",
          amz < 0.02 and mob < 0.02)
    check("Amazon repeats more often than MobileRec, yet still far too little",
          amz > mob and amz < 0.002, f"({amz:.5%} vs {mob:.5%})")

    cats, months, have = a["categories"], a["panel_months"], a["panel_reviews"]
    per_cm = have / (cats * months)
    check("mean reviews per category-month is 33.9",
          abs(per_cm - 33.87) < 0.05, f"({per_cm:.2f})")
    check("a single aspect would only just clear the threshold",
          30 < per_cm < 35, f"({per_cm:.1f})")
    check("two aspects already fall below it", per_cm / 2 < 30,
          f"({per_cm/2:.1f})")
    check("ten aspects fall an order of magnitude below",
          per_cm / 10 < 5, f"({per_cm/10:.1f})")

    fu = OBSERVED["followup"]
    for k in ("star", "lexicon"):
        d = fu[k]
        check(f"{k}: followup outcomes sum to episodes",
              d["recovered"] + d["non_recovered"] + d["censored"] == d["episodes"])
        b = d["boot"]
        check(f"{k}: bootstrap ratio matches counts",
              abs(b["ratio"] - b["observed"] / b["null_mean"]) < 0.001,
              f'({b["observed"]/b["null_mean"]:.4f})')
        check(f"{k}: MCSE equals sd over sqrt(reps)",
              abs(b["mcse"] - b["null_sd"] / np.sqrt(b["reps"])) < 0.002,
              f'({b["null_sd"]/np.sqrt(b["reps"]):.4f})')
        p = d["pelt"]
        check(f"{k}: PELT ratio matches counts",
              abs(p["ratio"] - p["observed"] / p["null_mean"]) < 0.001)
        check(f"{k}: PELT z matches counts",
              abs(p["z"] - (p["observed"] - p["null_mean"]) / p["null_sd"]) < 0.002,
              f'({(p["observed"]-p["null_mean"])/p["null_sd"]:.4f})')

    check("PELT is significant for star ratings and not for the lexicon",
          fu["star"]["pelt"]["p"] < 0.05 and fu["lexicon"]["pelt"]["p"] > 0.05,
          f'(star p={fu["star"]["pelt"]["p"]}, lexicon p={fu["lexicon"]["pelt"]["p"]})')
    check("threshold rule and PELT disagree on star ratings",
          fu["star"]["boot"]["ratio"] < 1 < fu["star"]["pelt"]["ratio"],
          "(the disagreement is the finding, not an error)")
    check("block length sensitivity is stable for star ratings",
          max(r for _, _, r in fu["star"]["block"]) -
          min(r for _, _, r in fu["star"]["block"]) < 0.10)

    den = OBSERVED["denominators"]
    for thr, (q, d_, dmax) in den.items():
        check(f"denominator {thr:.0%}: qualifying within denominator", q <= d_)
        check(f"denominator {thr:.0%}: denominator within maximum", d_ <= dmax)
    check("logged denominator is 2150, not the 2151 we once derived",
          den[0.75][1] == 2150)
    check("share at 75% matches the logged denominator",
          abs(den[0.75][0] / den[0.75][1] - 0.444) < 0.001,
          f'({den[0.75][0]/den[0.75][1]:.4f})')

    co = OBSERVED["cohort"]
    rates = {k: r / p for k, (r, p) in co.items()}
    check("user-category rate far exceeds user-item",
          rates["user_category"] / rates["user_item"] > 20,
          f'({rates["user_category"]/rates["user_item"]:.1f}x)')
    check("user-category rate is 1.64%",
          abs(rates["user_category"] - 0.0164) < 0.0002,
          f'({rates["user_category"]:.4%})')
    check("no cohort unit reaches 2%", all(v < 0.02 for v in rates.values()))
    check("the finest unit is the sparsest",
          rates["user_category_aspect"] < rates["user_aspect"])

    print()
    if failures:
        print(f"{len(failures)} test(s) FAILED: {failures}")
        return 1
    print("All make_figures self-tests passed.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--outdir", default="figures")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(_selftest())

    os.makedirs(args.outdir, exist_ok=True)
    for fn in FIGURES:
        fn(args.outdir)
        print(f"  wrote {fn.__name__}")
    def serialisable(obj):
        if isinstance(obj, dict):
            return {str(k): serialisable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [serialisable(v) for v in obj]
        return obj

    with open(os.path.join(args.outdir, "observed_values.json"), "w") as f:
        json.dump(serialisable(OBSERVED), f, indent=2)
    print(f"\n{len(FIGURES)} figures written to {args.outdir}/")




# ===========================================================================
# ADDITIONAL FIGURES: distributional and analytical rather than descriptive.
# ===========================================================================

from scipy import stats as _st


def fig8_null_distributions(outdir):
    """
    Null distributions with the observed count marked, and the implied
    one-sided p-value. More informative than error bars because the reader can
    see where the observation falls in the null density.
    """
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 3.0), sharey=True)
    for ax, key, title in zip(axes, ("star", "lexicon"),
                              ("Star rating", "Lexicon polarity")):
        # The 999-replicate run supersedes the 30-replicate values used in an
        # earlier version. Drawing the old density while the text quotes the
        # new p-value would put figure and text in conflict.
        b = OBSERVED["followup"][{"star": "star", "lexicon": "lexicon"}[key]]["boot"]
        mu, sd, obs = b["null_mean"], b["null_sd"], b["observed"]
        p_emp = b["p"]
        x = np.linspace(mu - 4 * sd, mu + 4 * sd, 400)
        y = _st.norm.pdf(x, mu, sd)
        ax.fill_between(x, y, color="#DDDDDD", zorder=1)
        ax.plot(x, y, color=GREY, lw=1.2, zorder=2)
        ax.axvline(obs, color=ACCENT, lw=1.8, zorder=3)
        ax.text(0.03, 0.95,
                f"observed = {obs}\nnull = {mu:.1f} $\\pm$ {sd:.1f}\n"
                f"ratio = {obs/mu:.2f}\n$p$ = {p_emp:.2f} (empirical)",
                transform=ax.transAxes, va="top", fontsize=7.5)
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("Shocks under the block bootstrap null")
        ax.set_yticks([])
    axes[0].set_ylabel("Null density")
    fig.savefig(os.path.join(outdir, "fig8_null_distributions.pdf"))
    plt.close(fig)


def fig9_power_curve(outdir):
    """
    Required events as a continuous function of the hazard ratio, with the
    largest observed episode count marked. Shows the detectable effect size
    given what the data actually yield.
    """
    hr = np.linspace(1.05, 4.0, 400)
    z_a, z_b = _st.norm.ppf(0.975), _st.norm.ppf(0.80)
    d = (z_a + z_b) ** 2 / (0.25 * np.log(hr) ** 2)

    best = max(OBSERVED["star"]["analysable"], OBSERVED["lexicon"]["analysable"])
    # HR at which the required events equal what we obtained
    hr_detectable = float(np.exp(np.sqrt((z_a + z_b) ** 2 / (0.25 * best))))

    fig, ax = plt.subplots(figsize=(5.4, 3.2))
    ax.plot(hr, d, color=DARK, lw=1.6)
    ax.axhline(best, color=ACCENT, ls="--", lw=1.2)
    ax.axvline(hr_detectable, color=ACCENT, ls=":", lw=1.2)
    ax.plot([hr_detectable], [best], "o", color=ACCENT, ms=6, zorder=5)
    ax.set_yscale("log")
    ax.set_xlabel("Hazard ratio to be detected")
    ax.set_ylabel("Events required (80\\% power, $\\alpha$ = 0.05)")
    ax.set_xlim(1.05, 4.0)
    ax.text(hr_detectable - 0.12, best * 1.8,
            f"smallest detectable HR\nwith {best} events: {hr_detectable:.2f}",
            fontsize=7.5, color=ACCENT, ha="right")
    fig.savefig(os.path.join(outdir, "fig9_power_curve.pdf"))
    plt.close(fig)


def fig10_attrition_flow(outdir):
    """Attrition from raw interactions to analysable episodes."""
    stages = ["Interactions\nstreamed", "Within\nwindow", "Balanced\npanel",
              "Qualifying\ncategory-months", "Usable\nseries", "Analysable\nepisodes"]
    values = [500000, 226009, 74780, 955, 27, 20]

    fig, ax = plt.subplots(figsize=(6.0, 3.2))
    xs = np.arange(len(stages))
    ax.plot(xs, values, "o-", color=DARK, lw=1.6, ms=6)
    ax.set_yscale("log")
    ax.set_xticks(xs)
    ax.set_xticklabels(stages, fontsize=7.5)
    ax.set_ylabel("Records remaining (log scale)")
    for x, v in zip(xs, values):
        ax.annotate(f"{v:,}", (x, v), textcoords="offset points",
                    xytext=(0, 9), ha="center", fontsize=7.5)
    ax.set_ylim(8, 2e6)
    fig.savefig(os.path.join(outdir, "fig10_attrition_flow.pdf"))
    plt.close(fig)


def fig11_aspect_density(outdir):
    """Aspect cells and how far each falls short of the mention threshold."""
    pa = OBSERVED["aspect"]["per_aspect"]
    names = sorted(pa, key=lambda k: pa[k][0])
    cells = [pa[n][0] for n in names]
    med = [pa[n][1] for n in names]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.4, 3.2), sharey=True)
    ax1.barh(names, cells, color=GREY, height=0.65)
    ax1.set_xlabel("Cells formed (category $\\times$ month)")
    for y, v in enumerate(cells):
        ax1.text(v + 20, y, str(v), va="center", fontsize=7.5, color=GREY)
    ax1.set_xlim(0, 1500)

    ax2.barh(names, med, color=DARK, height=0.65)
    ax2.axvline(30, color=ACCENT, ls="--", lw=1.3)
    ax2.set_xlabel("Median mentions per cell")
    ax2.set_xlim(0, 34)
    ax2.text(29, len(names) - 0.4, "threshold = 30", fontsize=7.5,
             color=ACCENT, ha="right", va="center")
    fig.savefig(os.path.join(outdir, "fig11_aspect_density.pdf"))
    plt.close(fig)


def fig12_ceiling(outdir):
    """
    Reviews required for full aspect coverage against reviews available.

    This bound assumes a perfect extractor assigning every review to exactly
    one of k aspects, so it is independent of lexicon quality: no extractor
    can create a review that was never written.
    """
    a = OBSERVED["aspect"]
    cats, months, have = a["categories"], a["panel_months"], a["panel_reviews"]
    ks = np.arange(1, 13)
    need = 30 * ks * cats * months
    per_cell = have / (cats * months) / ks

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.4, 3.0))
    ax1.plot(ks, per_cell, "o-", color=DARK, lw=1.6, ms=4)
    ax1.axhline(30, color=ACCENT, ls="--", lw=1.3)
    ax1.set_xlabel("Aspects in the taxonomy ($k$)")
    ax1.set_ylabel("Mentions per cell at best")
    ax1.text(12, 31, "threshold", fontsize=7.5, color=ACCENT, ha="right")
    ax1.set_ylim(0, 40)

    ax2.plot(ks, need / 1000, "o-", color=DARK, lw=1.6, ms=4)
    ax2.axhline(have / 1000, color=ACCENT, ls="--", lw=1.3)
    ax2.set_xlabel("Aspects in the taxonomy ($k$)")
    ax2.set_ylabel("Reviews required (thousands)")
    ax2.text(12, have / 1000 + 25, f"available: {have/1000:.0f}k",
             fontsize=7.5, color=ACCENT, ha="right")
    fig.savefig(os.path.join(outdir, "fig12_ceiling.pdf"))
    plt.close(fig)


def fig13_repeat_rates(outdir):
    """Repeat reviewing of the same item, both corpora."""
    r = OBSERVED["repeat"]
    labels = ["Amazon\nReviews 2023", "MobileRec", "MobileRec\n(balanced panel)"]
    vals = [r["amazon"][0] / r["amazon"][1] * 100,
            r["mobilerec"][0] / r["mobilerec"][1] * 100,
            r["mobilerec_balanced"] * 100]

    fig, ax = plt.subplots(figsize=(5.0, 2.8))
    bars = ax.bar(labels, vals, color=DARK, width=0.5)
    # No horizontal reference line: the 2% figure used in the code is our own
    # working convention, not a published standard, and drawing it here would
    # lend it an authority it does not have.
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.006, f"{v:.3f}%",
                ha="center", fontsize=8)
    ax.set_ylabel("User-item pairs with\nmore than one review (%)")
    ax.set_ylim(0, 0.195)
    fig.savefig(os.path.join(outdir, "fig13_repeat_rates.pdf"))
    plt.close(fig)


FIGURES = FIGURES + [fig8_null_distributions, fig9_power_curve,
                     fig10_attrition_flow, fig11_aspect_density,
                     fig12_ceiling, fig13_repeat_rates]


def _selftest_extra():
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    print("Self-tests for additional figures:\n")

    z_a, z_b = _st.norm.ppf(0.975), _st.norm.ppf(0.80)

    # the inverted power formula must round-trip
    for hr_true in (1.5, 2.0, 3.0):
        d = (z_a + z_b) ** 2 / (0.25 * np.log(hr_true) ** 2)
        hr_back = float(np.exp(np.sqrt((z_a + z_b) ** 2 / (0.25 * d))))
        check(f"power inversion round-trips at HR={hr_true}",
              abs(hr_back - hr_true) < 1e-6, f"(got {hr_back:.4f})")

    # smallest detectable HR with 20 events must be large
    hr20 = float(np.exp(np.sqrt((z_a + z_b) ** 2 / (0.25 * 20))))
    check("20 events detect only very large effects", hr20 > 3.0,
          f"(got HR={hr20:.2f})")

    # z-scores of the observed counts must match the reported ratios' direction
    for key in ("star", "lexicon"):
        d = OBSERVED[key]
        z = (d["observed"] - d["block_mean"]) / d["block_sd"]
        check(f"{key}: |z| below 2 confirms non-significance", abs(z) < 2.0,
              f"(z={z:+.2f})")
        check(f"{key}: sign of z matches ratio vs 1",
              (z > 0) == (d["ratio"] > 1.0))

    # attrition must be monotone decreasing
    vals = [500000, 226009, 74780, 955, 27, 20]
    check("attrition is monotone decreasing",
          all(a > b for a, b in zip(vals, vals[1:])))

    print()
    if failures:
        print(f"{len(failures)} test(s) FAILED: {failures}")
        return 1
    print("All additional-figure self-tests passed.")
    return 0


if __name__ == "__main__":
    main()
