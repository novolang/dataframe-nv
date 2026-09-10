# dataframe-nv

**Status: NOT IMPLEMENTED — interface only.**

Every public function below is published with its signature and its
effect row, and every body is `todo()`.  Installing this package works;
calling it panics with `not implemented`.

## What this is

A data frame for novo-lang: named, typed columns over one shared length,
each carrying a null mask.  Selection by name and by mask, `head`,
`tail` and `slice`, `with_column` and `drop`, a stable sort by several
keys, group-by with count, sum, mean, min and max, an inner and a left
join on one key, and `describe`.

It is the middle of the novobook tier.  ndarray-nv is underneath — a
numeric column converts to an array and back, and `filter` takes an
array mask — and stats-nv is beside it, taking the same arrays.

The subset is the one measured off notebook corpora rather than the
whole of polars: what a cell actually calls, load, look, filter, group,
join, summarise.  What is deliberately absent is in "What is not here".

```
novo pkg add dataframe-nv
novo pkg build
novo test --isolate
```

Every call panics with `not implemented` until the implementation lands,
so `novo test --isolate` is what a first-time reader runs: each `@test`
gets its own process and prints the function it stopped at.

## The one example that will work

```novo
use dftable
use dfcolumn
use dfgroup
use ndfloat

fn main() [io]
    // Sales per city, and the mean sale in each — the four calls a
    // notebook cell actually makes.
    match dftable.of_columns([dfcolumn.strings("city", ["oslo", "bergen", "oslo"]),
                              dfcolumn.floats("sale", [10.0, 20.0, 30.0])])
        Ok(sales) =>
            match dfgroup.by(sales, ["city"])
                Ok(g) =>
                    match dfgroup.aggregate(g, sales, [DfAggSpec { column: "sale", how: DfMean, into: "mean_sale" }])
                        Ok(out) => println("${dftable.names(out)} over ${dftable.rows(out)} row(s)")
                        Err(e)  => println(e.message())
                Err(e) => println(e.message())
        Err(e) => println(e.message())
```

## The layer, and why

`core`.  A frame is a list of columns and a column is a list of values.
Nothing here opens a file, connects to anything or reads a clock.
LOADING a frame is the host's job and it stays there: the host reads the
bytes, csv-nv parses them into records, and `dfcsv.of_records` turns
those into columns — only the first of those three performs anything.
The whole surface is `[]`, and there are no `host_modules`.

**No `@tier(embedded)` claim**, and none is intended.  A frame's whole
purpose is to hold more data than fits in a person's head; a device with
64 KB of RAM is not where that happens, and the `describe` this package
exists to make cheap allocates a second frame to say it.  The audit's
`core-embedded` row passes and says the claim was not made.

## The load-bearing interface

**A column is `DfCells` plus a `present` mask, and NOT an `NdFloat`.**

Three things a column has that an array does not: a NAME, a null MASK,
and an element type that may be Bool or Str.  If a column were an array
then a text column could not exist and a null could only be a NaN —
which collapses "missing" and "not a number", and telling those apart is
most of what a data frame is for.  So a column holds its values in a
four-way enum of flat lists, and CONVERTS to an array when the caller
wants array arithmetic, with the nulls decided explicitly at that
boundary.

That conversion is the whole of the ndarray-nv dependency, and it is
load-bearing rather than structural.  The path a notebook takes:

```
dfcolumn.to_floats   a numeric column becomes an NdFloat  (refuses a null)
ndfloat.gt           the comparison, over unboxed doubles, in ndarray-nv
dftable.filter       the resulting NdMask selects the frame's rows
dfcolumn.of_floats   a computed array becomes a named column again
```

`filter` takes a mask rather than a row predicate for the same reason
every columnar frame does: a predicate over a row would be handed one
tagged allocation per column per row and would run once per row in the
caller's code, where a mask is computed column-wise over flat buffers.
Sorting is by key list rather than by comparator for the same reason.

**And the null rule, written once.**  It lives in `dfcolumn`'s module
comment and every doc comment that could restate it points there
instead.  In short: nulls are SKIPPED in an aggregation and the count of
what remains is the divisor; a null join key MATCHES NOTHING, not even
another null; a null predicate DROPS its row; nulls sort LAST in both
directions; and a numeric conversion REFUSES a null unless the caller
names a fill.

Two of those are places this package deliberately differs from its
references, and both are stated where they bite:

| | polars | pandas | here |
| --- | --- | --- | --- |
| a null join key | matches other nulls | drops the row | matches nothing (SQL's rule) |
| a null group key | its own group | dropped | its own group, so the group sizes sum to the row count |
| nulls in a sort | last | last | last, in both directions |
| a null into numeric | becomes null downstream | becomes NaN | refused, unless a fill is named |

## What one dependency each buys

- **ndarray-nv** (path, sibling; `^0.0.1` at publish) — the numeric
  bridge above.  Without it this package would grow its own flat
  numeric arithmetic and its own mask type, and stats-nv would then
  have two array types to take.
- **csv-nv** (`^0.1.1`, published) — `dfcsv`, five functions.  It is
  NOT the only way in: `dftable.of_rows` takes `[Str]` and `[[Str]]`
  and serves a database cursor, a JSON array of arrays or a fixed-width
  reader.  What the dependency buys is that the CSV path is TYPED — a
  caller holding csv-nv's own `Header` and `Row` does not unpack them
  first — and that a record of the wrong width is reported with its
  LINE NUMBER, which csv-nv carries and a bare `[Str]` has thrown away.
  That line number is the whole argument for the dependency, and it is
  the trade the milestone review should weigh: one more package in
  every consumer's closure, for the CSV path being typed rather than
  merely possible.

## What is not here

Named so a reader stops looking: no row index (a row is a POSITION —
see `dftable`'s module comment for why pandas's index is the thing not
being copied), no lazy query plan, no expression DSL, no window
functions, no pivot or melt, no date or decimal column (calendar-nv and
chrono-nv are their own rows on the grid), no categorical type (an Int
column and a dictionary beside it), no right or outer join (a right
join is a left join with the arguments swapped), no multi-column join
key (make the key a column), and no printing — a library returns text
or a frame, and `describe` returning a FRAME is what lets a caller print
it however they like.

## The reference implementation

**polars** (MIT) for the shape — columnar, no row index, group-by
producing a frame, first-appearance group order — and **pandas**
(BSD-3-Clause) for the operations a notebook reader expects to find by
name: `head`, `describe`, `groupby(...).agg(...)`, a left join.  Where
the two disagree, the table above says which was taken and why.

polars's own test suite is the oracle the implementation lane will run
the ported subset against, with pandas's `describe` output as the
comparison for the summary numbers — mean, sample standard deviation
and linear-interpolated quantiles, which are what a reader checking
against a Python notebook will compare.

## Status

Every function is `todo()`.  `novo test --isolate` is the readable form
of that verdict.

| module | public functions | implemented |
| --- | --- | --- |
| `dffault` | the `DfFault` enum and its `Error` impl | no |
| `dfcell` | 6 | no |
| `dfcolumn` | 29 | no |
| `dftable` | 23 | no |
| `dfgroup` | 8 | no |
| `dfjoin` | 4 | no |
| `dfsummary` | 4 | no |
| `dfcsv` | 5 | no |
