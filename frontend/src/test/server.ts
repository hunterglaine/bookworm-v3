import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

import { USER, shelf } from './fixtures'

/** Defaults for a signed-in user with one shelf. Individual tests override
 *  with server.use(...) rather than reaching for a different server. */
export const handlers = [
  http.get('*/api/v1/auth/me', () => HttpResponse.json(USER)),
  http.post('*/api/v1/auth/refresh', () => HttpResponse.json(USER)),
  http.get('*/api/v1/shelves', () => HttpResponse.json([shelf()])),
  http.get('*/api/v1/me/books', () => HttpResponse.json([])),
]

export const server = setupServer(...handlers)
