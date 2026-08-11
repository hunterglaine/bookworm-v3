export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/** FastAPI returns `{detail: "..."}`, or a list of issues for a 422. */
function extractDetail(body: unknown): string | null {
  if (typeof body !== 'object' || body === null || !('detail' in body)) return null

  const { detail } = body as { detail: unknown }
  if (typeof detail === 'string') return detail

  if (Array.isArray(detail)) {
    const first: unknown = detail[0]
    if (typeof first === 'object' && first !== null && 'msg' in first) {
      const { msg } = first as { msg: unknown }
      if (typeof msg === 'string') return msg
    }
  }
  return null
}

/**
 * Thin fetch wrapper. `credentials: 'include'` matters -- auth is an httpOnly
 * cookie, so it has to ride along on every request.
 */
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })

  if (!response.ok) {
    // Surfacing the server's reason is what lets a form say "Email already
    // registered" rather than "Request failed".
    let message = `Request to ${path} failed`
    try {
      message = extractDetail(await response.json()) ?? message
    } catch {
      // Non-JSON error body -- keep the generic message.
    }
    throw new ApiError(message, response.status)
  }

  // 204 carries no body, so response.json() would throw on it.
  if (response.status === 204) return undefined as T

  return response.json() as Promise<T>
}
