import { DragDropContext, Draggable, type DropResult, Droppable } from '@hello-pangea/dnd'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'

import BookSpine from '@/components/BookSpine'
import { type BookshelfShelf, fetchBookshelf, setShelfContents } from '@/lib/shelves'

/**
 * The bookshelf: one physical shelf per named shelf, books stood spine-out.
 *
 * Drag works within a shelf (reorder) and between shelves (move). A move is two
 * writes -- the source shelf without the book, the target with it -- because
 * each call then fully describes one shelf and cannot leave the book on both or
 * on neither.
 */
export default function BookshelfPage() {
  const queryClient = useQueryClient()

  const bookshelf = useQuery({
    queryKey: ['bookshelf'],
    queryFn: ({ signal }) => fetchBookshelf(signal),
  })

  const reorder = useMutation({
    mutationFn: async (shelves: { id: number; bookIds: number[] }[]) => {
      for (const shelf of shelves) {
        await setShelfContents(shelf.id, shelf.bookIds)
      }
    },
    // The cache was already updated optimistically; refetch to reconcile
    // with what the server actually stored.
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['bookshelf'] })
      void queryClient.invalidateQueries({ queryKey: ['shelves'] })
    },
  })

  function onDragEnd(result: DropResult) {
    const { source, destination } = result
    if (!destination) return
    if (source.droppableId === destination.droppableId && source.index === destination.index) {
      return
    }

    const current = bookshelf.data
    if (!current) return

    const next: BookshelfShelf[] = current.map((shelf) => ({ ...shelf, books: [...shelf.books] }))
    const from = next.find((s) => String(s.id) === source.droppableId)
    const to = next.find((s) => String(s.id) === destination.droppableId)
    if (!from || !to) return

    const [moved] = from.books.splice(source.index, 1)
    if (!moved) return

    // A book may legitimately sit on several shelves, but not twice on one.
    if (from !== to && to.books.some((b) => b.id === moved.id)) {
      void queryClient.invalidateQueries({ queryKey: ['bookshelf'] })
      return
    }
    to.books.splice(destination.index, 0, moved)

    // Show the new arrangement immediately; the drag already felt instant.
    queryClient.setQueryData(['bookshelf'], next)

    const touched = from === to ? [to] : [from, to]
    reorder.mutate(touched.map((s) => ({ id: s.id, bookIds: s.books.map((b) => b.id) })))
  }

  if (bookshelf.isPending) {
    return <p className="text-neutral-500">Loading…</p>
  }

  if (bookshelf.isError) {
    return (
      <p role="alert" className="text-sm text-red-600">
        {bookshelf.error.message}
      </p>
    )
  }

  if (bookshelf.data.length === 0) {
    return (
      <p className="text-sm text-neutral-500">
        No shelves yet —{' '}
        <Link to="/shelves" className="underline underline-offset-4">
          create one
        </Link>
        , then add books from search.
      </p>
    )
  }

  return (
    <DragDropContext onDragEnd={onDragEnd}>
      {/* One case containing every shelf, rather than separate rows: the sides,
          top and base are what make it read as a bookcase. Shelves butt
          directly against each other, so each plank is the divider between
          one shelf and the next. */}
      <div className="bookcase flex flex-col">
        {bookshelf.data.map((shelf, shelfIndex) => (
          <section key={shelf.id} className={shelfIndex > 0 ? 'pt-1' : ''}>
            {/* The name is the link -- a separate "manage" control alongside it
                was two things pointing at the same place. Serif because this is
                the one piece of the shelf that is a label on an object rather
                than app chrome. */}
            <h2 className="px-3 pt-2">
              <Link
                to={`/shelves/${shelf.id}`}
                className="font-serif text-xl font-semibold text-neutral-700 underline-offset-4 hover:underline dark:text-neutral-200"
              >
                {shelf.name}
              </Link>
            </h2>

            <Droppable droppableId={String(shelf.id)} direction="horizontal">
              {(dropProvided, dropSnapshot) => (
                <div
                  ref={dropProvided.innerRef}
                  {...dropProvided.droppableProps}
                  className={`flex min-h-[184px] items-end gap-[3px] overflow-x-auto rounded-t-sm px-3 pt-6 transition-colors ${
                    dropSnapshot.isDraggingOver ? 'bg-neutral-200/60 dark:bg-neutral-800/60' : ''
                  }`}
                >
                  {shelf.books.length === 0 && !dropSnapshot.isDraggingOver && (
                    <span className="pb-2 text-xs text-neutral-400">
                      Empty — drag a book here, or add one from search.
                    </span>
                  )}

                  {shelf.books.map((book, index) => (
                    <Draggable key={book.id} draggableId={`${shelf.id}:${book.id}`} index={index}>
                      {(dragProvided, dragSnapshot) => (
                        <div
                          ref={dragProvided.innerRef}
                          {...dragProvided.draggableProps}
                          {...dragProvided.dragHandleProps}
                          className={dragSnapshot.isDragging ? 'z-30' : ''}
                        >
                          {/* Hover pull-out is suppressed mid-drag: a spine
                              that grows under the cursor makes drop targets
                              jump around. */}
                          <BookSpine book={book} dragging={dragSnapshot.isDragging} />
                        </div>
                      )}
                    </Draggable>
                  ))}
                  {dropProvided.placeholder}
                </div>
              )}
            </Droppable>

            {/* The plank the books stand on, and the divider to the shelf
                below. Its own element so a later pass can make it wood
                without touching the layout. */}
            <div className="shelf-plank" />
          </section>
        ))}
      </div>
    </DragDropContext>
  )
}
