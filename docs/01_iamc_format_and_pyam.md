# The IAMC data format and the pyam operations used here

## 1. The IAMC format

Integrated assessment model (IAM) results are exchanged in the format of the
Integrated Assessment Modeling Consortium (IAMC). Each row is one timeseries:

| model | scenario | region | variable | unit | 2020 | 2030 | ... | 2100 |
|---|---|---|---|---|---|---|---|---|
| MESSAGEix-GLOBIOM 1.0 | EN_NPi2020_400f | World | Emissions\|CO2 | Mt CO2/yr | 39 800 | 21 300 | ... | -9 200 |

- **model**: model name *including its version* (e.g. `REMIND-MAgPIE 2.1-4.2`).
  A *model family* is the model name with the version stripped; several versions
  of one model are not independent evidence.
- **scenario**: the scenario name as submitted by the modelling team; names are
  only unique within a model.
- **region**: `World`, aggregate regions (R5, R10) or ISO countries.
- **variable**: a hierarchical name with `|` as separator, e.g.
  `Emissions|CO2|Energy|Demand|Transportation`. By convention a parent equals the
  sum of its children, but submissions are often incomplete (children missing,
  an unreported `Other` remainder), which is why aggregation checks are needed.
- **unit**: free text, e.g. `Mt CO2/yr`.
- **year columns** ("wide" format). The equivalent "long" format has one row per
  (model, scenario, region, variable, unit, year) with a single `value` column;
  pyam stores data internally in long format.

Alongside the timeseries there is a **meta table**, one row per
(model, scenario), holding scenario-level indicators. In AR6 this includes the
climate category (`Category`: C1 ... C8), vetting status, and the illustrative
mitigation pathway (`IMP_marker`). The meta table is distributed as a separate
Excel file.

## 2. AR6 CO2 variables relevant to this project

| quantity | AR6 variable |
|---|---|
| total net CO2 | `Emissions\|CO2` |
| energy and industrial processes | `Emissions\|CO2\|Energy and Industrial Processes` |
| energy supply | `Emissions\|CO2\|Energy\|Supply` |
| industry (energy use) | `Emissions\|CO2\|Energy\|Demand\|Industry` |
| industry (process) | `Emissions\|CO2\|Industrial Processes` |
| transport | `Emissions\|CO2\|Energy\|Demand\|Transportation` |
| buildings | `Emissions\|CO2\|Energy\|Demand\|Residential and Commercial` |
| AFOLU (net) | `Emissions\|CO2\|AFOLU` |
| BECCS | `Carbon Sequestration\|CCS\|Biomass` |
| fossil CCS | `Carbon Sequestration\|CCS\|Fossil` |
| industrial-process CCS | `Carbon Sequestration\|CCS\|Industrial Processes` |
| DACCS | `Carbon Sequestration\|Direct Air Capture` |
| land-based removal | `Carbon Sequestration\|Land Use` |

Two reporting conventions matter for "gross" residual emissions:

1. Sectoral `Emissions|CO2|...` variables are **net** of CCS taking place in that
   sector. BECCS removals are typically netted into energy supply, so gross
   energy-supply emissions are approximately
   `Emissions|CO2|Energy|Supply + Carbon Sequestration|CCS|Biomass`.
2. `Emissions|CO2|AFOLU` is a **net** land-use flux; most models do not report
   gross land-use emissions and land-based removals separately. AFOLU is
   therefore kept as a net value in this analysis.

The variable list above is taken from the AR6 reporting template and will be
checked against the variables actually present in the downloaded file.

## 3. pyam operations used

`pyam.IamDataFrame` wraps the long-format data (`df.data`) and the meta table
(`df.meta`) in one object with IAMC-aware methods.

| task | pyam call |
|---|---|
| read a snapshot file | `pyam.IamDataFrame("data/raw/AR6_..._World_v1.1.csv")` |
| query the IIASA database directly | `pyam.read_iiasa("ar6", variable=..., region="World")` |
| attach meta indicators | `df.load_meta("..._metadata_indicators_v1.1.xlsx")` |
| select | `df.filter(Category="C1", region="World", year=2050, variable="Emissions\|CO2\|*")` (wildcards, meta columns usable as filters) |
| add a scenario-level column | `df.set_meta(series, name="model_family")` |
| check that a parent equals the sum of its children | `df.check_aggregate("Emissions\|CO2", components=[...])` (returns the failing rows) |
| find scenarios lacking a variable | `df.require_data(variable=[...])` |
| derived variables | `df.add("Emissions\|CO2\|Energy\|Supply", "Carbon Sequestration\|CCS\|Biomass", "Gross ...")`, `df.subtract(...)` |
| export | `df.timeseries()` (wide `pandas.DataFrame`), `df.to_csv(...)` |

For a programmer coming from C++/Java: an `IamDataFrame` behaves like an
immutable value object. `filter`, `add`, `subtract` return new objects unless
`inplace=True` / `append=True` is passed, and almost every analysis step is a
chain of such calls followed by a `pandas` group-by on the long data.
