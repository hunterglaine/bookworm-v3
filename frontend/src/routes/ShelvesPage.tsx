import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'

import {
  READING_STATUS_LABELS,
  type ReadingStatus,
  createShelf,
  deleteShelf,
  listReading,
  listShelves,
  renameShelf,
} from '@/lib/shelves'

// Reading-lifecycle order rather than the enum's: what you are reading now is
// the most useful thing to see first, and abandoned books the least.
const STATUS_ORDER: ReadingStatus[] = ['reading', 'want_to_read', 'read', 'dnf']

export default function ShelvesPage() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editingName, setEditingName] = useState('')

  const shelves = useQuery({
    queryKey: ['shelves'],
    queryFn: ({ signal }) => listShelves({ signal }),
  })
  const reading = useQuery({ queryKey: ['reading'], queryFn: ({ signal }) => listReading(signal) })

  const refresh = () => void queryClient.invalidateQueries({ queryKey: ['shelves'] })

  const create = useMutation({
    mutationFn: createShelf,
    onSuccess: () => {
      setName('')
      refresh()
    },
  })

  const remove = useMutation({ mutationFn: deleteShelf, onSuccess: refresh })

  const rename = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) => renameShelf(id, name),
    onSuccess: () => {
      setEditingId(null)
      refresh()
    },
  })

  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-medium">Shelves</h2>

        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            if (name.trim()) create.mutate(name.trim())
          }}
        >
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="New shelf name"
            aria-label="New shelf name"
            maxLength={100}
            className="flex-1 rounded-md border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          />
          <button
            type="submit"
            disabled={create.isPending || !name.trim()}
            className="rounded-md bg-neutral-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900"
          >
            Create
          </button>
        </form>

        {create.isError && (
          <p role="alert" className="text-sm text-red-600">
            {create.error.message}
          </p>
        )}

        {shelves.isPending ? (
          <p className="text-sm text-neutral-500">Loading…</p>
        ) : shelves.data?.length === 0 ? (
          <p className="text-sm text-neutral-500">
            No shelves yet. Create one, then add books from search.
          </p>
        ) : (
          <ul className="flex flex-col gap-1">
            {shelves.data?.map((shelf) =>
              editingId === shelf.id ? (
                <li key={shelf.id} className="-mx-2 px-2 py-1.5">
                  <form
                    className="flex gap-2"
                    onSubmit={(event) => {
                      event.preventDefault()
                      const name = editingName.trim()
                      if (name && name !== shelf.name) rename.mutate({ id: shelf.id, name })
                      else setEditingId(null)
                    }}
                  >
                    <input
                      // Focus follows the click that opened the field. This is
                      // the case autofocus is for -- a user-initiated edit --
                      // not a grab of focus on page load.
                      autoFocus
                      value={editingName}
                      maxLength={100}
                      aria-label={`Rename ${shelf.name}`}
                      onChange={(event) => setEditingName(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Escape') setEditingId(null)
                      }}
                      className="min-w-0 flex-1 rounded-md border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
                    />
                    <button
                      type="submit"
                      disabled={rename.isPending || !editingName.trim()}
                      className="flex-none rounded-md bg-neutral-900 px-3 py-1 text-sm text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900"
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditingId(null)}
                      className="flex-none rounded-md border border-neutral-300 px-3 py-1 text-sm dark:border-neutral-700"
                    >
                      Cancel
                    </button>
                  </form>
                </li>
              ) : (
                <li
                  key={shelf.id}
                  className="flex items-center justify-between gap-3 rounded-md px-2 py-1.5 -mx-2 hover:bg-neutral-100 dark:hover:bg-neutral-900"
                >
                  <Link to={`/shelves/${shelf.id}`} className="min-w-0 flex-1">
                    <span className="font-medium">{shelf.name}</span>{' '}
                    <span className="text-sm text-neutral-500">
                      {shelf.book_count} {shelf.book_count === 1 ? 'book' : 'books'}
                    </span>
                  </Link>
                  <button
                    type="button"
                    onClick={() => {
                      setEditingId(shelf.id)
                      setEditingName(shelf.name)
                    }}
                    className="flex-none text-sm text-neutral-500 underline underline-offset-4"
                  >
                    Rename
                  </button>
                  <button
                    type="button"
                    onClick={() => remove.mutate(shelf.id)}
                    disabled={remove.isPending}
                    className="flex-none text-sm text-neutral-500 underline underline-offset-4 disabled:opacity-50"
                  >
                    Delete
                  </button>
                </li>
              ),
            )}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-3">
        {/* Not "Reading": this lists every book with any status, including ones
         * finished or abandoned. Naming it after one status made it look like
         * shelved books were showing up here regardless of theirs. */}
        <h2 className="text-lg font-medium">Books you're tracking</h2>
        <p className="text-sm text-neutral-500">
          Reading status is separate from shelves — a book can sit on several shelves and still have
          exactly one status, or none at all.
        </p>

        {reading.data?.length === 0 ? (
          <p className="text-sm text-neutral-500">
            No statuses set yet. Open a book and choose one.
          </p>
        ) : (
          <div className="flex flex-col gap-5">
            {STATUS_ORDER.map((status) => {
              const entries = reading.data?.filter((entry) => entry.status === status) ?? []
              if (entries.length === 0) return null

              return (
                <div key={status} className="flex flex-col gap-1">
                  <h3 className="text-sm font-medium text-neutral-500">
                    {READING_STATUS_LABELS[status]}{' '}
                    <span className="font-normal text-neutral-400">({entries.length})</span>
                  </h3>
                  <ul className="flex flex-col gap-1">
                    {entries.map((entry) => (
                      <li key={entry.book.id} className="flex items-baseline justify-between gap-3">
                        <Link
                          to={`/books/${entry.book.hardcover_id}`}
                          className="min-w-0 truncate underline-offset-4 hover:underline"
                        >
                          {entry.book.title}
                        </Link>
                        {entry.rating !== null && (
                          <span className="flex-none text-sm text-neutral-500">
                            ★ {entry.rating}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}
