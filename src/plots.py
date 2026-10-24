"""Figures for the AR6 C1 residual-emissions analysis (values in Gt CO2/yr)."""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

POSITIVE_SECTORS = ["Energy supply", "Industry", "Transport", "Buildings"]
SECTOR_COLOURS = {
    "Energy supply": "#E69F00",
    "Industry": "#0072B2",
    "Transport": "#009E73",
    "Buildings": "#CC79A7",
    "AFOLU (net)": "#8C6D31",
}
CDR_COLOURS = {"BECCS": "#56B4E9", "DACCS": "#6A3D9A", "Enhanced weathering": "#9E9E9E"}
FAMILY_COLOURS = {"MESSAGEix-GLOBIOM": "#1B9E77", "REMIND-MAgPIE": "#D95F02", "IMAGE": "#7570B3"}

UNALLOCATED = dict(facecolor="white", edgecolor="0.45", hatch="//////", lw=0.4)

RNG = np.random.default_rng(42)  # fixed seed: jitter is reproducible


def set_style():
    mpl.rcParams.update({
        "hatch.linewidth": 0.4,
        "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
        "xtick.labelsize": 6, "ytick.labelsize": 6, "legend.fontsize": 7,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.titlelocation": "left", "figure.dpi": 150, "savefig.dpi": 300,
        "savefig.bbox": "tight",
    })


def _jitter(n, width=0.12):
    return RNG.uniform(-width, width, n)


def _median_tick(ax, x, y, half=0.22, colour="black"):
    ax.plot([x - half, x + half], [y, y], color=colour, lw=1.6, zorder=4, solid_capstyle="butt")


def fig_sector_distribution(tab: pd.DataFrame, sectors=POSITIVE_SECTORS + ["AFOLU (net)"]):
    """Fig. 1: gross residual CO2 by sector in 2050, all C1 scenarios."""
    fig, ax = plt.subplots(figsize=(6.3, 3.0))
    for i, s in enumerate(sectors):
        y = tab[s].dropna() / 1000
        ax.boxplot(y, positions=[i], widths=0.5, showfliers=False, whis=(5, 95),
                   medianprops=dict(color="black", lw=1.6), boxprops=dict(color="0.4"),
                   whiskerprops=dict(color="0.4"), capprops=dict(color="0.4"))
        ax.scatter(i + _jitter(len(y)), y, s=9, color=SECTOR_COLOURS[s], alpha=0.75,
                   edgecolor="none", zorder=3)
        ax.annotate(f"n = {len(y)}\nmedian {y.median():.1f}".replace("-", "\u2212"), (i, 1.0), xycoords=("data", "axes fraction"),
                    ha="center", va="bottom", fontsize=6)
    ax.axhline(0, color="0.6", lw=0.6, zorder=0)
    ax.axvline(len(sectors) - 1.5, color="0.8", lw=0.6, ls="--", zorder=0)
    ax.set_xticks(range(len(sectors)), sectors)
    ax.set_ylabel("CO$_2$ emissions in 2050 (Gt CO$_2$/yr)")
    ax.set_title("Transport and industry carry most residual CO$_2$ in 1.5 °C (C1) pathways", pad=24)
    ax.margins(x=0.04)
    return fig


def fig_family_comparison(tab: pd.DataFrame, families=tuple(FAMILY_COLOURS),
                          sectors=POSITIVE_SECTORS + ["AFOLU (net)"]):
    """Fig. 2: (a) residual CO2 by sector and model family; (b) total gross residual."""
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(6.8, 3.0), width_ratios=[5, 1.6])
    off = np.linspace(-0.27, 0.27, len(families))
    sub = tab[tab.family.isin(families)]
    for i, s in enumerate(sectors):
        for o, fam in zip(off, families):
            y = sub.loc[sub.family == fam, s].dropna() / 1000
            if y.empty:
                continue
            ax.scatter(i + o + _jitter(len(y), 0.05), y, s=9, color=FAMILY_COLOURS[fam],
                       alpha=0.7, edgecolor="none", zorder=3)
            _median_tick(ax, i + o, y.median(), half=0.09, colour=FAMILY_COLOURS[fam])
    ax.axhline(0, color="0.6", lw=0.6, zorder=0)
    ax.axvline(len(sectors) - 1.5, color="0.8", lw=0.6, ls="--", zorder=0)
    ax.set_xticks(range(len(sectors)), sectors)
    ax.set_ylabel("CO$_2$ emissions in 2050 (Gt CO$_2$/yr)")
    ax.set_title("Model families differ most in industry, transport and AFOLU")
    for fam in families:
        n = sub.loc[sub.family == fam].shape[0]
        ax.scatter([], [], s=12, color=FAMILY_COLOURS[fam], label=f"{fam} (n = {n})")
    ax.legend(frameon=False, loc="upper right", handletextpad=0.2)
    ax.margins(x=0.03)

    tot = "Gross residual (4 sectors)"
    for j, fam in enumerate(families):
        y = sub.loc[sub.family == fam, tot].dropna() / 1000
        bx.scatter(j + _jitter(len(y), 0.1), y, s=9, color=FAMILY_COLOURS[fam], alpha=0.7,
                   edgecolor="none", zorder=3)
        _median_tick(bx, j, y.median(), half=0.25, colour=FAMILY_COLOURS[fam])
        bx.annotate(f"{y.median():.1f}", (j + 0.3, y.median()), fontsize=6, va="center")
    bx.set_xticks(range(len(families)), [{"MESSAGEix-GLOBIOM": "MESSAGEix", "REMIND-MAgPIE": "REMIND-\nMAgPIE"}.get(f, f) for f in families])
    bx.set_ylim(bottom=0)
    bx.set_title("Sum of four\nsectors")
    bx.margins(x=0.15)
    fig.tight_layout(w_pad=1.0)
    return fig


