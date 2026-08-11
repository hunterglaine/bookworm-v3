import { api } from './api'

export interface BookSearchResult {
  hardcover_id: string
  title: string
  authors: string[]
  cover_url: string | null
  page_count: number | null
  /** Null means unrated, not a score of zero. */
  rating: number | null
  ratings_count: number
  release_year: number | null
  genres: string[]
}

export interface BookSearchResponse {
  query: string
  results: BookSearchResult[]
}

export function searchBooks(query: string, signal?: AbortSignal): Promise<BookSearchResponse> {
  return api<BookSearchResponse>(`/api/v1/books/search?q=${encodeURIComponent(query)}`, { signal })
}
