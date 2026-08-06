export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
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
    throw new ApiError(`Request to ${path} failed`, response.status)
  }

  return response.json() as Promise<T>
}
