# Existing parameters and large schematic inspection

Use `fastmean_edit_parameters` to change a shared setting such as the amplifier's
load, both feedback resistors or both supply rails. It changes an existing root
`.parameter`/`.param` numeric declaration in a fresh portable project. Component
expressions remain bound to the parameter; labels, comments, explanatory TEXT,
saved TD/FD formulas, wires and child models are preserved.

First inspect the source SCM:

```json
{"path":"<path-to-Amplifier_4BJT.scm>"}
```

The result contains `root_parameters`, including each exact name, SI value,
original literal, quoted label, TEXT object ID, direct known bindings and
editability reasons. `scope: "root"` means this lists the selected file's
declarations. It does not flatten instance parameters or evaluate expressions.

Then pass the same path to `fastmean_edit_parameters`:

```json
{
  "path":"<path-to-Amplifier_4BJT.scm>",
  "updates":{"Rload":2,"Rf":"3k","Vrail":40},
  "expected_source_sha256":"<source_sha256-returned-by-inspect>"
}
```

The optional digest prevents applying an edit after the source was resaved.
Returned `parameter_changes` records old/new SI values. The returned `path` and
model artifacts belong to a new job; move the complete folder. Run a new native
analysis for these values. Existing prose retains its original wording and can
describe the example's nominal regime. This tool performs no calculation.

`fastmean_edit_values` instead replaces a chosen component's value with a
literal. For example, editing `RFB_P` alone breaks its shared `Rf` binding;
editing parameter `Rf` keeps both feedback resistors linked.

In 1.6.0, `fastmean_annotate_circuit` can also create typed scalar bindings:

```json
{
  "path":"<path-to-source.scm>",
  "parameters":{"Ratio":2,"Fswitch":"50k"},
  "bindings":{"TR1":{"n":"Ratio"},"VIN":{"PULSE.F":"Fswitch"}},
  "descriptions":["Ratio: transformer primary/secondary turns ratio."]
}
```

Use actual instance names and declared native fields from `fastmean_catalog`.
Only scalar electrical fields bind this way; model/file interfaces, structural
fields changing pin count, and logic parameter expressions are excluded.
The same root parameter can drive several fields. This is not generation of
native per-instance `X` parameter overrides.

For a direct property or table edit, use `fastmean_edit_properties`, for example
`updates={"TR1":{"n":2},"SW1":{"Ron":0.01}}`. It preserves omitted native
fields and creates a portable copy. It also accepts saved TD/FD/AOD/SOD/DCOP
settings and definitions `{name,expression,arguments?}`. Changing N/HasRS when
it would change physical terminals requires regenerating the connected circuit.

## Supported declarations

Native manual pages27–30 document parameter/definition directives, semicolon
assignment separators, `%` comments and quoted descriptions. The updater masks
comments and quoted strings, then changes only finite numeric literal spans:

```text
.parameter
Rload=1.25 "Load [ohm]"; % this description/comment is preserved
Rf=3k "Feedback [ohm]";
```

Names are case-sensitive ASCII identifiers. Unknown names, expressions as
targets, duplicate declarations and conflicting `.define`/`.def`, `.global`
or `.set` names are rejected. Root `.set` overrides of direct affected component
fields and conflicting child `.global` declarations are rejected too. Known
direct passive/source frequency/rise-time bindings retain positive values;
delay and duty bindings retain their supported ranges. This is not evaluation
of arbitrary derived expressions or verification of an entire physical model.

Inspection reports root-only conflicts. Editing additionally checks recursive
model dependencies; it creates no parameter definitions or instance overrides.

## Complete pages instead of recursive truncation

Default `fastmean_inspect` returns compact components, ports, analysis settings,
root parameters and TEXT notes in independently budgeted collections. Raw native
component `Params` are available through a selected section. `include_objects`
adds a raw-object page. Every collection has `pages` metadata with its total,
returned count, continuation and section name. The reply stays below128KiB of
UTF-8 JSON and never cuts an individual native entry halfway through.

Select `section` to read full `components`, `nodes`, `objects`, `texts`, `ports`,
`parameters`, `analysis`, `wires`, `warnings` or `parameter_issues`:

```json
{
  "path":"<schematic-path>",
  "section":"objects",
  "offset":0,
  "limit":50,
  "expected_source_sha256":"<source_sha256-returned-by-inspect>"
}
```

The complete values are in `data`, with pagination in `page`. Lists stay lists
and mappings stay mappings; `page.kind` describes the selection. Continue at
`next_offset` while `has_more` is true. Reuse the source digest on every page;
an intervening save produces a clear error instead of mixing snapshots.

For an oversized individual object/property, use `detail_path` to select a
nested field. Paths are exact mapping keys and integer list indices in that
section, not file paths. For example, read saved graph expressions:

```json
{
  "path":"<schematic-path>",
  "section":"analysis",
  "detail_path":["TD","Expressions"],
  "offset":0,
  "limit":30
}
```

A large source waveform can be paged with `section:"objects"` and a path such
as `[5,"Params","USER","U","x"]`; index5 means the sixth native object.
Use the returned snapshot digest when following this index. A TEXT selection
such as `[0,"Params","Text"]` in `section:"texts"` returns character chunks,
preserving Unicode and line endings. Limits are1–1000 entries/characters.

If a summary's first item exceeds its collection allowance, its page includes
`needs_detail_path` and no continuation offset. Select that section/property to
make progress. A direct page request for an oversized item reports its location
explicitly. Reads create no jobs and start no native process or application UI.
