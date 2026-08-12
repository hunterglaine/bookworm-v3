import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'

import { type BookSearchResult, searchBooks } from '@/lib/books'
import { MIN_QUERY_LENGTH, SEARCH_DEBOUNCE_MS, useDebounced } from '@/lib/useDebounced'

function Stars({ rating, count }: { rating: number | null; count: number }) {
  if (rating === null) {
    return <span className="text-neutral-400">unrated</span>
  }
  return (
    <span>
      ★ {rating.toFixed(2)} <span className="text-neutral-400">({count.toLocaleString()})</span>
    </span>
  )
}

function BookCard({ book }: { book: BookSearchResult }) {
  return (
    <li>
      <Link
        to={`/books/${book.hardcover_id}`}
        className="flex gap-3 rounded-md p-2 -m-2 hover:bg-neutral-100 dark:hover:bg-neutral-900"
      >
        {book.cover_url ? (
          <img
            src={book.cover_url}
            alt=""
            loading="lazy"
            className="h-24 w-16 flex-none rounded object-cover"
          />
        ) : (
          <div className="h-24 w-16 flex-none rounded bg-neutral-200 dark:bg-neutral-800" />
        )}

        <div className="min-w-0">
          <p className="truncate font-medium">{book.title}</p>
          <p className="truncate text-sm text-neutral-500">
            {book.authors.length > 0 ? book.authors.join(', ') : 'Unknown author'}
          </p>
          <p className="mt-1 text-sm">
            <Stars rating={book.rating} count={book.ratings_count} />
            {book.release_year !== null && (
              <span className="text-neutral-400"> · {book.release_year}</span>
            )}
            {book.page_count !== null && (
              <span className="text-neutral-400"> · {book.page_count}pp</span>
            )}
          </p>
        </div>
      </Link>
    </li>
  )
}

export default function BookSearch() {
  const [input, setInput] = useState('')
  const query = useDebounced(input.trim(), SEARCH_DEBOUNCE_MS)
  const enabled = query.length >= MIN_QUERY_LENGTH

  const { data, isFetching, isError, error } = useQuery({
    queryKey: ['bookSearch', query],
    queryFn: ({ signal }) => searchBooks(query, signal),
    enabled,
  })

  return (
    <section className="flex flex-col gap-4">
      <input
        type="search"
        value={input}
        onChange={(event) => setInput(event.target.value)}
        placeholder="Search by title or author…"
        aria-label="Search books"
        className="rounded-md border border-neutral-300 px-3 py-2 dark:border-neutral-700 dark:bg-neutral-900"
      />

      {isError && (
        <p role="alert" className="text-sm text-red-600">
          {error.message}
        </p>
      )}

      {isFetching && <p className="text-sm text-neutral-500">Searching…</p>}

      {data && !isFetching && data.results.length === 0 && (
        <p className="text-sm text-neutral-500">Nothing found for “{data.query}”.</p>
      )}

      {data && data.results.length > 0 && (
        <ul className="flex flex-col gap-4">
          {data.results.map((book) => (
            <BookCard key={book.hardcover_id} book={book} />
          ))}
        </ul>
      )}
    </section>
  )
}
