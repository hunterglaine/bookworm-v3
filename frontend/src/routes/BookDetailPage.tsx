import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'

import BookActions from '@/components/BookActions'
import RatingDistribution from '@/components/RatingDistribution'
import { ApiError } from '@/lib/api'
import { fetchBook } from '@/lib/books'

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-neutral-500">{label}</dt>
      <dd className="text-sm">{value}</dd>
    </div>
  )
}

export default function BookDetailPage() {
  const { hardcoverId = '' } = useParams()

  const {
    data: book,
    isPending,
    isError,
    error,
  } = useQuery({
    queryKey: ['book', hardcoverId],
    queryFn: ({ signal }) => fetchBook(hardcoverId, signal),
  })

  if (isPending) {
    return <p className="text-neutral-500">Loading…</p>
  }

  if (isError) {
    const missing = error instanceof ApiError && error.status === 404
    return (
      <div className="flex flex-col gap-4">
        <p role="alert" className="text-sm text-red-600">
          {missing ? 'That book could not be found.' : error.message}
        </p>
        <Link to="/" className="text-sm underline underline-offset-4">
          Back to search
        </Link>
      </div>
    )
  }

  return (
    <article className="flex flex-col gap-6">
      <Link to="/" className="text-sm text-neutral-500 underline underline-offset-4">
        ← Back to search
      </Link>

      <div className="flex gap-5">
        {book.cover_url ? (
          <img
            src={book.cover_url}
            alt=""
            className="h-48 w-32 flex-none rounded object-cover shadow-sm"
          />
        ) : (
          <div className="h-48 w-32 flex-none rounded bg-neutral-200 dark:bg-neutral-800" />
        )}

        <div className="min-w-0 flex flex-col gap-2">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{book.title}</h1>
            {book.subtitle && <p className="text-neutral-500">{book.subtitle}</p>}
          </div>
          <p className="text-neutral-600 dark:text-neutral-400">
            {book.authors.length > 0 ? book.authors.join(', ') : 'Unknown author'}
          </p>

          <p className="text-lg">
            {book.rating === null ? (
              <span className="text-neutral-400">Not yet rated</span>
            ) : (
              <>
                <span className="font-medium">★ {book.rating.toFixed(2)}</span>{' '}
                <span className="text-sm text-neutral-500">
                  from {book.ratings_count.toLocaleString()} ratings
                </span>
              </>
            )}
          </p>

          {book.genres.length > 0 && (
            <ul className="flex flex-wrap gap-1.5">
              {book.genres.slice(0, 6).map((genre) => (
                <li
                  key={genre}
                  className="rounded-full border border-neutral-300 px-2 py-0.5 text-xs text-neutral-600 dark:border-neutral-700 dark:text-neutral-400"
                >
                  {genre}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <BookActions hardcoverId={book.hardcover_id} />

      {book.ratings_count > 0 && (
        <RatingDistribution buckets={book.ratings_distribution} total={book.ratings_count} />
      )}

      {book.description && (
        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-medium text-neutral-500">Description</h2>
          <p className="whitespace-pre-line leading-relaxed">{book.description}</p>
        </section>
      )}

      <dl className="grid grid-cols-2 gap-4 border-t border-neutral-200 pt-4 sm:grid-cols-4 dark:border-neutral-800">
        {book.page_count !== null && (
          <Meta label="Pages" value={book.page_count.toLocaleString()} />
        )}
        {book.release_date && <Meta label="Published" value={book.release_date} />}
        {book.users_read_count > 0 && (
          <Meta label="Readers" value={book.users_read_count.toLocaleString()} />
        )}
        {book.isbns[0] && <Meta label="ISBN" value={book.isbns[0]} />}
      </dl>
    </article>
  )
}
