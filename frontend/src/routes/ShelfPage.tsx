import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'

import AddBooksToShelf from '@/components/AddBooksToShelf'
import { READING_STATUS_LABELS, fetchShelf, listReading, removeBookFromShelf } from '@/lib/shelves'

export default function ShelfPage() {
  const { shelfId = '' } = useParams()
  const queryClient = useQueryClient()
  const id = Number(shelfId)

  const shelf = useQuery({
    queryKey: ['shelf', id],
    queryFn: ({ signal }) => fetchShelf(id, signal),
  })

  // Status lives on the user, not the shelf, so it comes from its own endpoint
  // and is matched by book id. A shelved book often has no status at all.
  const reading = useQuery({ queryKey: ['reading'], queryFn: ({ signal }) => listReading(signal) })
  const statusByBook = new Map(reading.data?.map((entry) => [entry.book.id, entry.status]))

  const remove = useMutation({
    mutationFn: (bookId: number) => removeBookFromShelf(id, bookId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['shelf', id] })
      void queryClient.invalidateQueries({ queryKey: ['shelves'] })
    },
  })

  if (shelf.isPending) return <p className="text-neutral-500">Loading…</p>

  if (shelf.isError) {
    return (
      <div className="flex flex-col gap-4">
        <p role="alert" className="text-sm text-red-600">
          {shelf.error.message}
        </p>
        <Link to="/shelves" className="text-sm underline underline-offset-4">
          Back to shelves
        </Link>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <Link to="/shelves" className="text-sm text-neutral-500 underline underline-offset-4">
        ← Back to shelves
      </Link>

      <h2 className="text-2xl font-semibold tracking-tight">{shelf.data.name}</h2>

      <AddBooksToShelf
        shelfId={id}
        onShelf={
          new Set(
            shelf.data.books
              .map((book) => book.hardcover_id)
              .filter((value): value is string => value !== null),
          )
        }
      />

      {shelf.data.books.length === 0 ? (
        <p className="text-sm text-neutral-500">
          Nothing here yet. Find a book in search and add it from its page.
        </p>
      ) : (
        <ul className="flex flex-col gap-4">
          {shelf.data.books.map((book) => {
            const status = statusByBook.get(book.id)
            return (
              <li key={book.id} className="flex items-start gap-3">
                <Link to={`/books/${book.hardcover_id}`} className="flex min-w-0 flex-1 gap-3">
                  {book.cover_url ? (
                    <img
                      src={book.cover_url}
                      alt=""
                      loading="lazy"
                      // Just enough to register as hovered. `relative` is
                      // load-bearing: z-index does nothing on a statically
                      // positioned element, so without it the next row would
                      // paint over the growth.
                      className="relative h-20 w-14 flex-none rounded object-cover shadow-sm transition duration-150 ease-out hover:z-10 hover:scale-115 hover:shadow-md"
                    />
                  ) : (
                    <div className="h-20 w-14 flex-none rounded bg-neutral-200 dark:bg-neutral-800" />
                  )}
                  <div className="min-w-0">
                    <p className="truncate font-medium">{book.title}</p>
                    <p className="truncate text-sm text-neutral-500">
                      {book.authors.length > 0 ? book.authors.join(', ') : 'Unknown author'}
                    </p>
                    {status && (
                      <p className="mt-0.5 text-xs text-neutral-400">
                        {READING_STATUS_LABELS[status]}
                      </p>
                    )}
                  </div>
                </Link>
                <button
                  type="button"
                  onClick={() => remove.mutate(book.id)}
                  disabled={remove.isPending}
                  className="flex-none text-sm text-neutral-500 underline underline-offset-4 disabled:opacity-50"
                >
                  Remove
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
