import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { ApiError, api } from './api'
import { server } from '../test/server'

/**
 * These pin the bug where a tab left idle for 15 minutes started 401ing while
 * holding a perfectly good 30-day refresh cookie, and the far worse bug the
 * obvious fix would have introduced.
 */
describe('api', () => {
  it('returns the body on success', async () => {
    server.use(http.get('*/api/v1/thing', () => HttpResponse.json({ ok: true })))
    await expect(api<{ ok: boolean }>('/api/v1/thing')).resolves.toEqual({ ok: true })
  })

  it('surfaces the server detail rather than a generic message', async () => {
    server.use(
      http.post('*/api/v1/auth/register', () =>
        HttpResponse.json({ detail: 'Email already registered' }, { status: 409 }),
      ),
    )

    await expect(api('/api/v1/auth/register', { method: 'POST' })).rejects.toThrow(
      'Email already registered',
    )
  })

  it('surfaces the first message from a 422 validation list', async () => {
    server.use(
      http.post('*/api/v1/thing', () =>
        HttpResponse.json({ detail: [{ msg: 'String too short' }] }, { status: 422 }),
      ),
    )

    await expect(api('/api/v1/thing', { method: 'POST' })).rejects.toThrow('String too short')
  })

  it('treats 204 as an empty body rather than trying to parse it', async () => {
    server.use(http.post('*/api/v1/auth/logout', () => new HttpResponse(null, { status: 204 })))
    await expect(api('/api/v1/auth/logout', { method: 'POST' })).resolves.toBeUndefined()
  })

  it('refreshes and retries once when the access token has expired', async () => {
    let attempts = 0
    let refreshes = 0

    server.use(
      http.get('*/api/v1/shelves', () => {
        attempts += 1
        // Expired on the first call, fine once the token has been refreshed.
        return attempts === 1
          ? HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 })
          : HttpResponse.json([])
      }),
      http.post('*/api/v1/auth/refresh', () => {
        refreshes += 1
        return HttpResponse.json({ ok: true })
      }),
    )

    await expect(api('/api/v1/shelves')).resolves.toEqual([])
    expect(attempts).toBe(2)
    expect(refreshes).toBe(1)
  })

  it('gives up after one retry rather than looping', async () => {
    let refreshes = 0
    server.use(
      http.get('*/api/v1/shelves', () =>
        HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 }),
      ),
      http.post('*/api/v1/auth/refresh', () => {
        refreshes += 1
        return HttpResponse.json({ ok: true })
      }),
    )

    await expect(api('/api/v1/shelves')).rejects.toBeInstanceOf(ApiError)
    expect(refreshes).toBe(1)
  })

  it('refreshes only once for concurrent 401s', async () => {
    // The property that matters most here. Refresh tokens rotate, and the
    // server treats a replayed rotated token as theft by revoking every
    // session. If each of these requests refreshed independently, the losers
    // would present an already-rotated token and sign the account out
    // everywhere -- worse than the expiry bug this fixes.
    let refreshes = 0
    const seen: string[] = []

    server.use(
      http.get('*/api/v1/:resource', ({ params }) => {
        const resource = String(params.resource)
        if (!seen.includes(resource)) {
          seen.push(resource)
          return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 })
        }
        return HttpResponse.json({ resource })
      }),
      http.post('*/api/v1/auth/refresh', async () => {
        refreshes += 1
        // A real refresh is not instantaneous; overlap is the whole point.
        await new Promise((resolve) => setTimeout(resolve, 10))
        return HttpResponse.json({ ok: true })
      }),
    )

    await Promise.all([api('/api/v1/shelves'), api('/api/v1/books'), api('/api/v1/authors')])

    expect(refreshes).toBe(1)
  })

  it('does not try to refresh when the credentials were simply wrong', async () => {
    // A 401 from login means bad password. Refreshing would be pointless, and
    // on /auth/refresh itself it would recurse.
    let refreshes = 0
    server.use(
      http.post('*/api/v1/auth/login', () =>
        HttpResponse.json({ detail: 'Incorrect email or password' }, { status: 401 }),
      ),
      http.post('*/api/v1/auth/refresh', () => {
        refreshes += 1
        return HttpResponse.json({ ok: true })
      }),
    )

    await expect(api('/api/v1/auth/login', { method: 'POST' })).rejects.toThrow('Incorrect email')
    expect(refreshes).toBe(0)
  })

  it('reports the original failure when the refresh itself fails', async () => {
    server.use(
      http.get('*/api/v1/shelves', () =>
        HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 }),
      ),
      http.post('*/api/v1/auth/refresh', () => new HttpResponse(null, { status: 401 })),
    )

    await expect(api('/api/v1/shelves')).rejects.toMatchObject({ status: 401 })
  })

  it('sends cookies, since auth is an httpOnly cookie', async () => {
    const spy = vi.spyOn(globalThis, 'fetch')
    server.use(http.get('*/api/v1/thing', () => HttpResponse.json({})))

    await api('/api/v1/thing')

    expect(spy.mock.calls[0]?.[1]).toMatchObject({ credentials: 'include' })
  })
})
