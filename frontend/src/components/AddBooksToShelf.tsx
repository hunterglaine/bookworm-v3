import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { searchBooks } from '@/lib/books'
import { addBookToShelf } from '@/lib/shelves'
import { MIN_QUERY_LENGTH, SEARCH_DEBOUNCE_MS, useDebounced } from '@/lib/useDebounced'

/**
 * Search and add, without leaving the shelf.
 *
 * Adding used to mean going to search, opening a book, and picking the shelf
 * from a dialog -- three screens away from the shelf you were looking at.
 */
export default function AddBooksToShelf({
  shelfId,
  onShelf,
}: {
  shelfId: number
  /** Hardcover ids already on this shelf, so results can say so. */
  onShelf: Set<string>
}) {
  const queryClient = useQueryClient()
  const [input, setInput] = useState('')
  const [added, setAdded] = useState<string | null>(null)

  const query = useDebounced(input.trim(), SEARCH_DEBOUNCE_MS)
  const enabled = query.length >= MIN_QUERY_LENGTH

  const results = useQuery({
    queryKey: ['bookSearch', query],
    queryFn: ({ signal }) => searchBooks(query, signal),
    enabled,
  })

  const add = useMutation({
    mutationFn: (hardcoverId: string) => addBookToShelf(shelfId, hardcoverId),
    onSuccess: (book) => {
      setAdded(book.title)
      void queryClient.invalidateQueries({ queryKey: ['shelf', shelfId] })
      void queryClient.invalidateQueries({ queryKey: ['shelves'] })
      void queryClient.invalidateQueries({ queryKey: ['bookshelf'] })
    },
  })

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <label htmlFor="add-books" className="text-sm font-medium">
        Add books to this shelf
      </label>
      <input
        id="add-books"
        type="search"
        value={input}
        onChange={(event) => {
          setInput(event.target.value)
          setAdded(null)
        }}
        placeholder="Search by title or author…"
        className="rounded-md border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900"
      />

      {added && <p className="text-sm text-neutral-500">Added {added}.</p>}

      {add.isError && (
        <p role="alert" className="text-sm text-red-600">
          {add.error.message}
        </p>
      )}

      {enabled && results.isFetching && <p className="text-sm text-neutral-500">Searching…</p>}

      {results.data && results.data.results.length === 0 && !results.isFetching && (
        <p className="text-sm text-neutral-500">Nothing found for “{results.data.query}”.</p>
      )}

      {results.data && results.data.results.length > 0 && (
        <ul className="flex flex-col gap-2">
          {results.data.results.map((book) => {
            const already = onShelf.has(book.hardcover_id)
            return (
              <li key={book.hardcover_id} className="flex items-center gap-3">
                {book.cover_url ? (
                  <img
                    src={book.cover_url}
                    alt=""
                    loading="lazy"
                    className="h-14 w-10 flex-none rounded object-cover"
                  />
                ) : (
                  <div className="h-14 w-10 flex-none rounded bg-neutral-200 dark:bg-neutral-800" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{book.title}</p>
                  <p className="truncate text-xs text-neutral-500">
                    {book.authors.length > 0 ? book.authors.join(', ') : 'Unknown author'}
                  </p>
                </div>
                <button
                  type="button"
                  disabled={already || add.isPending}
                  onClick={() => add.mutate(book.hardcover_id)}
                  className="flex-none rounded-md border border-neutral-300 px-3 py-1 text-sm disabled:opacity-50 dark:border-neutral-700"
                >
                  {already ? 'On shelf' : 'Add'}
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
