#!/usr/bin/env python3
"""Write tests/differential_tests.nv from SQLite and Python's statistics.

pandas is not installed on the machine this package is built on, so the
oracle is two independent implementations from Python's standard
library that answer the same questions under the same rules:

1. SQLite, through the `sqlite3` module, for group-by, the five
   aggregations, the inner and the left join, and the multi-key sort.
   SQL's null rules are this package's: an aggregate skips a null, a
   null join key matches nothing, a GROUP BY puts every null key in one
   group, and `NULLS LAST` is written on every sort key.  SQLite's SUM
   of an all-null group is NULL where this package answers zero, so the
   sum is taken with TOTAL, and its integer form with COALESCE.
2. `statistics` for describe: `mean`, `stdev` (the sample standard
   deviation) and `quantiles(..., method='inclusive')`, which is the
   linear interpolation numpy and pandas use by default.

The frames are drawn from a seeded generator.  Every float is a
multiple of 0.25 below 64, so a sum is exact in any order and a mean is
the same double whichever implementation divides.

Groups come out of this package in first-appearance order and SQLite
promises no order, so the expected groups are listed in first-appearance
order and each group's answers are read from SQLite by its key.

Run from the package root:  python3 tools/differential.py
The output is passed through `novo fmt`.
"""
import random
import sqlite3
import statistics
import subprocess

CITIES = ['oslo', 'bergen', 'tromso', 'bodo', 'alta']
SEEDS = [7, 19, 42]
ROWS = 36


def frame(seed):
    rng = random.Random(seed)
    rows = []
    for i in range(ROWS):
        city = rng.choice(CITIES) if rng.random() > 0.1 else None
        band = rng.randrange(3) if rng.random() > 0.1 else None
        w = rng.randrange(-40, 256) / 4 if rng.random() > 0.2 else None
        n = rng.randrange(-50, 100) if rng.random() > 0.15 else None
        ok = rng.random() > 0.5 if rng.random() > 0.2 else None
        rows.append((i, city, band, w, n, ok))
    return rows


def other(seed):
    """A frame to join against: a city key with repeats, gaps and a null."""
    rng = random.Random(seed * 101)
    rows = []
    for i in range(9):
        city = rng.choice(CITIES[1:] + ['bergen', 'narvik']) if i != 4 else None
        rows.append((i, city, rng.randrange(1000)))
    return rows


def lit_str(v):
    return '"' + v + '"'


def lit_float(v):
    t = repr(float(v))
    return t


def column_lit(name, kind, values):
    zero = {'Float': '0.0', 'Int': '0', 'Bool': 'false', 'Str': '""'}[kind]
    fmt = {'Float': lit_float, 'Int': str, 'Bool': lambda b: 'true' if b else 'false',
           'Str': lit_str}[kind]
    cells = ', '.join(zero if v is None else fmt(v) for v in values)
    present = ', '.join('false' if v is None else 'true' for v in values)
    return ('DfColumn { name: "%s", cells: Df%sCells([%s]),\n'
            '        present: [%s] }' % (name, kind, cells, present))


def render(v, kind):
    if v is None:
        return ''
    if kind == 'Float':
        f = float(v)
        t = repr(f)
        if t.endswith('.0'):
            return t
        return t
    if kind == 'Bool':
        return 'true' if v else 'false'
    return str(v)


def cell_lit(v, kind):
    if v is None:
        return 'DfNullCell'
    if kind == 'Float':
        return 'DfFloatCell(%s)' % lit_float(v)
    if kind == 'Int':
        return 'DfIntCell(%d)' % v
    if kind == 'Str':
        return 'DfStrCell("%s")' % v
    return 'DfBoolCell(%s)' % ('true' if v else 'false')


def rows_lit(rows):
    return '[' + ', '.join('[' + ', '.join(lit_str(x) for x in r) + ']' for r in rows) + ']'


out = []
emit = out.append

