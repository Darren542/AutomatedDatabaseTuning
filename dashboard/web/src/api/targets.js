const messages = {
  connected: 'Connection and collector permissions validated.',
  insufficient_permissions: 'Connected, but required collector permissions are missing.',
  excessive_permissions: 'Connected, but this account can perform DDL. A restricted account is recommended; you can acknowledge the warning and continue.',
  authentication_failed: 'Authentication failed. Check the authentication mode and database account access.',
  timeout: 'The connection test timed out. Check the server address or adjust the timeout.',
  connection_failed: 'Could not connect. Check the instance name, network access, and certificate settings.',
  database_unavailable: 'The selected database is unavailable or inaccessible to this account.',
  driver_unavailable: 'Install the selected SQL Server ODBC driver on the API machine.',
  validation_failed: 'Could not validate database access. Check the database and account permissions.',
  invalid_configuration: 'Check the target configuration and authentication fields.',
}

export function toRequest(form) {
  const { username, password, ...target } = form
  return {
    ...target,
    connection_timeout_seconds: Number(target.connection_timeout_seconds),
    query_timeout_seconds: Number(target.query_timeout_seconds),
    ...(target.authentication === 'sql' ? { credentials: { username, password } } : {}),
  }
}

export async function testConnection(form, signal, fetcher = fetch) {
  const response = await fetcher('/api/v1/targets/test-connection', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(toRequest(form)), signal,
  })
  if (response.status === 422) throw new Error('Check the required fields, authentication details, and timeout values.')
  if (!response.ok) throw new Error('The API could not complete the test. Check that the backend is running.')
  let result
  try { result = await response.json() } catch { throw new Error('The API returned an unreadable response. Check that the backend is running.') }
  if (!result || typeof result.connected !== 'boolean' || !Object.hasOwn(messages, result.code) ||
      result.connected !== ['connected', 'insufficient_permissions', 'excessive_permissions'].includes(result.code)) {
    throw new Error('The API returned an unexpected response. Try again after checking the backend.')
  }
  // Display known messages only; never echo raw response text or submitted secrets.
  return { connected: result.connected, message: messages[result.code] }
}


export function canSaveTarget(result, acknowledged = false, saveWarning = false) {
  return result?.connected === true && result.collector_ready === true &&
    ((!saveWarning && result.ddl_restricted === true) || acknowledged === true)
}
