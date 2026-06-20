#!/usr/bin/env python3
"""Convert each downloaded OWID raw CSV to the layered ground-truth schema
used by figure-recovery-suite, and write per-chart metadata.json.

For each chart:
  - read ground_truth_raw.csv (OWID's filtered-data download)
  - write ground_truth.csv with columns layer_idx, layer_type, series, x, y
  - write metadata.json with chart_id, type stressed, x/y axis title/unit,
    source, OWID slug

Three CSV patterns are handled:
  A) Long format, single value column: (Entity, Code, Year, <value>)
       -> one series per Entity, x = Year, y = value, Line Graph
  B) Wide format, single entity, many value columns:
       (Entity=World, Code, Year, val_a, val_b, ...)
       -> one series per value column, x = Year, y = value, Line Graph
       (used here for stacked-area charts; each layer's value is the raw
       per-source contribution, NOT cumulative top)
  C) Scatter format, single year, two value columns:
       (Entity, Code, Year, val_x, val_y, [..])
       -> one Scatter Plot series, one row per Entity at (val_x, val_y)
"""
import csv
import json
import os

CHARTS_DIR = os.path.dirname(os.path.abspath(__file__)) + "/charts"

CHART_INFO = {
    "life-expectancy": {
        "type": "multi-series line, time series",
        "x_axis": {"title": "Year", "unit": None},
        "y_axis": {"title": "Life expectancy", "unit": "years"},
        "value_column": "Life expectancy",
        "stress": "multi-series line plot with curated entity set; legend labels at line endpoints",
    },
    "annual-co2-emissions-per-country": {
        "type": "multi-series line, time series, large dynamic range",
        "x_axis": {"title": "Year", "unit": None},
        "y_axis": {"title": "Annual CO2 emissions", "unit": "t"},
        "value_column": "Annual CO₂ emissions",
        "stress": "y-axis tick labels carry SI unit suffix (billion t); legend at line endpoints",
    },
    "global-primary-energy": {
        "type": "stacked area, single entity, many sources",
        "x_axis": {"title": "Year", "unit": None},
        "y_axis": {"title": "Energy consumption", "unit": "TWh"},
        "value_columns": ["Modern biofuels", "Other renewables", "Solar",
                            "Wind", "Hydropower", "Nuclear", "Gas", "Oil",
                            "Coal", "Traditional biomass"],
        "wide": True,
        "stress": "stacked area chart, 10 series, color-by-source",
    },
    "life-expectancy-vs-gdp-per-capita": {
        "type": "scatter, log x, marker size by population",
        "x_axis": {"title": "GDP per capita", "unit": "$",
                    "scale": "log10"},
        "y_axis": {"title": "Life expectancy at birth", "unit": "years"},
        "x_value_column": "GDP per capita",
        "y_value_column": "Life expectancy at birth",
        "scatter": True,
        "stress": "log-x scatter; marker SIZE encodes population (third variable); marker color encodes continent (fourth)",
    },
    "share-of-individuals-using-the-internet": {
        "type": "multi-series line, percent y, time series",
        "x_axis": {"title": "Year", "unit": None},
        "y_axis": {"title": "Share of population using the internet",
                    "unit": "%"},
        "value_column": "Share of the population using the Internet",
        "stress": "percent y-axis ticks (0%, 20%, ...); 8 regional series",
    },
    "child-mortality": {
        "type": "multi-series line, percent y, time series, noisy early data",
        "x_axis": {"title": "Year", "unit": None},
        "y_axis": {"title": "Child mortality rate", "unit": "%"},
        "value_column": "Under-five mortality rate (selected)",
        "stress": "percent y-axis ticks; high-noise early data with many spikes",
    },
    "population": {
        "type": "multi-series line, time series, large dynamic range",
        "x_axis": {"title": "Year (with BCE)", "unit": None},
        "y_axis": {"title": "Population", "unit": "people"},
        "value_column": "Population",
        "stress": "x-axis with BCE/CE labels; y-axis SI suffix (billion); very large dynamic range",
    },
    "share-electricity-low-carbon": {
        "type": "multi-series line, percent y, BROKEN y-axis",
        "x_axis": {"title": "Year", "unit": None},
        "y_axis": {"title": "Share of electricity from low-carbon",
                    "unit": "%"},
        "value_column": "Share of electricity from low-carbon sources",
        "stress": "BROKEN y-axis (gap between 50% and 80%); 9 country series",
    },
    "co2-emissions-per-capita": {
        "type": "multi-series line, time series",
        "x_axis": {"title": "Year", "unit": None},
        "y_axis": {"title": "Annual CO2 emissions per capita",
                    "unit": "t"},
        "value_column": "CO₂ emissions per capita",
        "stress": "9 country series; one (China) crosses many others",
    },
    "gdp-per-capita-worldbank": {
        "type": "multi-series line, time series, dollar unit",
        "x_axis": {"title": "Year", "unit": None},
        "y_axis": {"title": "GDP per capita", "unit": "$"},
        "value_column": "GDP per capita",
        "stress": "10 country series; y-axis tick labels have $ prefix and ,000 separator",
    },
}


