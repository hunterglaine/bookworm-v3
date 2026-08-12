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

const REFRESH_PATH = '/api/v1/auth/refresh'

/** A 401 from these means "wrong credentials" or "session gone", not "token
 *  expired" -- refreshing in response would be pointless or recursive. */
const NO_REFRESH = [REFRESH_PATH, '/api/v1/auth/login', '/api/v1/auth/register']

let refreshInFlight: Promise<boolean> | null = null

/**
 * Exchange the refresh cookie for a fresh access token.
 *
 * Single-flight, and that is not an optimisation. Refresh tokens rotate, and
 * the server treats a replayed rotated token as theft and revokes every session
 * for the user. Two parallel refreshes would race, the loser would present a
 * token that had just been rotated away, and the account would be signed out
 * everywhere. One shared promise means concurrent 401s wait on the same call.
 */
function refreshSession(): Promise<boolean> {
  refreshInFlight ??= fetch(REFRESH_PATH, { method: 'POST', credentials: 'include' })
    .then((response) => response.ok)
    .catch(() => false)
    .finally(() => {
      refreshInFlight = null
    })

  return refreshInFlight
}

/**
 * Thin fetch wrapper. `credentials: 'include'` matters -- auth is an httpOnly
 * cookie, so it has to ride along on every request.
 *
 * A 401 triggers one refresh-and-retry: the access token lives 15 minutes but
 * the refresh token lives 30 days, so an expired access token should be
 * invisible rather than throwing the user back to the login form.
 */
export async function api<T>(path: string, init?: RequestInit, allowRetry = true): Promise<T> {
  const response = await fetch(path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })

  if (response.status === 401 && allowRetry && !NO_REFRESH.some((p) => path.startsWith(p))) {
    if (await refreshSession()) {
      // Retried once only: a second 401 means the session is genuinely gone.
      return api<T>(path, init, false)
    }
  }

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
