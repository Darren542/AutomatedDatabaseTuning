export function filterRecommendations(rows, action, status, search) {
  const term = search.trim().toLowerCase()
  return rows.filter(row => (!action || row.action === action) && (!status || row.status === status) &&
    (!term || `${row.schema_name}.${row.table_name} ${row.index_name}`.toLowerCase().includes(term)))
}

export function scoreNumber(value) { return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 4 }) }