emit('''// differential_tests.nv — group-by, joins, sorts and describe against
// SQLite and Python's statistics module.
//
// Written by tools/differential.py; do not edit by hand.  The script's
// docstring says what each oracle answers and why its rules are this
// package's.  Three seeded frames of %d rows, each with nulls in every
// column.

use std.test
use dfcell
use dfcolumn
use dftable
use dfgroup
use dfjoin
use dfsummary

// Whether two cells hold the same value, a null matching only a null.
fn same(a: DfCell, b: DfCell) -> Bool
    dfcell.compare(a, b) == Some(Equal)

fn same_cells(got: [DfCell], want: [DfCell]) -> Bool
    if list.len(got) != list.len(want)
        return false
    for i in 0..list.len(got)
        if not same(got[i], want[i])
            return false
    true

fn close(got: ?Float, want: ?Float) -> Bool
    match (got, want)
        (Some(a), Some(b)) =>
            let d = if a > b then a - b else b - a
            let m = if b < 0.0 then 0.0 - b else b
            d <= 1e-12 * (if m > 1.0 then m else 1.0)
        (None, None)       => true
        _                  => false

// One aggregation, checked against the answers SQLite gave per group.
fn check_agg(g: DfGroups, t: DfTable, column: Str, how: DfAgg, want: [DfCell]) [io]
    match dfgroup.agg(g, t, DfAggSpec { column: column, how: how, into: "out" })
        Ok(c)  => test.assert(same_cells(dfcolumn.cells_of(c), want))
        Err(e) => test.fail("agg over ${column} failed: ${e.message()}")

// An aggregation SQLite answered with NULL for some group, which this
// package refuses as an empty group.
fn check_agg_empty(g: DfGroups, t: DfTable, column: Str, how: DfAgg) [io]
    match dfgroup.agg(g, t, DfAggSpec { column: column, how: how, into: "out" })
        Ok(_)  => test.fail("an aggregation over an all-null group answered")
        Err(e) =>
            match e
                DfEmptyGroup(_) => test.assert(true)
                _               => test.fail("an empty group reported ${e.message()}")

fn check_summary(c: DfColumn, count: Int, mean: ?Float, sd: ?Float, q25: ?Float, median: ?Float,
                 q75: ?Float) [io]
    match dfsummary.of_column(c)
        Ok(s)  =>
            test.assert(s.count == count)
            test.assert(close(s.mean, mean))
            test.assert(close(s.sd, sd))
            test.assert(close(s.q25, q25))
            test.assert(close(s.median, median))
            test.assert(close(s.q75, q75))
        Err(e) => test.fail("of_column failed: ${e.message()}")
''' % ROWS)

KINDS = [('id', 'Int'), ('city', 'Str'), ('band', 'Int'), ('w', 'Float'), ('n', 'Int'), ('ok', 'Bool')]

