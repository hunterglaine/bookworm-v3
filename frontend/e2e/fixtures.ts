import type { Page } from '@playwright/test'

/**
 * A signed-in app with a known bookshelf, without a backend.
 *
 * Auth is stubbed at /auth/me rather than driven through a real login: these
 * tests are about layout and interaction, and a real login would drag in
 * Postgres and the provider for no gain.
 */

/** A 1x1 PNG, so covers load instantly and deterministically offline. */
const PIXEL =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBASfMhVAAAAAASUVORK5CYII='

export function book(id: number, title: string, color: string) {
  return {
    id,
    hardcover_id: String(100000 + id),
    title,
    subtitle: null,
    authors: ['Susanna Clarke'],
    cover_url: PIXEL,
    cover_color: color,
    page_count: 245,
  }
}

/** Long enough to exercise the ellipsis, and varied colours for the spines. */
export const SHELVES = [
  {
    id: 1,
    name: 'Sci-fi',
    slug: 'sci-fi',
    books: [
      book(1, 'Piranesi', '#908764'),
      book(2, 'A Wizard of Earthsea and Other Very Long Titles Indeed', '#2a4d69'),
      book(3, 'Sapiens', '#e6e6df'),
      book(4, 'The Fifth Season', '#7a3b2e'),
    ],
  },
  { id: 2, name: 'Owned', slug: 'owned', books: [book(5, 'Stoner', '#4a4a48')] },
]

export async function signedInBookshelf(page: Page) {
  const shelves = structuredClone(SHELVES)

  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      json: { id: 1, email: 'reader@example.test', display_name: 'Reader', is_active: true },
    }),
  )
  await page.route('**/api/v1/health', (route) => route.fulfill({ json: { status: 'ok' } }))
  await page.route('**/api/v1/me/books', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/v1/shelves/bookshelf', (route) => route.fulfill({ json: shelves }))
  await page.route(/\/api\/v1\/shelves(\?.*)?$/, (route) =>
    route.fulfill({
      json: shelves.map((s) => ({
        id: s.id,
        name: s.name,
        slug: s.slug,
        book_count: s.books.length,
        contains_book: false,
      })),
    }),
  )

  // Reorder writes back into the in-memory shelves so a reload-free refetch
  // reflects the drag, the same as the real endpoint would.
  await page.route(/\/api\/v1\/shelves\/(\d+)\/books$/, async (route, request) => {
    if (request.method() !== 'PUT') return route.fallback()

    const shelfId = Number(/shelves\/(\d+)\/books/.exec(request.url())?.[1])
    const { book_ids: bookIds } = request.postDataJSON() as { book_ids: number[] }
    const known = new Map(shelves.flatMap((s) => s.books).map((b) => [b.id, b]))
    const target = shelves.find((s) => s.id === shelfId)
    if (target) {
      target.books = bookIds.map((id) => known.get(id)!).filter(Boolean)
    }
    await route.fulfill({ json: target ?? {} })
  })

  return shelves
}
