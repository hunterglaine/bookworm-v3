import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'

import { fetchShelf, removeBookFromShelf } from '@/lib/shelves'

export default function ShelfPage() {
  const { shelfId = '' } = useParams()
  const queryClient = useQueryClient()
  const id = Number(shelfId)

  const shelf = useQuery({
    queryKey: ['shelf', id],
    queryFn: ({ signal }) => fetchShelf(id, signal),
  })

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

      {shelf.data.books.length === 0 ? (
        <p className="text-sm text-neutral-500">
          Nothing here yet. Find a book in search and add it from its page.
        </p>
      ) : (
        <ul className="flex flex-col gap-4">
          {shelf.data.books.map((book) => (
            <li key={book.id} className="flex items-start gap-3">
              <Link to={`/books/${book.hardcover_id}`} className="flex min-w-0 flex-1 gap-3">
                {book.cover_url ? (
                  <img
                    src={book.cover_url}
                    alt=""
                    loading="lazy"
                    className="h-20 w-14 flex-none rounded object-cover"
                  />
                ) : (
                  <div className="h-20 w-14 flex-none rounded bg-neutral-200 dark:bg-neutral-800" />
                )}
                <div className="min-w-0">
                  <p className="truncate font-medium">{book.title}</p>
                  <p className="truncate text-sm text-neutral-500">
                    {book.authors.length > 0 ? book.authors.join(', ') : 'Unknown author'}
                  </p>
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
          ))}
        </ul>
      )}
    </div>
  )
}
