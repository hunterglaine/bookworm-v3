import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router'

import { inkOn, spineColor } from '@/lib/color'
import type { BookSummary } from '@/lib/shelves'

/**
 * A book stood spine-out, which shows its cover on hover.
 *
 * Spines are generated, not fetched -- no provider supplies spine artwork. The
 * colour is the cover's dominant colour, which is what stops a shelf reading as
 * thirty identical grey rectangles. Spine-out is also what makes one row per
 * shelf work: a row fits maybe six covers but thirty spines, which is exactly
 * why real shelves store books this way.
 *
 * The cover renders in a portal rather than inside the row, for two reasons
 * that both come down to containment:
 *
 *  - The shelf row scrolls horizontally, and `overflow-x: auto` forces the
 *    other axis to a non-visible value too. A cover wider than its spine is
 *    clipped by that container, and no z-index escapes a clip.
 *  - The drag library puts a `transform` on each draggable, which creates a
 *    stacking context. Inside one, a child's z-index cannot rise above a later
 *    sibling's context, so the following spines painted over the cover.
 *
 * A portal sidesteps both: the cover is a child of <body>, positioned to the
 * spine's measured rect.
 */
const MIN_WIDTH = 26
const MAX_WIDTH = 46
const HEIGHT = 168
const COVER_WIDTH = 112
const VIEWPORT_MARGIN = 8

function spineWidth(pageCount: number | null): number {
  if (!pageCount) return 32
  const scaled = MIN_WIDTH + (pageCount / 900) * (MAX_WIDTH - MIN_WIDTH)
  return Math.round(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, scaled)))
}

export default function BookSpine({
  book,
  dragging = false,
}: {
  book: BookSummary
  dragging?: boolean
}) {
  const [rect, setRect] = useState<DOMRect | null>(null)
  const background = spineColor(book.cover_color)
  const ink = inkOn(background)
  const width = spineWidth(book.page_count)
  const author = book.authors[0] ?? ''

  // A measured rect goes stale the moment anything moves, and the cover is
  // fixed-position so it would hang in the wrong place.
  useEffect(() => {
    if (!rect) return
    const dismiss = () => setRect(null)
    window.addEventListener('scroll', dismiss, true)
    window.addEventListener('resize', dismiss)
    return () => {
      window.removeEventListener('scroll', dismiss, true)
      window.removeEventListener('resize', dismiss)
    }
  }, [rect])

  useEffect(() => {
    if (dragging) setRect(null)
  }, [dragging])

  const open = rect !== null && !dragging

  // Centre on the spine, then keep the whole cover on screen -- otherwise the
  // first and last books on a shelf get their covers cut off by the edge.
  const left = rect
    ? Math.min(
        Math.max(rect.left + rect.width / 2 - COVER_WIDTH / 2, VIEWPORT_MARGIN),
        window.innerWidth - COVER_WIDTH - VIEWPORT_MARGIN,
      )
    : 0

  return (
    <>
      <Link
        to={`/books/${book.hardcover_id}`}
        title={`${book.title}${author ? ` — ${author}` : ''}`}
        aria-label={`${book.title}${author ? ` by ${author}` : ''}`}
        onMouseEnter={(event) => {
          if (!dragging) setRect(event.currentTarget.getBoundingClientRect())
        }}
        onMouseLeave={() => setRect(null)}
        onFocus={(event) => setRect(event.currentTarget.getBoundingClientRect())}
        onBlur={() => setRect(null)}
        className="relative block shrink-0 rounded-[2px] transition-transform duration-200 ease-out"
        style={{
          width,
          height: HEIGHT,
          background,
          color: ink,
          // Lifts slightly as the cover appears, so the book reads as coming
          // off the shelf rather than the cover simply materialising.
          transform: open ? 'translateY(-6px)' : undefined,
        }}
      >
        <span className="absolute inset-0 flex items-center justify-center overflow-hidden">
          {/* Rotated so the title reads bottom-to-top, as on a real spine. */}
          <span
            className="max-h-[150px] overflow-hidden text-[11px] leading-tight font-medium whitespace-nowrap"
            style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
          >
            {book.title}
          </span>
        </span>
        {/* A hint of the page block along one edge. */}
        <span className="pointer-events-none absolute inset-y-0 right-0 w-[3px] bg-white/25" />
      </Link>

      {open &&
        rect &&
        createPortal(
          <div
            aria-hidden
            className="pointer-events-none fixed z-50 overflow-hidden rounded-sm shadow-2xl ring-1 ring-black/10"
            style={{
              left,
              top: rect.bottom - HEIGHT - 6,
              width: COVER_WIDTH,
              height: HEIGHT,
            }}
          >
            {book.cover_url ? (
              <img src={book.cover_url} alt="" className="h-full w-full object-cover" />
            ) : (
              <div
                className="flex h-full w-full flex-col justify-end gap-1 p-2 text-[11px] leading-tight"
                style={{ background, color: ink }}
              >
                <span className="font-medium">{book.title}</span>
                <span className="opacity-80">{author}</span>
              </div>
            )}
          </div>,
          document.body,
        )}
    </>
  )
}
