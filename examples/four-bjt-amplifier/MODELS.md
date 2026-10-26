# Compact transistor equivalents

The four native SCM definitions use the same nominal piecewise-linear terminal
characteristics as the earlier alpha form, expressed with beta-controlled
collector/emitter branches. This permits short diode-to-sensor connections and
two straight internal buses. Each generated model has five genuine junctions
and one retained routing waypoint in the published files. Every retained CON remains visible.

For a forward/reverse diode current `IF`/`IR` and transfer coefficients
`alphaF`/`alphaR`, define:

```
jF = (1 - alphaF) * IF
jR = (1 - alphaR) * IR
betaF = alphaF / (1 - alphaF)
betaR = alphaR / (1 - alphaR)
```

Scaling both diode resistances by `1 / (1 - alpha)` while keeping its threshold
voltage produces the corresponding `j` current. For the NPN convention,
collector current entering C and emitter current leaving E become:

```
IC = betaF*jF - (betaR+1)*jR = alphaF*IF - IR
IE = (betaF+1)*jF - betaR*jR = IF - alphaR*IR
IB = jF + jR
```

The PNP diodes reverse direction. The native F gains and terminal ordering in
the JSON account for FASTMEAN's current-reference convention. The external
base, collector and emitter series resistances remain unchanged.

The complete amplifier was rebuilt and calculated through real MCP stdio.
Over 0.29–0.30 s, the beta form produced **500.100725490108 W**, compared with
**500.100725498907 W** for the previous alpha form. This numerical agreement
checks the equivalent conversion at the demonstrated operating point; it
does not add thermal, SOA or high-frequency behavior to the nominal model.

`verify_connectivity.py` independently flattens the logical project JSON and
compares it with the included native exported netlist: 60 leaf components,
136 terminals and 43 matching net partitions, without splits or merges.
The original alpha authoring specification remains a routing regression
fixture under `tests/fixtures/`.

Preview captions and drawings are MCP engineering illustrations. Their wire
paths use native pin geometry; they are not screenshots of FASTMEAN's fonts.
The manufacturer data links and the model's physical limitations are described
in the [example README](README.md).
