"""Helpers for the AR6 C1 residual-emissions analysis.

Kept deliberately small: variable definitions, data loading and the
consistency check. The notebook holds the narrative and the figures.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pyam

E = "Emissions|CO2"
S = "Carbon Sequestration"

# --- AR6 variables -----------------------------------------------------------

TOTALS = {
    "total_net": E,
    "eip_net": f"{E}|Energy and Industrial Processes",
    "energy_net": f"{E}|Energy",
    "demand_net": f"{E}|Energy|Demand",
}

# Net sectoral emissions as reported (net of any CCS within the sector).
SECTOR_NET = {
    "supply": f"{E}|Energy|Supply",
    "industry_energy": f"{E}|Energy|Demand|Industry",
    "industry_process": f"{E}|Industrial Processes",
    "transport": f"{E}|Energy|Demand|Transportation",
    "buildings": f"{E}|Energy|Demand|Residential and Commercial",
    "afolu": f"{E}|AFOLU",
    # small remainders, needed for the sum check only
    "afofi": f"{E}|Energy|Demand|AFOFI",
    "demand_other": f"{E}|Energy|Demand|Other Sector",
    "other": f"{E}|Other",
}

# Carbon captured or removed (reported as positive numbers).
CDR = {
    "beccs": f"{S}|CCS|Biomass",
    "beccs_supply": f"{S}|CCS|Biomass|Energy|Supply",
    "beccs_industry": f"{S}|CCS|Biomass|Energy|Demand|Industry",
    "beccs_process": f"{S}|CCS|Biomass|Industrial Processes",
    "daccs": f"{S}|Direct Air Capture",
    "land_use": f"{S}|Land Use",
    "enhanced_weathering": f"{S}|Enhanced Weathering",
    "ccs_fossil": f"{S}|CCS|Fossil",
    "ccs_process": f"{S}|CCS|Industrial Processes",
}

ALL_VARIABLES = sorted(set(TOTALS.values()) | set(SECTOR_NET.values()) | set(CDR.values()))

# Parent = sum of components. Each rule lists *required* components (without them
# the sum is meaningless, so the scenario is reported as "incomplete" rather than
# "inconsistent") and *optional* ones (added when reported, e.g. small remainders).
AGGREGATION_RULES = {
    TOTALS["total_net"]: {
        "required": [TOTALS["eip_net"], SECTOR_NET["afolu"]],
        "optional": [SECTOR_NET["other"]],
    },
    TOTALS["eip_net"]: {
        "required": [SECTOR_NET["supply"], TOTALS["demand_net"]],
        "optional": [SECTOR_NET["industry_process"]],
    },
    TOTALS["demand_net"]: {
        "required": [SECTOR_NET[k] for k in ("industry_energy", "transport", "buildings")],
        "optional": [SECTOR_NET[k] for k in ("afofi", "demand_other")],
    },
    CDR["beccs"]: {
        "required": [CDR["beccs_supply"]],
        "optional": [CDR["beccs_industry"], CDR["beccs_process"]],
    },
}


# --- model families ----------------------------------------------------------

def model_family(model: str) -> str:
    """Strip the version from an AR6 model name.

    'REMIND-MAgPIE 2.1-4.2' -> 'REMIND-MAgPIE', 'MESSAGEix-GLOBIOM_1.1' ->
    'MESSAGEix-GLOBIOM'. A version starts at the first space or underscore
    that is followed by a digit (optionally preceded by 'v').
    """
    return re.split(r"[ _]v?\d", model, maxsplit=1)[0].strip()


# --- loading -----------------------------------------------------------------

def load_ar6(csv: Path, meta_xlsx: Path, years=(2050,), variables=ALL_VARIABLES) -> pyam.IamDataFrame:
    """Read the AR6 World snapshot for selected variables and years.

    The full file (~360 MB, ~690 000 timeseries) is pre-filtered with pandas
    before it is handed to pyam; converting all of it to pyam's long format
    would be slow and is not needed here.
    """
    cols = ["Model", "Scenario", "Region", "Variable", "Unit"] + [str(y) for y in years]
    raw = pd.read_csv(csv, usecols=cols)
    raw = raw[raw["Variable"].isin(variables)]
    df = pyam.IamDataFrame(raw)
    df.load_meta(meta_xlsx, sheet_name="meta")
    return df


# --- gross sectoral emissions and CDR ----------------------------------------

SECTORS = ["Energy supply", "Industry", "Transport", "Buildings", "AFOLU (net)"]
CDR_COMPONENTS = ["BECCS", "DACCS", "Land-based removal", "Enhanced weathering"]


def sector_table(df: pyam.IamDataFrame, year: int = 2050) -> pd.DataFrame:
    """One row per scenario: gross sectoral CO2 emissions and CDR (Mt CO2/yr).

    Gross = net sectoral emissions + BECCS captured in that sector, because AR6
    sectoral variables are reported net of BECCS. Rules:

    * Energy supply = Energy|Supply + CCS|Biomass|Energy|Supply. If the supply
      split is not reported but total CCS|Biomass is, and no industrial BECCS is
      reported, all BECCS is attributed to supply (flag ``beccs_supply_assumed``).
      If net supply is negative and no BECCS is reported at all, the gross value
      cannot be derived and is set to missing.
    * Industry = Energy|Demand|Industry + Industrial Processes (0 if not reported)
      + BECCS in industry (energy and process, 0 if not reported).
    * Transport, Buildings: as reported (no CCS in these sectors).
    * AFOLU: net flux as reported; most models do not separate gross land-use
      emissions from land-based removals, so it is not converted to gross.
    * BECCS = max(CCS|Biomass, sum of its sectoral components), because some
      models (IMAGE) omit industrial BECCS from the parent variable.
    """
    w = df.filter(year=year).timeseries()[year].unstack("variable")
    w = w.droplevel(["region", "unit"]) if "region" in w.index.names else w
    g = lambda key, src=SECTOR_NET: w.get(src[key], pd.Series(np.nan, index=w.index))
    c = lambda key: g(key, CDR)

    out = pd.DataFrame(index=w.index)
    beccs_ind = c("beccs_industry").fillna(0) + c("beccs_process").fillna(0)
    assumed = c("beccs_supply").isna() & c("beccs").notna() & (beccs_ind == 0)
    beccs_supply = c("beccs_supply").where(~assumed, c("beccs"))
    out["Energy supply"] = g("supply") + beccs_supply.fillna(0)
    # negative net supply without any reported BECCS: gross value cannot be derived
    out.loc[g("supply").lt(0) & c("beccs").isna(), "Energy supply"] = np.nan
    out["Industry"] = g("industry_energy") + g("industry_process").fillna(0) + beccs_ind
    out["Transport"] = g("transport")
    out["Buildings"] = g("buildings")
    out["AFOLU (net)"] = g("afolu")

    sector_sum = c("beccs_supply").fillna(0) + beccs_ind
    out["BECCS"] = np.fmax(c("beccs"), sector_sum.where(sector_sum > 0))
    out["DACCS"] = c("daccs")
    out["Land-based removal"] = c("land_use")
    out["Enhanced weathering"] = c("enhanced_weathering")
    out["Fossil and process CCS"] = c("ccs_fossil").fillna(0) + c("ccs_process").fillna(0)

    # only where all four energy and industry sectors are reported
    out["Gross residual (4 sectors)"] = out[["Energy supply", "Industry", "Transport", "Buildings"]].sum(
        axis=1, min_count=4
    )
    out["Emissions|CO2 (net, reported)"] = w.get(TOTALS["total_net"])
    out["beccs_supply_assumed"] = assumed
    out["industry_process_reported"] = g("industry_process").notna()
    out = out.reset_index()
    out.insert(1, "family", out["model"].map(model_family))
    return out


SUMMARY_COLUMNS = ["Energy supply", "Industry", "Transport", "Buildings",
                   "Gross residual (4 sectors)", "AFOLU (net)"] + CDR_COMPONENTS


def summary_stats(tab: pd.DataFrame, families) -> pd.DataFrame:
    """n, quartiles (Gt CO2/yr) per quantity, for all C1 scenarios and per family."""
    groups = {"All C1": tab, **{f: tab[tab["family"] == f] for f in families}}
    out = {}
    for name, d in groups.items():
        q = d[SUMMARY_COLUMNS].quantile([0.25, 0.5, 0.75]).T / 1000
        out[name] = pd.DataFrame({"n": d[SUMMARY_COLUMNS].count(),
                                  "p25": q[0.25], "median": q[0.5], "p75": q[0.75]})
    return pd.concat(out, names=["group", "quantity"]).round(2)


# --- consistency check -------------------------------------------------------

def check_aggregates(df: pyam.IamDataFrame, rules=AGGREGATION_RULES, rtol=0.01, atol=10.0):
    """Check parent = sum of components for every rule and scenario.

    Returns ``(summary, failures)``:

    * ``summary``: per rule, how many scenarios report the parent, how many lack a
      required component ("incomplete"), how many were checked and how many failed.
    * ``failures``: one row per failing (scenario, rule), with the reported parent,
      the sum of reported components and the difference, in Mt CO2/yr.

    A scenario fails if ``|parent - sum| > atol + rtol * |sum|`` (numpy.isclose).
    """
    summary, failures = [], []
    for parent, comp in rules.items():
        # all variables of the scenarios that report the parent
        has_parent = df.filter(index=df.filter(variable=parent).index)
        # scenarios that report the parent but miss a required component
        missing = has_parent.require_data(variable=comp["required"])
        incomplete = set() if missing is None else set(zip(missing.model, missing.scenario))
        complete = has_parent.filter(
            index=[i for i in has_parent.index if i not in incomplete]
        ) if incomplete else has_parent
        res = complete.check_aggregate(
            parent, components=comp["required"] + comp["optional"], rtol=rtol, atol=atol
        )
        n_fail = 0
        if res is not None and not res.empty:
            res = res.rename(
                columns={"variable": "parent_value", "components": "sum_of_components"}
            ).reset_index().rename(columns={"variable": "parent"})
            res["difference"] = res["parent_value"] - res["sum_of_components"]
            failures.append(res[["model", "scenario", "parent", "parent_value",
                                 "sum_of_components", "difference"]])
            n_fail = len(res)
        summary.append({
            "parent": parent,
            "reported": len(has_parent.index),
            "incomplete": len(incomplete),
            "checked": len(complete.index),
            "failed": n_fail,
        })
    failures = pd.concat(failures, ignore_index=True) if failures else pd.DataFrame()
    return pd.DataFrame(summary).set_index("parent"), failures