for seed in SEEDS:
    rows = frame(seed)
    orows = other(seed)
    db = sqlite3.connect(':memory:')
    db.execute('create table t (id integer, city text, band integer, w real, n integer, ok integer)')
    db.executemany('insert into t values (?, ?, ?, ?, ?, ?)', rows)
    db.execute('create table o (rid integer, city text, score integer)')
    db.executemany('insert into o values (?, ?, ?)', orows)

    emit('fn frame_%d() -> DfTable' % seed)
    emit('    let cols = [')
    lits = []
    for j, (name, kind) in enumerate(KINDS):
        lits.append('        ' + column_lit(name, kind, [r[j] for r in rows]))
    emit(',\n'.join(lits) + ']')
    emit('    DfTable { columns: cols, rows: %d }\n' % ROWS)
    emit('fn other_%d() -> DfTable' % seed)
    emit('    let cols = [')
    okinds = [('rid', 'Int'), ('city', 'Str'), ('score', 'Int')]
    lits = ['        ' + column_lit(n, k, [r[j] for r in orows]) for j, (n, k) in enumerate(okinds)]
    emit(',\n'.join(lits) + ']')
    emit('    DfTable { columns: cols, rows: %d }\n' % len(orows))

    # Group-by, one key and two keys.
    for keys in (['city'], ['city', 'band']):
        firsts = []
        seen = set()
        for r in rows:
            k = tuple(r[[n for n, _ in KINDS].index(x)] for x in keys)
            if k not in seen:
                seen.add(k)
                firsts.append(k)
        tag = '_'.join(keys)
        emit('@test')
        emit('fn test_group_by_%s_matches_sqlite_%d() [io]' % (tag, seed))
        emit('    let t = frame_%d()' % seed)
        emit('    match dfgroup.by(t, [%s])' % ', '.join(lit_str(k) for k in keys))
        emit('        Err(e) => test.fail("by failed: ${e.message()}")')
        emit('        Ok(g)  =>')
        key_rows = [[render(v, dict(KINDS)[keys[i]]) for i, v in enumerate(k)] for k in firsts]
        emit('            test.case("the groups, in first-appearance order")')
        emit('            test.assert(dftable.to_rows(dfgroup.keys(g)) == %s)' % rows_lit(key_rows))

        def where(k):
            parts, args = [], []
            for name, v in zip(keys, k):
                if v is None:
                    parts.append('%s is null' % name)
                else:
                    parts.append('%s = ?' % name)
                    args.append(v)
            return ' and '.join(parts), args

        sizes = []
        for k in firsts:
            w, a = where(k)
            sizes.append(db.execute('select count(*) from t where ' + w, a).fetchone()[0])
        emit('            test.case("the sizes sum to the row count")')
        emit('            test.assert(same_cells(dfcolumn.cells_of(dfgroup.sizes(g, "rows")), [%s]))'
             % ', '.join('DfIntCell(%d)' % s for s in sizes))
        for col, kind in (('w', 'Float'), ('n', 'Int'), ('city', 'Str'), ('ok', 'Bool')):
            if col in keys:
                continue
            aggs = [('DfCount', 'count(%s)' % col, 'Int')]
            if kind in ('Float', 'Int'):
                sum_sql = 'total(%s)' % col if kind == 'Float' else 'coalesce(sum(%s), 0)' % col
                aggs += [('DfSum', sum_sql, kind), ('DfMean', 'avg(%s)' % col, 'Float')]
            if kind != 'Bool':
                aggs += [('DfMin', 'min(%s)' % col, kind), ('DfMax', 'max(%s)' % col, kind)]
            for how, sql, rkind in aggs:
                answers = []
                for k in firsts:
                    w, a = where(k)
                    answers.append(db.execute('select %s from t where %s' % (sql, w), a).fetchone()[0])
                emit('            test.case("%s over %s")' % (how, col))
                if any(v is None for v in answers):
                    emit('            check_agg_empty(g, t, "%s", %s)' % (col, how))
                else:
                    emit('            check_agg(g, t, "%s", %s, [%s])'
                         % (col, how, ', '.join(cell_lit(v, rkind) for v in answers)))
        emit('')

    # Joins on the city key, in the left frame's order and then the right's.
    for how, sql_how in (('DfInnerJoin', 'join'), ('DfLeftJoin', 'left join')):
        got = db.execute('select t.id, t.city, o.score from t %s o on t.city = o.city '
                         'order by t.id, o.rid' % sql_how).fetchall()
        want = [[render(a, 'Int'), render(b, 'Str'), render(c, 'Int')] for a, b, c in got]
        emit('@test')
        emit('fn test_%s_on_city_matches_sqlite_%d() [io]' % (how.lower()[2:], seed))
        emit('    match dftable.select(frame_%d(), ["id", "city"])' % seed)
        emit('        Err(e) => test.fail("select failed: ${e.message()}")')
        emit('        Ok(l)  =>')
        emit('            match dftable.select(other_%d(), ["city", "score"])' % seed)
        emit('                Err(e) => test.fail("select failed: ${e.message()}")')
        emit('                Ok(r)  =>')
        emit('                    match dfjoin.join(l, r, "city", %s)' % how)
        emit('                        Err(e) => test.fail("join failed: ${e.message()}")')
        emit('                        Ok(j)  =>')
        emit('                            test.assert(dftable.names(j) == ["id", "city", "score"])')
        emit('                            test.assert(dftable.rows(j) == %d)' % len(want))
        emit('                            test.assert(dftable.to_rows(j) == %s)' % rows_lit(want))
        emit('')

    # A stable sort on two keys, nulls last in both directions.
    order = db.execute('select id from t order by city asc nulls last, w desc nulls last, id').fetchall()
    emit('@test')
    emit('fn test_sort_by_city_then_w_descending_matches_sqlite_%d() [io]' % seed)
    emit('    let keys = [DfSortKey { column: "city", descending: false }, '
         'DfSortKey { column: "w", descending: true }]')
    emit('    match dftable.sort_positions(frame_%d(), keys)' % seed)
    emit('        Ok(p)  => test.assert(p == [%s])' % ', '.join(str(r[0]) for r in order))
    emit('        Err(e) => test.fail("sort_positions failed: ${e.message()}")')
    emit('')

    # describe's numbers against statistics.
    emit('@test')
    emit('fn test_summary_matches_python_statistics_%d() [io]' % seed)
    emit('    let t = frame_%d()' % seed)
    for col, j in (('w', 3), ('n', 4)):
        xs = [float(r[j]) for r in rows if r[j] is not None]
        mean = statistics.mean(xs)
        sd = statistics.stdev(xs)
        q = statistics.quantiles(xs, n=4, method='inclusive')
        emit('    test.case("%s")' % col)
        emit('    match dftable.column(t, "%s")' % col)
        emit('        Ok(c)  => check_summary(c, %d, Some(%r), Some(%r), Some(%r), Some(%r), Some(%r))'
             % (len(xs), mean, sd, q[0], q[1], q[2]))
        emit('        Err(e) => test.fail("column failed: ${e.message()}")')
    emit('')

text = '\n'.join(out) + '\n'
path = 'tests/differential_tests.nv'
open(path, 'w').write(text)
subprocess.run(['novo', 'fmt', path], check=False)
