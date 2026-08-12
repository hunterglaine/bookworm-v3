import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { Link } from 'react-router'

import {
  READING_STATUS_LABELS,
  type ReadingStatus,
  addBookToShelf,
  clearReadingStatus,
  createShelf,
  listReading,
  listShelves,
  setReadingStatus,
} from '@/lib/shelves'

const STATUSES = Object.keys(READING_STATUS_LABELS) as ReadingStatus[]

/**
 * Shelving and reading status, side by side but not wired together.
 *
 * Adding to "Owned" says nothing about whether you have read it, so the two
 * controls stay independent -- that separation is the whole reason shelves and
 * reading status are different tables.
 *
 * Shelving goes through a modal rather than a menu because it writes to the
 * database: a deliberate confirm step beats a control that commits the moment
 * it changes. Status is a small fixed set shown in full, so the current value
 * is legible without opening anything.
 *
 * <dialog> is native on purpose -- focus trapping, Escape to close, and the
 * backdrop all come for free rather than from a library.
 */
export default function BookActions({ hardcoverId }: { hardcoverId: string }) {
  const queryClient = useQueryClient()
  const dialog = useRef<HTMLDialogElement>(null)
  const [chosen, setChosen] = useState<number | null>(null)
  const [newShelfName, setNewShelfName] = useState('')
  const [justAdded, setJustAdded] = useState<string | null>(null)

  // Asking which shelves already hold this book costs no extra request -- the
  // dialog needs the shelf list anyway, and the answer rides along with it.
  const shelves = useQuery({
    queryKey: ['shelves', { contains: hardcoverId }],
    queryFn: ({ signal }) => listShelves({ containsHardcoverId: hardcoverId, signal }),
  })
  const reading = useQuery({ queryKey: ['reading'], queryFn: ({ signal }) => listReading(signal) })

  const entry = reading.data?.find((item) => item.book.hardcover_id === hardcoverId)

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['reading'] })
    void queryClient.invalidateQueries({ queryKey: ['shelves'] })
    void queryClient.invalidateQueries({ queryKey: ['shelf'] })
  }

  const closeDialog = () => {
    dialog.current?.close()
    setChosen(null)
    setNewShelfName('')
  }

  const shelve = useMutation({
    mutationFn: (shelfId: number) => addBookToShelf(shelfId, hardcoverId),
    onSuccess: (_result, shelfId) => {
      setJustAdded(shelves.data?.find((s) => s.id === shelfId)?.name ?? null)
      closeDialog()
      invalidate()
    },
  })

  const createAndShelve = useMutation({
    mutationFn: async (name: string) => {
      const shelf = await createShelf(name)
      await addBookToShelf(shelf.id, hardcoverId)
      return shelf
    },
    onSuccess: (shelf) => {
      setJustAdded(shelf.name)
      closeDialog()
      invalidate()
    },
  })

  const status = useMutation({
    // Both branches resolve to void: clearing is a delete, anything else a put,
    // and the caller only cares that it finished.
    mutationFn: async (next: ReadingStatus | null): Promise<void> => {
      if (next === null) {
        await clearReadingStatus(hardcoverId)
      } else {
        await setReadingStatus(hardcoverId, { status: next })
      }
    },
    onSuccess: invalidate,
  })

  const busy = shelve.isPending || createAndShelve.isPending || status.isPending
  // The dialog can create a shelf, so an empty list is no longer a dead end.
  const shelfCount = shelves.data?.length ?? 0

  return (
    <section className="flex flex-col gap-4 rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            setJustAdded(null)
            dialog.current?.showModal()
          }}
          className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm hover:bg-neutral-100 disabled:opacity-50 dark:border-neutral-700 dark:hover:bg-neutral-900"
        >
          Add to shelf
        </button>

        {shelfCount > 0 && (
          <Link to="/shelves" className="text-sm text-neutral-500 underline underline-offset-4">
            Manage shelves
          </Link>
        )}

        {justAdded && <span className="text-sm text-neutral-500">Added to {justAdded}.</span>}
      </div>

      <dialog
        ref={dialog}
        aria-labelledby="add-to-shelf-heading"
        onClose={() => setChosen(null)}
        className="m-auto w-80 max-w-[90vw] rounded-lg border border-neutral-200 bg-white p-0 text-neutral-900 backdrop:bg-black/40 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100"
      >
        <form
          method="dialog"
          className="flex flex-col gap-4 p-4"
          onSubmit={(event) => {
            // The dialog would close on its own; the mutation needs to run and
            // close it only once the write succeeded.
            event.preventDefault()
            if (chosen !== null) shelve.mutate(chosen)
          }}
        >
          <h2 id="add-to-shelf-heading" className="font-medium">
            Add to shelf
          </h2>

          <ul className="flex flex-col gap-1">
            {shelves.data?.map((shelf) => (
              <li key={shelf.id}>
                <label
                  className={
                    shelf.contains_book
                      ? 'flex items-center gap-2 rounded px-2 py-1.5 text-sm text-neutral-400'
                      : 'flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-neutral-100 dark:hover:bg-neutral-800'
                  }
                >
                  <input
                    type="radio"
                    name="shelf"
                    value={shelf.id}
                    // Already on it: nothing to add, so the row states the fact
                    // rather than offering a no-op that silently succeeds.
                    disabled={shelf.contains_book}
                    checked={chosen === shelf.id}
                    onChange={() => setChosen(shelf.id)}
                  />
                  <span className="flex-1">{shelf.name}</span>
                  {shelf.contains_book && <span className="text-xs">✓ already on</span>}
                </label>
              </li>
            ))}
          </ul>

          <div className="flex flex-col gap-2 border-t border-neutral-200 pt-3 dark:border-neutral-700">
            <label htmlFor="new-shelf" className="text-sm text-neutral-500">
              Or create a new shelf
            </label>
            <div className="flex gap-2">
              <input
                id="new-shelf"
                value={newShelfName}
                maxLength={100}
                placeholder="Shelf name"
                onChange={(event) => {
                  setNewShelfName(event.target.value)
                  // Typing a new name and having a radio still selected is
                  // ambiguous about which one Add would use.
                  if (event.target.value) setChosen(null)
                }}
                className="min-w-0 flex-1 rounded-md border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800"
              />
              <button
                type="button"
                disabled={!newShelfName.trim() || createAndShelve.isPending}
                onClick={() => createAndShelve.mutate(newShelfName.trim())}
                className="flex-none rounded-md border border-neutral-300 px-3 py-1 text-sm disabled:opacity-50 dark:border-neutral-700"
              >
                {createAndShelve.isPending ? 'Creating…' : 'Create & add'}
              </button>
            </div>
          </div>

          {(shelve.isError || createAndShelve.isError) && (
            <p role="alert" className="text-sm text-red-600">
              {(shelve.error ?? createAndShelve.error)?.message}
            </p>
          )}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={closeDialog}
              className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm dark:border-neutral-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={chosen === null || shelve.isPending}
              className="rounded-md bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900"
            >
              {shelve.isPending ? 'Adding…' : 'Add'}
            </button>
          </div>
        </form>
      </dialog>

      <div className="flex flex-col gap-2">
        <span className="text-sm text-neutral-500">Reading status</span>
        <div className="flex flex-wrap gap-1.5">
          {STATUSES.map((value) => {
            const active = entry?.status === value
            return (
              <button
                key={value}
                type="button"
                aria-pressed={active}
                disabled={busy}
                onClick={() => status.mutate(active ? null : value)}
                className={
                  active
                    ? 'rounded-md bg-neutral-900 px-3 py-1.5 text-sm text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900'
                    : 'rounded-md border border-neutral-300 px-3 py-1.5 text-sm hover:bg-neutral-100 disabled:opacity-50 dark:border-neutral-700 dark:hover:bg-neutral-900'
                }
              >
                {READING_STATUS_LABELS[value]}
              </button>
            )
          })}
        </div>
        {entry && (
          <p className="text-sm text-neutral-500">Click the selected status again to clear it.</p>
        )}
      </div>

      {status.isError && (
        <p role="alert" className="text-sm text-red-600">
          {status.error.message}
        </p>
      )}
    </section>
  )
}
