import { ApiError, api } from './api'

export interface User {
  id: number
  email: string
  display_name: string | null
  is_active: boolean
}

export interface Credentials {
  email: string
  password: string
  display_name?: string
}

export function register(body: Credentials): Promise<User> {
  return api<User>('/api/v1/auth/register', { method: 'POST', body: JSON.stringify(body) })
}

export function login(body: Credentials): Promise<User> {
  return api<User>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify(body) })
}

export function logout(): Promise<void> {
  return api<void>('/api/v1/auth/logout', { method: 'POST' })
}

/**
 * Null when signed out, rather than throwing.
 *
 * A 401 here is the expected answer to "is anyone signed in", not a failure --
 * treating it as an error would make every signed-out page load look broken and
 * would trip the query client's retry logic.
 */
export async function fetchCurrentUser(): Promise<User | null> {
  try {
    return await api<User>('/api/v1/auth/me')
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null
    throw error
  }
}
