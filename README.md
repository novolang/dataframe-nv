# dataframe-nv

A data frame is a table held one column at a time: each column has a
name, one element type, and the same number of rows as its neighbours.
It is the shape a spreadsheet, a database result and a statistical
notebook all have. This package brings it to novo-lang. Its references
are the Rust library [polars](https://docs.pola.rs/) for the shape and
[pandas](https://pandas.pydata.org/docs/) for the names of the
operations. Numeric columns convert to and from arrays of
[ndarray-nv](https://novo-lang.org/packages/ndarray-nv), and
[csv-nv](https://novo-lang.org/packages/csv-nv) records convert to and
from frames.

**Status: NOT IMPLEMENTED — interface only.** Every function is declared
with its full signature, but every body is a `todo()` that panics when
called. The package is published so its design can be reviewed and
depended on before it is implemented. Version 0.1.0 will be the first
working release.

## What a frame, a column and a null are

A **column** is a name, a list of values all of one type, and a
**present mask** saying which positions hold a value. A **frame** is a
list of columns of equal length. A **row** is a position, the same
position in every column.

A **null** is a position the mask says is absent. It is not a zero and
not a not-a-number: a missing measurement and a failed calculation are
different things, and telling them apart is most of what a frame is for.

There are four element types.

| Kind | Holds |
| --- | --- |
| `DfFloatKind` | a 64-bit floating-point number |
| `DfIntKind` | a 64-bit integer |
| `DfBoolKind` | a truth |
| `DfStrKind` | text |

A **cell** is one value at one position, as a `DfCell`. It is either one
of the four types or `DfNullCell`.

A **mask** is a shaped array of truths from ndarray-nv. Selecting rows
from a frame means computing a mask over a column and handing it to
`dftable.filter`.

A **group-by** splits the rows into groups that share the same value in
one or more key columns, and then computes one number per group. A
**join** matches the rows of two frames by the value in one column of
each.

## Install

```
novo pkg add dataframe-nv
```

## Example

```novo
use std.list
use dfcolumn
use dftable
use dfgroup

fn main() [io]
    // Three rows, two columns. Every column has a name, a type and the
    // same length as its neighbours.
    match dftable.of_columns([dfcolumn.strings("city", ["oslo", "bergen", "oslo"]),
                              dfcolumn.floats("sale", [10.0, 20.0, 30.0])])
        Err(e) => println(e.message())
        Ok(sales) =>
            println("${list.len(dftable.names(sales))} columns over ${dftable.rows(sales)} rows")

            // One group per distinct city, in first-appearance order.
            match dfgroup.by(sales, ["city"])
                Err(e) => println(e.message())
                Ok(g) =>
                    // The mean sale in each group, as a new frame.
                    match dfgroup.aggregate(g, sales, [DfAggSpec { column: "sale", how: DfMean, into: "mean_sale" }])
                        Err(e)  => println(e.message())
                        Ok(out) => println("${dfgroup.count(g)} groups, ${dftable.rows(out)} rows out")
```

Build and test with `novo pkg build` and `novo test`. Today `novo test`
fails on purpose: every test reaches a
`not implemented: dataframe-nv.<module>.<fn>` panic. The tests are the
specification the implementation will have to satisfy.

`novo test --isolate` gives each test its own process, so the output
names the function each one stopped at.

## What the package contains

| Module | Contents |
| --- | --- |
| `dfcell` | The four element kinds, one cell, and what can be asked of one: its kind, its text, parsing it from text, inferring a kind from a list of texts, and comparing two. |
| `dfcolumn` | The column: the four constructors, nulls, the accessors, selection by mask and by position, the conversions to and from ndarray-nv arrays, casting, and the six per-column aggregates. |
| `dftable` | The frame: construction from columns and from rows of text, the shape, column lookup, select and drop, `with_column` and rename, `head`, `tail` and `slice`, filter and take, a sort by several keys, the row and text views, concatenation, and dropping rows with nulls. |
| `dfgroup` | Group-by: the groups, their keys and sizes, the rows of one group, the five aggregations, and applying several of them at once. |
| `dfjoin` | The inner and left joins, on one column name or on two different ones, with a suffix rule for colliding names, and the matching positions on their own. |
| `dfsummary` | One column summarised, `describe` over a whole frame, a quantile, and the null counts per column. |
| `dfcsv` | Turning csv-nv records into a frame and back, with the element kinds given or inferred. |
| `dffault` | Every reason an operation refuses, as one enum with ten variants. |

## How to choose an entry point

**`dftable.of_columns` is the usual way in** when you already hold typed
values. `dftable.of_rows` takes a header and rows of text, which serves
a database cursor, a JSON array of arrays or a fixed-width reader.
`dfcsv.of_records` takes csv-nv's own header and records.

**Use `dfcsv` rather than `dftable.of_rows` for a CSV file.** It keeps
the types csv-nv already knows, and a record of the wrong width is
reported with the line number it came from. A bare list of texts has
thrown that number away.

**Arithmetic happens in ndarray-nv, not here.** The path a filter takes
is four calls.

```novo ignore
let sale = dfcolumn.to_floats(dftable.column(t, "sale")!)!   // a numeric column becomes an array
let big  = ndfloat.gt(sale, ndfloat.scalar(15.0))!           // the comparison, column-wise
let rows = dftable.filter(t, big)!                           // the mask selects the frame's rows
let col  = dfcolumn.of_floats("sale", sale)!                 // a computed array becomes a column again
```

`filter` takes a mask rather than a predicate over a row, and `sort`
takes a list of key columns rather than a comparator, because both are
then computed over flat buffers one column at a time.

**`dfsummary.describe` answers a frame, not text.** So does
`dfgroup.aggregate` and so does `dfjoin.join`. Nothing in this package
prints.

## The rules a user needs

The null rule is the one to read first. It is written once, in
`dfcolumn`'s module documentation, and it has five parts.

1. **An aggregation skips nulls, and the divisor is what remains.** The
   mean of a column with two nulls out of five is the sum of the three
   present values divided by three.
2. **A null join key matches nothing, not even another null.** This is
   SQL's rule. polars matches nulls to each other and pandas drops the
   row.
3. **A null in a group key is its own group.** So the group sizes add up
   to the frame's row count. pandas drops those rows.
4. **Nulls sort last, in both directions.**
5. **A conversion to a numeric array refuses a column with nulls.**
   `dfcolumn.to_floats` answers `DfNullInNumeric`, naming the column and
   the count. `to_floats_or` takes the fill value to use instead. A null
   is not silently a NaN.

The rest:

6. **A row is a position, not a label.** There is no row index. Two
   frames are aligned by position or joined by a key column, never by an
   index nobody set.
7. **Column names are unique within a frame.** `of_columns` refuses a
   repeat with `DfDuplicateColumn`.
8. **Every column in a frame has the same length.** A mismatch is
   `DfLengthMismatch`, carrying both numbers.
9. **Groups come back in first-appearance order.** This follows polars.
10. **`describe` gives the sample standard deviation**, divided by one
    less than the count, and quantiles by linear interpolation. Those
    are pandas's choices, so that a reader comparing against a Python
    notebook sees the same numbers.
11. **`describe` is defined at every kind.** A text column gets its row
    count, its present count, its null count, its distinct count and its
    smallest and largest values. The mean, the standard deviation and
    the quartiles are absent for it.
12. **A join between frames with a colliding column name needs a
    suffix.** `dfjoin.join_with_suffix` takes it.
13. **Every failure carries the numbers or the name.**
    `DfNoSuchColumn` names the column, `DfRowOutOfRange` carries the row
    and the row count, and `DfArrayFault` carries the ndarray-nv failure
    underneath it unchanged.

## What is not included

- **A row index.** See rule 6.
- **A lazy query plan and an expression language.** Every call here runs
  when it is made.
- **Window functions, pivot and melt.**
- **A date column and a decimal column.** Dates belong to a calendar
  package and decimals to their own.
- **A categorical type.** An integer column with a dictionary beside it
  is the same thing without a second element kind.
- **Right and outer joins.** A right join is a left join with the
  arguments the other way round.
- **A join on more than one column.** Combine the keys into one column
  first.
- **Printing.** See "How to choose an entry point".
- **A microcontroller build.** A frame exists to hold more data than fits in a
  person's head, and `describe` allocates a second frame to report on the
  first. Nothing here is claimed to build for a device with no heap allocator,
  and there is no `tests/embedded_probe.nv`.

## Related packages

- [ndarray-nv](https://novo-lang.org/packages/ndarray-nv) is where the
  arithmetic happens. A numeric column converts to one of its arrays and
  back, and its mask type is what `filter` takes.
- [csv-nv](https://novo-lang.org/packages/csv-nv) reads and writes the
  records `dfcsv` converts. It carries the line number that a refusal
  reports.
- [stats-nv](https://novo-lang.org/packages/stats-nv) takes the same
  arrays a column converts to, for summaries this package does not
  carry and for hypothesis tests.
- [plot-nv](https://novo-lang.org/packages/plot-nv) draws a column
  directly.
- [parquet-nv](https://novo-lang.org/packages/parquet-nv) reads the
  columnar file format a frame of this shape is usually stored in.

## Tests

```bash
novo test tests/dfcell_tests.nv        #  7 tests: the cell and the kind inference
novo test tests/dfcolumn_tests.nv      # 13 tests: the column, its nulls and its conversions
novo test tests/dftable_tests.nv       # 12 tests: the frame and its row operations
novo test tests/dfgroup_tests.nv       #  7 tests: group-by and the five aggregations
novo test tests/dfjoin_tests.nv        #  7 tests: the two joins and the null key rule
novo test tests/dfsummary_tests.nv     #  9 tests: describe and the quantiles
```

polars is the reference for the shape and pandas for the summary
numbers. polars's own test suite is the oracle the implementation will
be run against, with pandas's `describe` output as the comparison for
the mean, the sample standard deviation and the quartiles.

The suite asserts each of the five parts of the null rule against the
case that would break it: an aggregation over a column with nulls, a
join whose keys are null on both sides, a group whose key is null, a
sort in both directions, and a numeric conversion of a column with a
null in it. It also asserts that group sizes sum to the row count, that
groups appear in first-appearance order, and that `describe` is defined
for a text column.

The tests compile today and fail at run, each on the
`not implemented: dataframe-nv.<module>.<fn>` panic that is its body.
That is the expected state of an interface release. They turn green one
at a time as bodies land.

## Implementation status

| Item | Implemented |
| --- | --- |
| `dfcell.DfKind`, `.DfCell`, `dfcolumn.DfColumn`, `.DfCells` | declared |
| `dftable.DfTable`, `.DfSortKey`, `dfgroup.DfGroups`, `.DfAgg`, `.DfAggSpec` | declared |
| `dfjoin.DfJoinKind`, `dfsummary.DfSummary`, `dffault.DfFault` | declared |
| `dfcell.kind_of`, `.kind_name`, `.render`, `.parse`, `.infer`, `.compare` | no |
| `dfcolumn.floats`, `.ints`, `.bools`, `.strings`, `.of_cells`, `.with_nulls` | no |
| `dfcolumn.name`, `.rename`, `.kind`, `.len`, `.null_count`, `.is_null`, `.cell`, `.cells_of` | no |
| `dfcolumn.filter`, `.take`, `.cast` | no |
| `dfcolumn.to_floats`, `.to_floats_or`, `.to_ints`, `.mask`, `.present_mask`, `.of_floats`, `.of_ints` | no |
| `dfcolumn.count`, `.sum`, `.mean`, `.min`, `.max`, `.unique_count` | no |
| `dftable.of_columns`, `.empty`, `.of_rows`, `.rows`, `.width`, `.names`, `.column`, `.has` | no |
| `dftable.select`, `.drop`, `.with_column`, `.rename`, `.head`, `.tail`, `.slice` | no |
| `dftable.filter`, `.take`, `.sort`, `.sort_positions` | no |
| `dftable.row_cells`, `.to_rows`, `.concat_rows`, `.drop_nulls` | no |
| `dfgroup.by`, `.count`, `.keys`, `.sizes`, `.positions`, `.frame_of`, `.agg`, `.aggregate` | no |
| `dfjoin.join`, `.join_on`, `.join_with_suffix`, `.join_positions` | no |
| `dfsummary.of_column`, `.describe`, `.quantile`, `.null_counts` | no |
| `dfcsv.of_records`, `.of_records_inferred`, `.infer_kinds`, `.to_records`, `.header_of` | no |
| `dffault`'s ten variants and its `Error` implementation | no |

## Licence

Apache-2.0. See `LICENSE`.

<!-- docs/writing-a-readme.md is the style guide for this page. -->
