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

export interface RatingBucket {
  rating: number
  count: number
}

export interface BookDetail {
  hardcover_id: string
  title: string
  subtitle: string | null
  description: string | null
  page_count: number | null
  rating: number | null
  ratings_count: number
  /** Low to high. Empty when the provider has no breakdown. */
  ratings_distribution: RatingBucket[]
  release_date: string | null
  users_read_count: number
  cover_url: string | null
  authors: string[]
  genres: string[]
  moods: string[]
  isbns: string[]
}

export function searchBooks(query: string, signal?: AbortSignal): Promise<BookSearchResponse> {
  return api<BookSearchResponse>(`/api/v1/books/search?q=${encodeURIComponent(query)}`, { signal })
}

export function fetchBook(hardcoverId: string, signal?: AbortSignal): Promise<BookDetail> {
  return api<BookDetail>(`/api/v1/books/${encodeURIComponent(hardcoverId)}`, { signal })
}
