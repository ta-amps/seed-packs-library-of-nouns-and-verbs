# CSV checks

Checks a CSV analysis at every step, so a reviewer can rerun it without the drafter's tools: the
file's digest and schema profile, every cell against the declared schema, missing values and
outliers by Tukey's fences, recorded queries with result digests, chart specs kept as Vega-Lite data,
and findings whose every number traces to a query result. Python 3.10 or later, standard library only.

```bash
make check                                    # compile, then every test
python -m csv_checks profile --csv DATA.csv --request REQUEST.json
python -m csv_checks validate --csv DATA.csv --request REQUEST.json
python -m csv_checks flag --csv DATA.csv --request REQUEST.json
python -m csv_checks query --csv DATA.csv --request REQUEST.json --queries QUERIES.json
python -m csv_checks charts --charts CHARTS.json --results RESULTS.json
python -m csv_checks trace --findings FINDINGS.json --results RESULTS.json
```

Nothing is changed, imputed or deleted: a query leaves a row out only through a filter written in it,
and its result counts the rows left out. Values from a column the request marks identifying never
appear in a report. The tests cover type inference, every validation rule, the fences against
hand-computed quartiles, the query language, the chart and trace checks, and recompute the pack's
worked example from [source.json](../source.json). Nothing here draws a chart, calls a model, opens a
network connection or writes a file. MIT license, written for this pack by ta-amps.
