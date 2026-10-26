# Charts and measurements through MCP

`fastmean_ac` and `fastmean_transient` already return a PNG as MCP
`ImageContent`, together with native samples and CSV artifacts. Use
`fastmean_plot` to make an annotated chart from a saved calculation: choose
signals, display and measurement windows, units, captions and reference lines.
This creates another persistent run without starting FASTMEAN or requiring a
separate plotting script. FASTMEAN supplies the numbers; Matplotlib in the MCP
server renders the chart.

## Five signals from a native transient

Run `fastmean_transient` with the path to the amplifier SCM. Replace the path
placeholder with the actual returned or inspected schematic path:

```json
{
  "path": "<path-to-Amplifier_4BJT.scm>",
  "signals": ["U(IN)", "U(OUT)", "I(RL)", "I(VIN)", "U(OUT)*I(RL)"],
  "stop": 0.3,
  "step": 0.00001,
  "eps": 0.00001,
  "timeout": 60
}
```

Keep that response's `run_id`. Then call `fastmean_plot` with these arguments,
replacing the run placeholder:

```json
{
  "run_id": "<run_id-returned-by-fastmean_transient>",
  "title": "Four-BJT amplifier",
  "subtitle": "Native FASTMEAN transient · nominal PWL model",
  "display_window": [0.297, 0.3],
  "measurement_window": [0.29, 0.3],
  "x_unit": "ms",
  "panels": [
    {"signal": "U(IN)", "label": "Input", "unit": "V", "metrics": ["rms"]},
    {"signal": "U(OUT)", "label": "Output", "unit": "V", "metrics": ["rms"]},
    {"signal": "I(RL)", "label": "Load current", "unit": "A", "metrics": ["rms"]},
    {"signal": "I(VIN)", "label": "Input current", "unit": "mA", "scale": 1000, "metrics": ["rms", "peak"]},
    {"signal": "U(OUT)*I(RL)", "label": "Load power", "unit": "W", "metrics": ["mean"], "guides": ["mean"]}
  ]
}
```

The chart shows 297–300 ms; its measurements cover 290–300 ms. The power column
was evaluated by native FASTMEAN during the transient. `fastmean_plot` selects
that exported column by its exact name. To add a formula that was not exported,
request it in a new native AC/transient calculation. Current and power signs
follow the native expression and component orientation.

For the included nominal amplifier, this workflow reproduced approximately
25.002515 V RMS, 20.002012 A RMS and 500.100725 W average load power. See the
[example and its model scope](../examples/four-bjt-amplifier/README.md).

## Arguments and defaults

| Argument | Meaning |
| --- | --- |
| `run_id` | An original, registered native AC/transient run. Find one with `fastmean_list_runs`; inspect its `columns` using `fastmean_get_result`. |
| `panels` | A list of 1–12 panel objects. Omitted: all exported signals, provided there are at most 12. Duplicate panel signals are rejected. |
| `display_window` | `[start, stop]` in original seconds or Hz. Omitted: the complete exported range. |
| `measurement_window` | Independent `[start, stop]` in original seconds or Hz. Omitted: the complete exported range, even when the display window is shorter. |
| `title`, `subtitle` | Optional plain text, up to 160 and 240 characters. Control characters are rejected. |
| `x_unit` | Transient: `s`, `ms`, `us`; AC: `Hz`, `kHz`, `MHz`. Omitted: `s` or `Hz`. This changes displayed values and labels. |

Window bounds must be finite, increasing and completely bracketed by the
exported data. For example, `x_unit: "ms"` still requires window bounds in
seconds: `[0.297, 0.3]`, rather than `[297, 300]`.

| Panel field | Meaning |
| --- | --- |
| `signal` | Required exact exported column name, including case and expression spelling. |
| `label` | Optional plain text, up to 80 characters. The native formula remains in the panel heading. |
| `unit` | Optional plain display label, up to 24 characters. The server does not infer a formula's physical dimensions. |
| `scale` | Finite positive display multiplier; default `1`. `display_value = native_value * scale`. |
| `metrics` | Unique list of `rms`, `mean`, `peak`, `min`, `max`, `peak_to_peak`. Default: `["rms"]` for transient data, `[]` for AC. Use `[]` to omit measurements. |
| `guides` | Unique list of `mean` and/or `rms` horizontal reference lines. Each requested guide also adds that metric. Default: `[]`. |
| `color` | Optional `#RRGGBB` color. Otherwise the server chooses from its palette. |

Raw exported values and measurements are preserved. For a native current in
amperes, `unit: "mA", scale: 1000` changes the plotted current and metric
captions to milliamperes. It does not multiply the raw `metrics` values.

## Measurement definition

The server retains the native adaptive timestamps inside each window. It adds
the exact start and stop bounds, linearly interpolating their signal values
when a bound falls between samples. It performs no extrapolation.

