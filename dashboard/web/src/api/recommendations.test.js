import test from 'node:test'
import assert from 'node:assert/strict'
import { filterRecommendations, scoreNumber } from './recommendations.js'

const rows = [
  { action: 'CREATE', status: 'Suggested', schema_name: 'sales', table_name: 'Orders', index_name: 'IX_AT_Orders' },
  { action: 'CREATE', status: 'Review', schema_name: 'sales', table_name: 'Events', index_name: 'IX_AT_Events' },
  { action: 'RETAIN', status: 'Informational', schema_name: 'sales', table_name: 'Orders', index_name: 'PK_Orders' },
]
test('action and status filters preserve backend rank order', () => {
  assert.deepEqual(filterRecommendations(rows, 'CREATE', '', ''), rows.slice(0, 2))
  assert.deepEqual(filterRecommendations(rows, 'CREATE', 'Review', ''), [rows[1]])
})
test('search matches table/index names and cannot expose hidden actions', () => {
  assert.deepEqual(filterRecommendations(rows, 'RETAIN', '', ' orders '), [rows[2]])
  assert.deepEqual(filterRecommendations(rows, 'DROP', '', 'orders'), [])
})
test('small measured write pressure is not displayed as zero', () => {
  assert.notEqual(scoreNumber(1/48), '0')
})
