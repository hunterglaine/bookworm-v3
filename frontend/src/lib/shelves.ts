import { api } from './api'

export type ReadingStatus = 'want_to_read' | 'reading' | 'read' | 'dnf'

export const READING_STATUS_LABELS: Record<ReadingStatus, string> = {
  want_to_read: 'Want to read',
  reading: 'Reading',
  read: 'Read',
  dnf: 'Did not finish',
}

export interface Shelf {
  id: number
  name: string
  slug: string
  book_count: number
  /** Only meaningful when listShelves was given a book id; false otherwise. */
  contains_book: boolean
}

export interface BookSummary {
  id: number
  hardcover_id: string | null
  title: string
  subtitle: string | null
  authors: string[]
  cover_url: string | null
  /** Dominant colour of the cover; drives the generated spine. */
  cover_color: string | null
  page_count: number | null
}

export interface BookshelfShelf {
  id: number
  name: string
  slug: string
  books: BookSummary[]
}

export interface ShelfDetail {
  id: number
  name: string
  slug: string
  books: BookSummary[]
}

export interface ReadingEntry {
  status: ReadingStatus
  rating: number | null
  review: string | null
  started_at: string | null
  finished_at: string | null
  updated_at: string
  book: BookSummary
}

export function listShelves(
  options: { containsHardcoverId?: string; signal?: AbortSignal } = {},
): Promise<Shelf[]> {
  const query = options.containsHardcoverId
    ? `?contains=${encodeURIComponent(options.containsHardcoverId)}`
    : ''
  return api<Shelf[]>(`/api/v1/shelves${query}`, { signal: options.signal })
}

export function createShelf(name: string): Promise<Shelf> {
  return api<Shelf>('/api/v1/shelves', { method: 'POST', body: JSON.stringify({ name }) })
}

export function renameShelf(shelfId: number, name: string): Promise<Shelf> {
  return api<Shelf>(`/api/v1/shelves/${shelfId}`, {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  })
}

export function deleteShelf(shelfId: number): Promise<void> {
  return api<void>(`/api/v1/shelves/${shelfId}`, { method: 'DELETE' })
}

export function fetchShelf(shelfId: number, signal?: AbortSignal): Promise<ShelfDetail> {
  return api<ShelfDetail>(`/api/v1/shelves/${shelfId}`, { signal })
}

export function fetchBookshelf(signal?: AbortSignal): Promise<BookshelfShelf[]> {
  return api<BookshelfShelf[]>('/api/v1/shelves/bookshelf', { signal })
}

/** Replaces a shelf's contents and their order. A cross-shelf drag is two of
 *  these, so each call fully describes one shelf. */
export function setShelfContents(shelfId: number, bookIds: number[]): Promise<ShelfDetail> {
  return api<ShelfDetail>(`/api/v1/shelves/${shelfId}/books`, {
    method: 'PUT',
    body: JSON.stringify({ book_ids: bookIds }),
  })
}

export function addBookToShelf(shelfId: number, hardcoverId: string): Promise<BookSummary> {
  return api<BookSummary>(`/api/v1/shelves/${shelfId}/books`, {
    method: 'POST',
    body: JSON.stringify({ hardcover_id: hardcoverId }),
  })
}

export function removeBookFromShelf(shelfId: number, bookId: number): Promise<void> {
  return api<void>(`/api/v1/shelves/${shelfId}/books/${bookId}`, { method: 'DELETE' })
}

export function listReading(signal?: AbortSignal): Promise<ReadingEntry[]> {
  return api<ReadingEntry[]>('/api/v1/me/books', { signal })
}

export function setReadingStatus(
  hardcoverId: string,
  update: { status?: ReadingStatus; rating?: number | null; review?: string | null },
): Promise<ReadingEntry> {
  return api<ReadingEntry>(`/api/v1/me/books/${hardcoverId}`, {
    method: 'PUT',
    body: JSON.stringify(update),
  })
}

export function clearReadingStatus(hardcoverId: string): Promise<void> {
  return api<void>(`/api/v1/me/books/${hardcoverId}`, { method: 'DELETE' })
}