def convert_long(chart_dir, info):
    """Pattern A: (Entity, Code, Year, value) -> one series per Entity."""
    raw = os.path.join(chart_dir, "ground_truth_raw.csv")
    out = os.path.join(chart_dir, "ground_truth.csv")
    value_col = info["value_column"]
    n_rows = 0
    series_seen = set()
    with open(raw) as f, open(out, "w", newline="") as g:
        w = csv.writer(g)
        w.writerow(["layer_idx", "layer_type", "series", "x", "y"])
        for r in csv.DictReader(f):
            try:
                year = float(r["Year"])
                val = r.get(value_col)
                if val in (None, ""): continue
                y = float(val)
            except (TypeError, ValueError):
                continue
            entity = r["Entity"]
            w.writerow([0, "Line Graph", entity, year, y])
            n_rows += 1
            series_seen.add(entity)
    return n_rows, sorted(series_seen)


def convert_wide(chart_dir, info):
    """Pattern B: (Entity, Code, Year, val1, val2, ...) one Entity, many cols."""
    raw = os.path.join(chart_dir, "ground_truth_raw.csv")
    out = os.path.join(chart_dir, "ground_truth.csv")
    cols = info["value_columns"]
    n_rows = 0
    with open(raw) as f, open(out, "w", newline="") as g:
        w = csv.writer(g)
        w.writerow(["layer_idx", "layer_type", "series", "x", "y"])
        for r in csv.DictReader(f):
            try:
                year = float(r["Year"])
            except (TypeError, ValueError):
                continue
            for col in cols:
                v = r.get(col)
                if v in (None, ""): continue
                try:
                    y = float(v)
                except ValueError:
                    continue
                w.writerow([0, "Line Graph", col, year, y])
                n_rows += 1
    return n_rows, cols


def convert_scatter(chart_dir, info):
    """Pattern C: (Entity, Year, val_x, val_y) one row per Entity, one Scatter."""
    raw = os.path.join(chart_dir, "ground_truth_raw.csv")
    out = os.path.join(chart_dir, "ground_truth.csv")
    xc = info["x_value_column"]
    yc = info["y_value_column"]
    n_rows = 0
    with open(raw) as f, open(out, "w", newline="") as g:
        w = csv.writer(g)
        w.writerow(["layer_idx", "layer_type", "series", "x", "y"])
        for r in csv.DictReader(f):
            x = r.get(xc); y = r.get(yc)
            if x in (None, "") or y in (None, ""): continue
            try:
                xv = float(x); yv = float(y)
            except ValueError:
                continue
            w.writerow([0, "Scatter Plot", "Country", xv, yv])
            n_rows += 1
    return n_rows, ["Country"]


def write_metadata(chart_dir, slug, info, n_rows, series_seen):
    md = {
        "chart_id": slug,
        "source": "Our World in Data",
        "source_url": f"https://ourworldindata.org/grapher/{slug}",
        "csv_url": f"https://ourworldindata.org/grapher/{slug}.csv?csvType=filtered&tab=chart",
        "image_url": f"https://ourworldindata.org/grapher/{slug}.png?tab=chart",
        "chart_type": info["type"],
        "feature_stressed": info["stress"],
        "x_axis_title": info["x_axis"]["title"],
        "x_axis_unit": info["x_axis"].get("unit"),
        "y_axis_title": info["y_axis"]["title"],
        "y_axis_unit": info["y_axis"].get("unit"),
        "x_scale": info["x_axis"].get("scale", "linear"),
        "y_scale": info["y_axis"].get("scale", "linear"),
        "n_gt_rows": n_rows,
        "series": series_seen,
    }
    with open(os.path.join(chart_dir, "metadata.json"), "w") as f:
        json.dump(md, f, indent=2)


def main():
    for slug, info in CHART_INFO.items():
        cd = os.path.join(CHARTS_DIR, slug)
        if not os.path.isdir(cd):
            print(f"  SKIP {slug}: dir missing"); continue
        if info.get("wide"):
            n, series = convert_wide(cd, info)
        elif info.get("scatter"):
            n, series = convert_scatter(cd, info)
        else:
            n, series = convert_long(cd, info)
        write_metadata(cd, slug, info, n, series)
        print(f"  {slug}: {n} GT rows, {len(series)} series")


if __name__ == "__main__":
    main()