For the resulting points `(t_i, y_i)`, with duration `T = stop - start`:

```text
mean = sum((y_i + y_(i+1)) / 2 * (t_(i+1) - t_i)) / T
rms  = sqrt(sum((y_i² + y_(i+1)²) / 2 * (t_(i+1) - t_i)) / T)
```

Thus RMS uses time-weighted trapezoidal quadrature of squared samples. It is a
sample-based approximation to the continuous integral, not the arithmetic mean
of squared sample values. The implementation scales the RMS calculation
internally to avoid overflowing the square of a large finite value.

`peak` is `max(abs(y))`; `min`, `max` and `peak_to_peak` use the same windowed
samples and interpolated endpoints. These extrema do not estimate peaks between
sample points. Mean native instantaneous power gives the average power over the
selected time interval. All time-weighted metrics and guides require transient
data; they are rejected for AC data.

Measurements use the complete window before graphical reduction. Each plotted
panel is limited to 6,000 vertices, retaining each display bucket's minimum and
maximum. This rendering step does not alter the measurements or source CSV.

## Images, resources and recovery

A successful `fastmean_plot` response contains:

- An actual MCP `ImageContent` PNG block, ready for the AI/client to inspect.
- Structured JSON and a text JSON block describing the new plot run.
- MCP `ResourceLink` entries for `plot.png`, `plot.svg`, `chart-spec.json`,
  `measurements.json`, `manifest.json` and the full result record.

Use each artifact's returned `uri` with MCP `resources/read`; artifact URIs have
the form `fastmean://artifacts/{plot_run_id}/{name}`. The SVG is a scalable
version of the chart. The PNG is kept below the inline image budget of
3,900,000 bytes; an oversized result produces an error instead of silently
omitting its image.

Measurements are available directly at
`result.measurements.signals[i].metrics`, keyed by metric name. These values
are in the native exported column's units. The corresponding
`display_metrics` apply that panel's scale. For example, an input current might
have raw `metrics.rms` of about `0.0668034` A and `display_metrics.rms` of about
`66.8034` with a `mA` label. `sample_count` includes inserted window endpoints;
`interpolated_boundaries` records how many of the two endpoints needed
interpolation. Captions show six significant digits; JSON retains the numeric
values used for those captions.

`chart-spec.json` saves normalized arguments. To repeat the chart, pass its
`source_run_id` as `run_id`, together with its `panels`, `display_window`,
`measurement_window`, `title`, `subtitle` and `x_unit`. The other spec fields
are descriptive metadata, rather than additional tool arguments. Use the
original calculation's ID again when changing the presentation; a plot run's ID
is not accepted as a numeric source.

After a server restart, call `fastmean_get_result` with the **plot** `run_id` to
recover its image, measurements and resources. Source data remain accessible
through the original calculation's run and `fastmean_read_data`. Replotting
requires the registered source files but does not require a running native
application.

## AC example

After `fastmean_ac` has exported `db(U(out)/U(in))` and `phs(U(out)/U(in))`, call
`fastmean_plot` with:

```json
{
  "run_id": "<run_id-returned-by-fastmean_ac>",
  "title": "Native frequency response",
  "display_window": [10, 100000],
  "x_unit": "kHz",
  "panels": [
    {"signal": "db(U(out)/U(in))", "label": "Gain", "unit": "dB", "metrics": []},
    {"signal": "phs(U(out)/U(in))", "label": "Phase", "unit": "deg", "metrics": []}
  ]
}
```

The source AC run must cover the selected 10–100,000 Hz range and contain those
exact columns. The chart retains the native request's logarithmic or linear
frequency axis. Changing `x_unit` does not resample the calculation.

## Provenance and access boundaries

Each chart manifest records its source run/resource URI, source schematic
SHA256, native-data and CSV SHA256, native engine identity/hash, original
analysis request, normalized chart request, renderer version and output image
hashes. The complete source CSV is SHA256-verified against the registered native
manifest while it is read. Existing source files are preserved.

Numeric sources are limited to completed, registered native AC/transient runs.
The tool accepts no arbitrary CSV filename, URL, Python code or newly evaluated
formula. Published-file checks reject traversal, symlinks/junctions and changed
artifacts. Tables must have finite values, a valid strictly increasing axis,
at most 31 columns, and at most 10,000 AC or 1,000,001 transient rows. Internal
verified CSV processing permits up to 256 MiB; individual public resource reads
remain limited to 8 MiB, with large source tables available through paged
`fastmean_read_data`. Generated SVGs also fit the 8 MiB resource limit.

The chart identifies FASTMEAN as the numeric solver and Matplotlib as the
renderer. Native application screenshots require a separate explicit action.
