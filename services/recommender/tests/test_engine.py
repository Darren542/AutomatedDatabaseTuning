from copy import deepcopy
from datetime import timedelta
import math

import pytest

from recommender.engine import Policy, analyze, identifier, parse_columns, utc
from recommender.fixtures import acceptance_bundle


def test_acceptance_create_rank_explain_and_drop():
    result = analyze(acceptance_bundle())
    creates = [r for r in result['recommendations'] if r['action'] == 'CREATE']
    assert [r['table_name'] for r in creates] == ['Orders', 'Events']
    assert creates[0]['score'] > creates[1]['score']
    assert creates[1]['score_components']['write_penalty'] > creates[0]['score_components']['write_penalty']
    assert creates[0]['affected_queries'][0]['query_id'] == 101
    assert creates[0]['source_evidence'][0]['batch_id']
    assert creates[0]['predicted_impact']['latency_change_ms'] is None
    assert 'CREATE NONCLUSTERED INDEX' in creates[0]['sql']
    drops = [r for r in result['recommendations'] if r['action'] == 'DROP']
    assert drops and all(not r['protected'] for r in drops)
    assert all(r['index_name'].endswith('_10') for r in drops)


@pytest.mark.parametrize('text, expected', [('[a], [b]', ['a', 'b']), ('[a,b], [x]]y]', ['a,b', 'x]y']), ('[a], [a]', ['a']), (None, [])])
def test_column_parsing(text, expected):
    assert parse_columns(text) == expected


@pytest.mark.parametrize('value', ['a', '[a]; DROP TABLE x', '[a],', '[unfinished', '[]', '[a] other'])
def test_unsafe_or_malformed_columns_are_rejected(value):
    with pytest.raises(ValueError): parse_columns(value)


def test_quote_escapes_identifier_not_sql_code():
    assert identifier('A]; DROP TABLE x;--') == '[A]]; DROP TABLE x;--]'


def test_duplicates_merge_includes_without_double_counting_hint_benefit():
    bundle = acceptance_bundle()
    original = analyze(bundle)['recommendations'][0]
    bundle['missing'].append(dict(bundle['missing'][0], index_handle=999, included_columns='[Payload], [OrderDate]'))
    result = analyze(bundle)
    row = next(r for r in result['recommendations'] if r['action'] == 'CREATE' and r['object_id'] == 101)
    assert row['included_columns'] == ['OrderDate', 'Payload']
    assert len(row['source_evidence']) == 2
    assert row['score_components']['raw_optimizer_benefit'] == original['score_components']['raw_optimizer_benefit']


def test_existing_coverage_suppresses_create():
    bundle = acceptance_bundle()
    for r in bundle['index_columns']:
        if r['object_id'] == 101 and r['index_id'] == 9: r['column_id'] = 2
    bundle['index_columns'].append(dict(object_id=101,index_id=9,column_id=4,key_ordinal=0,is_included_column=True,is_descending_key=False))
    result = analyze(bundle)
    assert not any(r['action'] == 'CREATE' and r['object_id'] == 101 for r in result['recommendations'])
    assert any(r['action'] == 'RETAIN' and r['index_name'] == 'IX_Orders_9' for r in result['recommendations'])


@pytest.mark.parametrize('flag', ['is_primary_key','is_unique','is_unique_constraint','has_filter','is_disabled'])
def test_protected_indexes_never_drop(flag):
    bundle = acceptance_bundle()
    index = next(i for i in bundle['indexes'] if i['object_id'] == 101 and i['index_id'] == 10)
    index[flag] = True
    result = analyze(bundle)
    row = next(r for r in result['recommendations'] if r['index_name'] == index['index_name'])
    assert row['action'] == 'RETAIN' and row['sql'] is None


def test_foreign_key_tables_are_conservatively_protected():
    bundle = acceptance_bundle()
    bundle['constraints'] = [dict(object_id=101, referenced_object_id=102, constraint_type='FOREIGN_KEY', unique_index_id=None)]
    assert not any(r['action'] == 'DROP' for r in analyze(bundle)['recommendations'])


@pytest.mark.parametrize('change', ['restart','counter_reset','no_baseline','short_window','changed_definition'])
def test_uncertain_history_cannot_justify_drop(change):
    bundle = acceptance_bundle()
    if change == 'restart': bundle['source']['sql_server_start_time_utc'] = '2026-10-28T01:00:00Z'
    elif change == 'counter_reset':
        for r in bundle['baseline']['usage']: r['user_updates'] = 999999999
    elif change == 'no_baseline': bundle['baseline'] = None
    elif change == 'short_window': bundle['baseline']['source']['observed_at_utc'] = '2026-10-28T11:00:00Z'
    else:
        for c in bundle['baseline']['index_columns']: c['column_id'] = 1
    assert not any(r['action'] == 'DROP' for r in analyze(bundle)['recommendations'])


