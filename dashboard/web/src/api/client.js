export async function request(path, { method = 'GET', body, signal } = {}) {
  let response
  try {
    response = await fetch(`/api/v1${path}`, {
      method, signal, headers: body ? { 'Content-Type': 'application/json' } : {},
      ...(body ? { body: JSON.stringify(body) } : {}),
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new Error('Cannot reach the API. Check that the backend is running.')
  }
  if (!response.ok) {
    const messages = {
      404: 'The selected target or collection was not found. Refresh the list.',
      409: 'This action conflicts with the current state. A collection may already be running, or the target name may already exist.',
      422: 'Check the configuration, credentials reference, permissions, and date range. The target must be collector-ready before it can be saved.',
      503: 'The repository is unavailable. Check its configuration and apply the repository SQL migrations.',
    }
    throw new Error(messages[response.status] || 'The API could not complete this request. Refresh to inspect the saved state.')
  }
  try { return await response.json() } catch { throw new Error('The API returned an unreadable response.') }
}

export function utcDate(value) {
  if (!value) return null
  const hasZone = /(?:Z|[+-]\d\d:\d\d)$/i.test(value)
  return new Date(hasZone ? value : `${value}Z`)
}
export function dateLabel(value) {
  return utcDate(value)?.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) || '—'
}
export const number = value => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 1 })
