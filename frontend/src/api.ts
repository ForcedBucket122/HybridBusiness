export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch('/api' + path, { method, headers: { 'Content-Type': 'application/json', 'X-LocalAI': '1' }, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(15000) })
  } catch { throw new Error('Brak połączenia z backendem. Sprawdź, czy LocalAICompany jest uruchomione.') }
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: `Błąd HTTP ${response.status}` }))
    throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
  }
  return response.json()
}
