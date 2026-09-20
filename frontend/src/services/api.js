// Callers provide paths relative to the configured versioned API base URL.
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

async function errorMessage(response) {
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string' && body.detail.trim()) return body.detail
  } catch {
    // Some upstream/proxy failures do not have a JSON response body.
  }

  return `API request failed with status ${response.status}`
}

export async function apiRequest(path, options = {}, accessToken = null) {
  const authorization = accessToken ? { Authorization: `Bearer ${accessToken}` } : {}
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: { Accept: 'application/json', ...authorization, ...options.headers },
  })

  if (!response.ok) {
    const error = new Error(await errorMessage(response))
    error.status = response.status
    throw error
  }

  if (response.status === 204) return null
  return response.json()
}