def test_stale_metadata_refuses_analysis():
    bundle = acceptance_bundle(); bundle['metadata_observed_at_utc'] = '2026-10-01T00:00:00Z'
    with pytest.raises(ValueError, match='Metadata'): analyze(bundle)


@pytest.mark.parametrize('mutation', ['wide_key','max_key','computed','unknown_column'])
def test_unsafe_creation_is_reported_without_sql(mutation):
    bundle = acceptance_bundle()
    col = next(c for c in bundle['columns'] if c['object_id'] == 101 and c['column_id'] == 2)
    if mutation == 'wide_key': col['max_length'] = 2000
    elif mutation == 'max_key': col['max_length'] = -1
    elif mutation == 'computed': col['is_computed'] = True
    else: bundle['missing'][0]['equality_columns'] = '[DoesNotExist]'
    result = analyze(bundle)
    assert not any(r['action'] == 'CREATE' and r['object_id'] == 101 for r in result['recommendations'])
    assert result['diagnostics']


def test_empty_missing_evidence_does_not_fabricate_create():
    bundle = acceptance_bundle(); bundle['missing'] = []
    assert not any(r['action'] == 'CREATE' for r in analyze(bundle)['recommendations'])


def test_deterministic_and_non_mutating():
    bundle = acceptance_bundle(); original = deepcopy(bundle)
    assert analyze(bundle) == analyze(bundle)
    assert bundle == original


def test_policy_weights_change_scores_but_not_protection():
    bundle = acceptance_bundle()
    default = analyze(bundle)
    changed = analyze(bundle, Policy(write_weight=10))
    assert changed['recommendations'][0]['score'] < default['recommendations'][0]['score']
    assert not any(r['action'] == 'DROP' and r['protected'] for r in changed['recommendations'])


def test_sql_literals_do_not_create_query_associations():
    bundle = acceptance_bundle(); bundle['queries'][0]['query_sql_text'] = "SELECT 'FROM [sales].[Orders]'"
    result = analyze(bundle)
    assert next(r for r in result['recommendations'] if r['action']=='CREATE' and r['object_id']==101)['affected_queries'] == []


def test_sustained_unused_index_is_review_only_and_duplicate_keeper_survives():
    bundle = acceptance_bundle(); bundle['baseline']['source']['observed_at_utc'] = '2026-10-10T12:00:00Z'
    for r in bundle['usage']: r['user_seeks'] = 0
    result = analyze(bundle)
    assert next(r for r in result['recommendations'] if r['index_name']=='IX_Orders_9')['action']=='RETAIN'
    for r in result['recommendations']:
        if r['action']=='DROP': assert r['status']=='Review'


def test_operational_maintenance_has_separate_units_and_reset_handling():
    bundle = acceptance_bundle()
    row = dict(object_id=101,index_id=1,partition_number=1,leaf_insert_count=4800,leaf_delete_count=0,leaf_update_count=0)
    bundle['operational'] = [row]
    bundle['baseline']['operational'] = [dict(row,leaf_insert_count=0)]
    result = next(r for r in analyze(bundle)['recommendations'] if r['action']=='CREATE' and r['object_id']==101)
    assert result['score_components']['operational_leaf_writes_per_hour'] == 100
    assert result['score_components']['writes_per_hour'] == pytest.approx(1/48)
    bundle['baseline']['operational'][0]['leaf_insert_count'] = 9999
    result = next(r for r in analyze(bundle)['recommendations'] if r['action']=='CREATE' and r['object_id']==101)
    assert result['score_components']['operational_leaf_writes_per_hour'] is None


def test_unused_nonduplicate_needs_a_sustained_observation_interval():
    bundle = acceptance_bundle()
    item = dict(bundle['indexes'][1],index_id=11,index_name='IX_Orders_Payload')
    column = dict(bundle['index_columns'][1],index_id=11,column_id=4)
    bundle['indexes'].append(item);bundle['index_columns'].append(column)
    bundle['baseline']['indexes'].append(deepcopy(item));bundle['baseline']['index_columns'].append(deepcopy(column))
    usage = dict(bundle['usage'][1],index_id=11,user_seeks=0,user_updates=100)
    bundle['usage'].append(usage);bundle['baseline']['usage'].append(dict(usage,user_updates=0))
    result = next(r for r in analyze(bundle)['recommendations'] if r['index_name']=='IX_Orders_Payload')
    assert result['action']=='RETAIN'
    bundle['baseline']['source']['observed_at_utc']='2026-10-10T12:00:00Z'
    result = next(r for r in analyze(bundle)['recommendations'] if r['index_name']=='IX_Orders_Payload')
    assert result['action']=='DROP' and 'low-value' in result['rationale']


def test_nonfinite_source_cost_cannot_produce_a_candidate():
    bundle=acceptance_bundle();bundle['missing'][0]['avg_total_user_cost']=float('inf')
    result=analyze(bundle)
    assert not any(r['action']=='CREATE' and r['object_id']==101 for r in result['recommendations'])
    assert result['diagnostics']