def fig_balance(tab: pd.DataFrame, families=tuple(FAMILY_COLOURS)):
    """Fig. 3: per-scenario balance of gross residual emissions, AFOLU and CDR."""
    sub = tab[tab.family.isin(families)].dropna(subset=POSITIVE_SECTORS).copy()
    sub["_order"] = sub[POSITIVE_SECTORS].sum(axis=1)
    ns = [int((sub.family == f).sum()) for f in families]
    fig, axes = plt.subplots(1, len(families), figsize=(6.8, 3.2), sharey=True,
                             width_ratios=ns, gridspec_kw=dict(wspace=0.06))
    for ax, fam in zip(axes, families):
        d = sub[sub.family == fam].sort_values("_order")
        x = np.arange(len(d))
        top = np.zeros(len(d))
        for s in POSITIVE_SECTORS:
            v = d[s].to_numpy() / 1000
            ax.bar(x, v, bottom=top, width=0.8, color=SECTOR_COLOURS[s], lw=0)
            top += v
        afolu = d["AFOLU (net)"].fillna(0).to_numpy() / 1000
        bottom = np.minimum(afolu, 0)
        ax.bar(x, np.where(afolu > 0, afolu, 0), bottom=top, width=0.8, color=SECTOR_COLOURS["AFOLU (net)"], lw=0)
        ax.bar(x, np.where(afolu < 0, afolu, 0), width=0.8, color=SECTOR_COLOURS["AFOLU (net)"], lw=0)
        for c in CDR_COLOURS:
            v = -d[c].fillna(0).to_numpy() / 1000
            ax.bar(x, v, bottom=bottom, width=0.8, color=CDR_COLOURS[c], lw=0)
            bottom += v
        # remainder: reported net CO2 minus the sum of all stacked components
        net = d["Emissions|CO2 (net, reported)"].to_numpy() / 1000
        rest = net - (top + afolu - d[list(CDR_COLOURS)].fillna(0).sum(axis=1).to_numpy() / 1000)
        top_all = top + np.maximum(afolu, 0)
        up_, dn_ = rest > 0.01, rest < -0.01  # draw only remainders above 10 Mt
        ax.bar(x[up_], rest[up_], bottom=top_all[up_], width=0.8, **UNALLOCATED)
        ax.bar(x[dn_], rest[dn_], bottom=bottom[dn_], width=0.8, **UNALLOCATED)
        ax.scatter(x, net, s=10, color="black", zorder=5)
        ax.axhline(0, color="black", lw=0.6)
        ax.set_xticks([])
        ax.set_xlabel(f"{fam}\n(n = {len(d)})")
        ax.margins(x=0.02)
    up = sub[POSITIVE_SECTORS].sum(axis=1) + sub["AFOLU (net)"].clip(lower=0)
    down = sub["AFOLU (net)"].clip(upper=0) - sub[list(CDR_COLOURS)].fillna(0).sum(axis=1)
    rest = sub["Emissions|CO2 (net, reported)"] - (up + down)
    hi = (up + rest.clip(lower=0)).max() / 1000
    lo = (down + rest.clip(upper=0)).min() / 1000
    pad = 0.04 * (hi - lo)
    axes[0].set_ylim(lo - pad, hi + pad)
    axes[0].set_ylabel("CO$_2$ in 2050 (Gt CO$_2$/yr)")
    axes[0].set_title("Gross residual emissions are balanced by BECCS and the land sink "
                      "in different proportions", loc="left")
    handles = [mpl.patches.Patch(color=SECTOR_COLOURS[s], label=s) for s in SECTOR_COLOURS]
    handles += [mpl.patches.Patch(color=CDR_COLOURS[c], label=c) for c in CDR_COLOURS]
    handles += [mpl.patches.Patch(label="Not allocated to a sector", **UNALLOCATED)]
    handles += [mpl.lines.Line2D([], [], marker="o", ls="", color="black", ms=3,
                                 label="Net CO$_2$ (reported)")]
    fig.legend(handles=handles, frameon=False, ncol=5, loc="lower center",
               bbox_to_anchor=(0.5, -0.12), handlelength=1.0, columnspacing=1.0)
    return fig
