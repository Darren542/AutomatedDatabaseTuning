"""Pure, advisory physical-design analysis over a persisted collector snapshot."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import re

VERSION = '0.2.0'


@dataclass(frozen=True)
class Policy:
    read_weight: float = 1.0
    write_weight: float = 1.0
    storage_weight: float = 0.1
    minimum_drop_hours: float = 24.0
    minimum_unused_hours: float = 168.0
    maximum_metadata_age_hours: float = 24.0

    def __post_init__(self):
        for key, value in asdict(self).items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f'{key} must be finite and non-negative.')


def utc(value):
    value = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def identifier(value):
    return '[' + value.replace(']', ']]') + ']'


def parse_columns(value):
    """Parse DMV bracket-quoted lists, including commas and escaped ] in names."""
    if not value or not value.strip():
        return []
    result, pos = [], 0
    while pos < len(value):
        while pos < len(value) and value[pos].isspace():
            pos += 1
        if pos >= len(value) or value[pos] != '[':
            raise ValueError('Column evidence is not a bracket-quoted identifier list.')
        pos += 1
        name = ''
        while pos < len(value):
            char = value[pos]
            pos += 1
            if char == ']':
                if pos < len(value) and value[pos] == ']':
                    name += ']'
                    pos += 1
                else:
                    break
            else:
                name += char
        else:
            raise ValueError('Unterminated column identifier.')
        if not name:
            raise ValueError('Empty column identifier.')
        if name not in result:
            result.append(name)
        while pos < len(value) and value[pos].isspace():
            pos += 1
        if pos == len(value):
            break
        if value[pos] != ',':
            raise ValueError('Unexpected text after column identifier.')
        pos += 1
        if not value[pos:].strip():
            raise ValueError('Trailing comma in column evidence.')
    return result


def _number(value):
    number = float(value or 0)
    if not math.isfinite(number) or number < 0:
        raise ValueError('Source counters/costs must be finite and non-negative.')
    return number


KEY_TYPES = set('bigint binary bit char date datetime datetime2 datetimeoffset decimal float int money nchar numeric nvarchar real smalldatetime smallint smallmoney time tinyint uniqueidentifier varbinary varchar timestamp rowversion'.split())
INCLUDE_TYPES = KEY_TYPES | {'xml'}


def column_width(column, key=False):
    data_type = column['data_type'].lower()
    if column['is_computed'] or data_type not in (KEY_TYPES if key else INCLUDE_TYPES):
        raise ValueError('Computed or unsupported column type requires manual design review.')
    width = column['max_length']
    if width == -1:
        if key:
            raise ValueError('MAX/LOB columns cannot be index keys.')
        return 4096  # Explicit planning assumption, not measured stored width.
    if width <= 0:
        raise ValueError('Column width is unavailable.')
    return width


def signature(index, columns):
    return (
        tuple((c['column_id'], bool(c['is_descending_key'])) for c in sorted(columns, key=lambda c: c['key_ordinal']) if c['key_ordinal'] > 0 and not c['is_included_column']),
        tuple(sorted(c['column_id'] for c in columns if c['is_included_column'])),
        index['index_type'], bool(index['has_filter']), index.get('filter_definition'),
        bool(index['is_disabled']), bool(index['is_unique']),
    )


def _matching_queries(table, queries):
    # This is supporting evidence, never a claim that a plan uses a table/index.
    ident = r'(?:\[(?:[^\]]|\]\])+\]|"(?:[^"]|"")+"|[\w]+)'
    pattern = re.compile(r'\b(?:FROM|JOIN|UPDATE|INTO)\s+(' + ident + r')\s*\.\s*(' + ident + r')', re.I)
    def unquote(token):
        return token[1:-1].replace(']]', ']') if token.startswith('[') else token[1:-1].replace('""', '"') if token.startswith('"') else token
    matches = {}
    for row in queries:
        text = row['query_sql_text']
        # Discard comments and string literals so examples/dynamic SQL are not evidence.
        cleaned = re.sub(r"'(?:''|[^'])*'|--[^\n]*|/\*.*?\*/", ' ', text, flags=re.S)
        referenced = [(unquote(a).casefold(), unquote(b).casefold()) for a, b in pattern.findall(cleaned)]
        if (table['schema_name'].casefold(), table['table_name'].casefold()) not in referenced:
            continue
        qid = row['query_id']
        result = matches.setdefault(qid, dict(query_id=qid, query_sql_text=text[:4000], evidence_ids=[], execution_count=0, total_duration_ms=0.0, total_cpu_ms=0.0, logical_reads=0.0, association='schema-qualified SQL text match; not plan-proven'))
        if row['evidence_id'] in result['evidence_ids']:
            continue
        result['evidence_ids'].append(row['evidence_id'])
        count = _number(row['execution_count'])
        result['execution_count'] += int(count)
        result['total_duration_ms'] += _number(row.get('avg_duration_microseconds')) * count / 1000
        result['total_cpu_ms'] += _number(row.get('avg_cpu_time_microseconds')) * count / 1000
        result['logical_reads'] += _number(row.get('avg_logical_io_reads')) * count
    return sorted(matches.values(), key=lambda q: -q['total_duration_ms'])[:20]


def analyze(bundle, policy=None, *, score=True):
    policy = policy or Policy()
    observed = utc(bundle['source']['observed_at_utc'])
    metadata_time = utc(bundle['metadata_observed_at_utc'])
    age = (observed - metadata_time).total_seconds() / 3600
    if age < 0 or age > policy.maximum_metadata_age_hours:
        raise ValueError('Metadata is stale or from the future. Collect again with force_metadata=true.')
    tables = {t['object_id']: t for t in bundle['tables']}
    cols = {(c['object_id'], c['column_id']): c for c in bundle['columns']}
    indexes = {(i['object_id'], i['index_id']): i for i in bundle['indexes']}
    index_columns = {}
    for item in bundle['index_columns']:
        index_columns.setdefault((item['object_id'], item['index_id']), []).append(item)
    baseline = bundle.get('baseline')
    compatible = bool(baseline and all(bundle['source'].get(k) == baseline['source'].get(k) and bundle['source'].get(k) is not None for k in ['sql_server_start_time_utc', 'database_id', 'database_create_date_utc']))
    hours = (observed - utc(baseline['source']['observed_at_utc'])).total_seconds() / 3600 if compatible else 0
    compatible = compatible and hours > 0 and not bundle['source'].get('dmv_reset_detected', False)
    usage = {(r['object_id'], r['index_id']): r for r in bundle['usage']}
    old_usage = {(r['object_id'], r['index_id']): r for r in baseline['usage']} if compatible else {}
    old_indexes = {(r['object_id'], r['index_id']): r for r in baseline.get('indexes', [])} if compatible else {}
    old_columns = {}
    for r in baseline.get('index_columns', []) if compatible else []:
        old_columns.setdefault((r['object_id'], r['index_id']), []).append(r)
    diagnostics, recommendations = [], []
    query_cache = {}

    def deltas(key):
        current, previous = usage.get(key), old_usage.get(key)
        if not current or not previous:
            return None
        fields = ['user_seeks', 'user_scans', 'user_lookups', 'user_updates']
        values = {f: _number(current[f]) - _number(previous[f]) for f in fields}
        return values if all(v >= 0 for v in values.values()) else None

    def table_writes(oid):
        # Base-table maintenance is counted once, not summed over every index.
        base_keys = [k for k in usage if k[0] == oid and k[1] in (0, 1)]
        values = [deltas(k)['user_updates'] / hours for k in base_keys if deltas(k) is not None]
        return max(values) if values else None

    def operational_writes(oid):
        if not compatible:
            return None
        fields = ['leaf_insert_count', 'leaf_delete_count', 'leaf_update_count']
        previous = {(r['object_id'], r['index_id'], r['partition_number']): r for r in baseline.get('operational', [])}
        total = 0.0
        found = False
        for row in bundle.get('operational', []):
            key = (row['object_id'], row['index_id'], row['partition_number'])
            if row['object_id'] != oid or row['index_id'] not in (0, 1):
                continue
            if key not in previous:
                return None
            changes = [_number(row[f]) - _number(previous[key][f]) for f in fields]
            if any(v < 0 for v in changes):
                return None
            found = True
            total += sum(changes)
        return total / hours if found else None

    def make(action, table, keys, includes, index_name, sources, reason, read_hint=0, width=0, protected=False):
        oid = table['object_id']
        if oid not in query_cache:
            query_cache[oid] = _matching_queries(table, bundle['queries'])
        queries = query_cache[oid]
        writes = table_writes(oid)
        storage = _number(table['row_count']) * (width + 16) * 1.2 / (1024 ** 2) if action == 'CREATE' else 0.0
        leaf_writes = operational_writes(oid)
        read_score = write_penalty = storage_penalty = net = 0.0
        if score and action == 'CREATE':
            read_score = 10 * math.log1p(read_hint)
            write_penalty = 10 * math.log1p(writes) * max(width, 16) / 128 if writes is not None else 10 * max(width, 16) / 128
            storage_penalty = math.log1p(storage) + (math.log1p(leaf_writes) * max(width, 16) / 256 if leaf_writes is not None else 0)
            net = policy.read_weight * read_score - policy.write_weight * write_penalty - policy.storage_weight * storage_penalty
        material = json.dumps([action, oid, keys, includes, index_name], ensure_ascii=False)
        rid = sha256(material.encode()).hexdigest()[:20]
        sql = None
        target = identifier(table['schema_name']) + '.' + identifier(table['table_name'])
        if action == 'CREATE':
            sql = f'CREATE NONCLUSTERED INDEX {identifier(index_name)} ON {target} (' + ', '.join(identifier(k) for k in keys) + ')'
            if includes:
                sql += ' INCLUDE (' + ', '.join(identifier(c) for c in includes) + ')'
            sql += ';'
        elif action == 'DROP':
            sql = f'DROP INDEX {identifier(index_name)} ON {target};'
        warnings = ['Advisory only; validate against a replay workload before applying.', 'Query associations are textual and may be incomplete.']
        if action == 'CREATE':
            warnings += ['Usage maintenance counts statements; operational leaf counters count row operations. They are separate heuristic factors, not directly equivalent units.', 'Scores are heuristic points, not predicted milliseconds or guaranteed improvement.', 'Read evidence is cumulative DMV optimizer cost; write pressure uses a separate reset-compatible observation interval.', 'Storage uses declared column widths and an assumed 20% overhead; MAX includes assume 4096 bytes.']
            if writes is None:
                warnings.append('Write pressure is unknown; a fallback penalty is used. Collect compatible snapshots before approval.')
            if not queries:
                warnings.append('No schema-qualified query text could be associated with this table in the selected window.')
        return dict(recommendation_id=rid, action=action, status='Review' if action == 'DROP' or (action == 'CREATE' and (net <= 0 or writes is None)) else 'Suggested' if action == 'CREATE' else 'Informational', object_id=oid, schema_name=table['schema_name'], table_name=table['table_name'], index_name=index_name, key_columns=keys, included_columns=includes, sql=sql, protected=protected, score=round(net, 4), score_components=dict(read_benefit=round(read_score, 4), write_penalty=round(write_penalty, 4), maintenance_penalty=round(storage_penalty, 4), raw_optimizer_benefit=round(read_hint, 4), row_width_bytes=width, writes_per_hour=writes, operational_leaf_writes_per_hour=leaf_writes), predicted_impact=dict(storage_estimate_mb=round(storage, 4), latency_change_ms=None, units='heuristic score; storage MB; writes/hour'), rationale=reason, warnings=warnings, affected_queries=queries, source_evidence=sources)

    groups = {}
    for row in bundle['missing']:
        oid = row['object_id']
        try:
            if oid not in tables:
                raise ValueError('Table is absent from the selected metadata snapshot.')
            mapping = {c['column_name']: c for (obj, _), c in cols.items() if obj == oid}
            equality = parse_columns(row['equality_columns'])
            ranges = [c for c in parse_columns(row['inequality_columns']) if c not in equality]
            includes = [c for c in parse_columns(row['included_columns']) if c not in equality + ranges]
            if not equality + ranges or any(c not in mapping for c in equality + ranges + includes):
                raise ValueError('Missing/unknown key or include columns.')
            equality.sort(key=lambda c: mapping[c]['column_id'])
            key = (oid, tuple(equality), tuple(ranges))
            benefit = _number(row['avg_total_user_cost']) * min(_number(row['avg_user_impact']), 100) / 100 * (_number(row['user_seeks']) + _number(row['user_scans']))
            if not math.isfinite(benefit):
                raise ValueError('Optimizer benefit overflowed the supported numeric range.')
            group = groups.setdefault(key, dict(includes=set(), rows=[], benefit=0.0))
            group['includes'].update(includes)
            group['rows'].append(dict(group_handle=row['group_handle'], index_handle=row['index_handle'], batch_id=str(bundle['batch']['batch_id'])))
            # Multiple hints for the same shape are not independent workload counts.
            group['benefit'] = max(group['benefit'], benefit)
        except ValueError as error:
            diagnostics.append(dict(object_id=oid, reason=str(error), index_handle=row['index_handle']))
    retained = set()
    for (oid, eq, ranges), group in sorted(groups.items()):
        table = tables[oid]
        mapping = {c['column_name']: c for (obj, _), c in cols.items() if obj == oid}
        keys = list(eq + ranges)
        includes = sorted(group['includes'], key=lambda c: mapping[c]['column_id'])
        try:
            widths = [column_width(mapping[c], True) for c in keys]
            if len(keys) > 32 or sum(widths) > 1700 or len(keys + includes) > 1023:
                raise ValueError('Candidate exceeds rowstore nonclustered key/column limits.')
            width = sum(widths) + sum(column_width(mapping[c]) for c in includes)
            covered = None
            for key, index in sorted(indexes.items()):
                if key[0] != oid or index['index_type'] not in (1, 2) or index['is_disabled'] or index['has_filter']:
                    continue
                ic = index_columns.get(key, [])
                index_keys = [cols[(oid, c['column_id'])]['column_name'] for c in sorted(ic, key=lambda c: c['key_ordinal']) if c['key_ordinal'] > 0 and not c['is_included_column']]
                available = {cols[(oid, c['column_id'])]['column_name'] for c in ic}
                # Clustered keys are implicitly carried in ordinary nonclustered indexes.
                for ck, ci in indexes.items():
                    if ck[0] == oid and ci['index_type'] == 1:
                        available.update(cols[(oid, c['column_id'])]['column_name'] for c in index_columns.get(ck, []) if c['key_ordinal'] > 0)
                if set(index_keys[:len(eq)]) == set(eq) and index_keys[len(eq):len(keys)] == list(ranges) and len(index_keys) >= len(keys) and set(keys + includes) <= available:
                    covered = (key, index)
                    break
            if covered:
                key, index = covered
                if key not in retained:
                    recommendations.append(make('RETAIN', table, keys, includes, index['index_name'], group['rows'], 'Missing-index shape is already covered by this enabled, unfiltered index.', protected=bool(index['is_unique'] or index['is_primary_key'] or index['is_unique_constraint'])))
                    retained.add(key)
                else:
                    next(r for r in recommendations if r['action'] == 'RETAIN' and r['object_id'] == oid and r['index_name'] == index['index_name'])['source_evidence'].extend(group['rows'])
                continue
            digest = sha256(json.dumps([oid, keys, includes]).encode()).hexdigest()[:12]
            name = 'IX_AT_' + re.sub(r'[^\w]', '_', table['table_name'])[:70] + '_' + digest
            recommendations.append(make('CREATE', table, keys, includes, name, group['rows'], 'Missing-index evidence suggests a new covering access path. Read benefit is balanced against observed write pressure and estimated width/storage.', group['benefit'], width))
        except (ValueError, KeyError) as error:
            diagnostics.append(dict(object_id=oid, reason=str(error), source_evidence=group['rows']))

    for key, index in sorted(indexes.items()):
        oid, iid = key
        if key in retained or oid not in tables or not index.get('index_name'):
            continue
        ic = index_columns.get(key, [])
        protected = bool(index['is_unique'] or index['is_primary_key'] or index['is_unique_constraint'] or index['index_type'] != 2 or index['is_disabled'] or index['has_filter'])
        for constraint in bundle['constraints']:
            if (constraint['object_id'] == oid and constraint.get('unique_index_id') == iid) or (constraint['constraint_type'] == 'FOREIGN_KEY' and oid in (constraint['object_id'], constraint.get('referenced_object_id'))):
                protected = True  # FK column mapping is not collected; protect the whole table.
        names = [cols[(oid, c['column_id'])]['column_name'] for c in sorted(ic, key=lambda c: c['key_ordinal']) if c['key_ordinal'] > 0 and (oid, c['column_id']) in cols]
        includes = [cols[(oid, c['column_id'])]['column_name'] for c in ic if c['is_included_column'] and (oid, c['column_id']) in cols]
        reason, action = 'Retain: protected, special, disabled, or filtered index requires manual review.', 'RETAIN'
        delta = deltas(key)
        unchanged = key in old_indexes and signature(index, ic) == signature(old_indexes[key], old_columns.get(key, []))
        duplicate = next((other for other, ix in sorted(indexes.items()) if other[0] == oid and other != key and other[1] < iid and not ix['is_disabled'] and signature(index, ic)[:2] == signature(ix, index_columns.get(other, []))[:2] and ix['index_type'] in (1, 2) and not ix['has_filter']), None)
        if not protected:
            if not compatible or not delta or not unchanged or hours < policy.minimum_drop_hours:
                reason = 'Retain: compatible, unchanged-index observations over the minimum observation period are unavailable.'
            elif sum(delta[f] for f in ['user_seeks', 'user_scans', 'user_lookups']) > 0:
                reason = 'Retain: read activity was observed during the compatible observation interval.'
            elif duplicate and delta['user_updates'] > 0:
                action, reason = 'DROP', f'Potential exact duplicate of index {indexes[duplicate]["index_name"]}; no reads and positive maintenance were observed over {hours:.1f} hours. Manual validation is required.'
            elif any(other[0] == oid and other[1] > iid and signature(index, ic)[:2] == signature(ix, index_columns.get(other, []))[:2] and not ix['is_disabled'] and not ix['has_filter'] and ix['index_type'] == 2 for other, ix in indexes.items()):
                reason = 'Retain: keep one canonical access path while redundant copies are reviewed.'
            elif hours >= policy.minimum_unused_hours and delta['user_updates'] > 0:
                action, reason = 'DROP', f'Potential low-value index: no observed reads and positive maintenance over {hours:.1f} compatible hours. Rare workloads may still need it.'
            else:
                reason = 'Retain: insufficient sustained unused/maintenance evidence for DROP advice.'
        recommendation = make(action, tables[oid], names, includes, index['index_name'], [dict(batch_id=str(bundle['batch']['batch_id']), index_id=iid, baseline_batch_id=str(baseline['batch_id']) if compatible else None)], reason, protected=protected)
        recommendation['usage_evidence'] = dict(observation_hours=round(hours, 4) if compatible else None, compatible=compatible, deltas=delta)
        recommendations.append(recommendation)

    creates = [r for r in recommendations if r['action'] == 'CREATE']
    for row in creates:
        alternatives = [other['recommendation_id'] for other in creates if other is not row and other['object_id'] == row['object_id'] and (
            other['key_columns'][:len(row['key_columns'])] == row['key_columns'] or row['key_columns'][:len(other['key_columns'])] == other['key_columns'])]
        row['overlapping_recommendation_ids'] = alternatives
        if alternatives:
            row['warnings'].append('Overlaps another proposed index shape. Review these as alternatives instead of blindly applying the whole set.')

    recommendations.sort(key=lambda r: ({'CREATE': 0, 'DROP': 1, 'RETAIN': 2}[r['action']], -r['score'], r['recommendation_id']))
    for rank, item in enumerate(recommendations, 1):
        item['rank'] = rank
    return dict(engine_version=VERSION, policy=asdict(policy), recommendations=recommendations, diagnostics=diagnostics, warnings=['Analysis uses persisted evidence; source statistics and metadata may have changed since collection.', 'Missing-index DMV hints are not guaranteed optimizations. Revalidate schema and safety before any future execution.'])
