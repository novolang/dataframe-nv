# Changelog

All notable changes to dataframe-nv are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
package follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with the pre-1.0 rule that a breaking change bumps the MINOR number.

## 0.1.0 — 2026-09-27

The first implementation of the interface published as 0.0.1: columns
with a null mask, frames, a stable multi-key sort, group-by with five
aggregations, the inner and the left join, describe, and the bridges to
ndarray-nv and csv-nv.  It requires novo 0.13.0, ndarray-nv `^0.1.4`
and csv-nv `^0.2.1`.

### Breaking changes

- `DfFault` has an eleventh variant, `DfRaggedRecord(line, want, got)`.
  `dfcsv.of_records`, `of_records_inferred` and `infer_kinds` refuse a
  record of the wrong width with it, carrying the line the record
  started on, where the interface named `DfLengthMismatch`, which has
  no place for a line.  A `match` over `DfFault` needs the new arm.
- `dfcolumn.of_floats` and `of_ints` refuse an array that is not rank 1
  with `DfArrayFault(NdRankMismatch(1, rank))`, not `DfKindMismatch`:
  the array's kind is right and its rank is not.

### Added

- `dfcell.key`, the text two cells share exactly when they hold the
  same value.  Group-by and join match on it, and a caller grouping by
  hand can use the same rule.

### Behaviour the interface left open

- `dfcell.render` writes a float with a point: `1.0`, not `1`.  A
  Float column written to CSV and read back with its kinds inferred is
  a Float column again.
- Floats order by the total order of SPEC section 13.6, with every
  not-a-number after every number.  In a key, the two zeros of a float
  are one value, and every not-a-number is one value.
- `dfcolumn.with_nulls` keeps a null that is already there: the mask
  can add nulls and cannot remove them.
- `dfcolumn.cast` turns a float with no integer value, an infinity or a
  not-a-number, into a null when it truncates to Int, and refuses a
  cast from Int or Float to Bool with `DfKindMismatch`.
- `dfgroup.agg`, `aggregate` and `frame_of` refuse a frame whose row
  count is not the grouped frame's, with `DfLengthMismatch`.
- A join suffix that collides again is `DfDuplicateColumn`.

### Tests

- The group-by aggregations, both joins and a two-key sort are checked
  against SQLite, and the summary statistics against Python's
  `statistics` module, over three seeded frames with nulls in every
  column (`tools/differential.py`).
- A CSV document read with csv-nv, loaded with its kinds inferred and
  written back comes out byte for byte.
- Line coverage over `src/` is 100%, measured by `tests/coverage.sh`.

## 0.0.4 — 2026-09-25

The package builds with novo 0.11.  Every body is still `todo()`.

- The csv-nv requirement is now `^0.2.0`, and the lock names csv-nv
  0.2.0.  csv-nv 0.1.4 writes into lists through names that are not
  declared `var`, which novo 0.11 refuses (E2038), and 0.2.0, the first
  release with the repair, is outside `^0.1.4`.  The one change in
  csv-nv 0.2.0 that breaks a caller, `record.names` answering a copy,
  touches nothing in this package.

## 0.0.3 — 2026-09-25

The package builds with novo 0.10.0.  Every body is still `todo()`.

- The csv-nv requirement is now `^0.1.4`.  csv-nv 0.1.1 to 0.1.3 do not
  build with novo 0.10.0, and a program that depends on this package
  would fail inside csv-nv.
- One summary test read the first record with a `match` on `list.get`.
  `list.get` answers the element itself, not an option, so the test now
  checks the length and reads the element by index.  It asserts the
  same things.

## 0.0.2 — 2026-09-15

README rewritten to the package README style guide (docs/writing-a-readme.md); no change to the interface.

## 0.0.1 — 2026-09-10

The **interface**: every signature and every effect row, and no bodies.
`stability = "draft"`, and the release is recorded `implemented = false`.

### Added

- `dffault` — one error enum for the whole package, ten variants, each
  naming the column or the count it was asked about. `DfArrayFault`
  carries an `NdFault` whole rather than restating ndarray-nv's nine
  failures.
- `dfcell` — the four element types a column can hold (Float, Int, Bool,
  Str) and one value out of one, including the missing one. The
  narrowest-kind inference a loader runs lives here too.
- `dfcolumn` — a named column, its null mask, and THE NULL RULE the
  whole package points at: skipped in an aggregation, nothing in a join
  key, false in a predicate, last in a sort, refused in a numeric
  conversion unless a fill is named. Also the ndarray-nv bridge:
  `to_floats`, `to_ints`, `mask`, `present_mask`, and back.
- `dftable` — a frame: named columns over one shared length, no row
  index, rows as positions. `filter` takes an array mask rather than a
  row predicate, and `sort` takes keys rather than a comparator; both
  for the same reason, which is written down.
- `dfgroup` — group-by as POSITIONS into the caller's frame rather than
  as sub-frames, in two flat lists. Groups come out in first-appearance
  order and a null key is a group of its own, so the sizes sum to the
  row count.
- `dfjoin` — inner and left on one key, output in the left frame's
  order, a null key matching nothing.
- `dfsummary` — `describe` twice: a struct for a program, a frame for a
  person. Every number that may not exist is typed `?Float`.
- `dfcsv` — five functions over csv-nv's `Header` and `Row`.

### Known

- **A `Some` binder from `list.get` over a list of structs loses its
  struct type at a field read** — an E6000, filed under
  `bugs/codegen-llvm/`. `tests/dfsummary_tests.nv` re-binds through an
  annotation and says so at the line where it does.
- No `@tier(embedded)` claim, and none is intended: a frame holds more
  data than fits in a person's head, which is not what a
  microcontroller is for.
