/** Shared test data.
 *
 * Shapes mirror the API responses exactly, so a schema change breaks tests
 * rather than being papered over by hand-written objects that drifted.
 */
import type { BookSummary, BookshelfShelf, ReadingEntry, Shelf } from '@/lib/shelves'

export const USER = {
  id: 1,
  email: 'reader@example.com',
  display_name: 'Reader',
  is_active: true,
}

export function book(overrides: Partial<BookSummary> = {}): BookSummary {
  return {
    id: 1,
    hardcover_id: '175280',
    title: 'Piranesi',
    subtitle: null,
    authors: ['Susanna Clarke'],
    cover_url: 'https://example.test/piranesi.jpg',
    cover_color: '#908764',
    page_count: 245,
    ...overrides,
  }
}

export function shelf(overrides: Partial<Shelf> = {}): Shelf {
  return {
    id: 1,
    name: 'Sci-fi',
    slug: 'sci-fi',
    book_count: 1,
    contains_book: false,
    ...overrides,
  }
}

export function bookshelfShelf(overrides: Partial<BookshelfShelf> = {}): BookshelfShelf {
  return { id: 1, name: 'Sci-fi', slug: 'sci-fi', books: [book()], ...overrides }
}

export function readingEntry(overrides: Partial<ReadingEntry> = {}): ReadingEntry {
  return {
    status: 'reading',
    rating: null,
    review: null,
    started_at: null,
    finished_at: null,
    updated_at: '2026-08-12T00:00:00Z',
    book: book(),
    ...overrides,
  }
}
