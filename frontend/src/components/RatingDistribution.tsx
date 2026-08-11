import type { RatingBucket } from '@/lib/books'

/**
 * How a rating breaks down, not just what it averages.
 *
 * One series, so no legend — the heading names it. Magnitude is already carried
 * by bar length, so colouring by magnitude too would encode the same thing
 * twice; every bar takes the same validated hue.
 */
export default function RatingDistribution({
  buckets,
  total,
}: {
  buckets: RatingBucket[]
  total: number
}) {
  if (buckets.length === 0) return null

  const largest = Math.max(...buckets.map((bucket) => bucket.count))
  if (largest === 0) return null

  // Descending, so 5 stars sits at the top the way readers expect.
  const ordered = [...buckets].sort((a, b) => b.rating - a.rating)

  return (
    <section className="viz-root flex flex-col gap-2">
      <h2 className="text-sm font-medium text-neutral-500">Rating distribution</h2>

      {/* A table rather than divs: the numbers stay readable to a screen reader
       * and survive with styles off, which is the accessible fallback view. */}
      <table className="w-full border-separate border-spacing-y-[2px] text-sm">
        <caption className="sr-only">
          Number of ratings at each star value, out of {total.toLocaleString()} total
        </caption>
        <tbody>
          {ordered.map((bucket) => {
            const share = bucket.count / largest
            const percent = total > 0 ? (bucket.count / total) * 100 : 0
            const isLargest = bucket.count === largest

            return (
              <tr key={bucket.rating} className="group">
                <th
                  scope="row"
                  className="w-10 py-0.5 pr-2 text-right font-normal text-neutral-500 tabular-nums"
                >
                  {bucket.rating.toFixed(1)}
                </th>
                <td className="w-full py-0.5">
                  <div
                    className="h-3 w-full rounded-sm"
                    style={{ background: 'var(--viz-track)' }}
                    title={`${bucket.count.toLocaleString()} ratings (${percent.toFixed(1)}%)`}
                  >
                    <div
                      className="h-3 rounded-r-[4px] transition-[width] duration-200"
                      style={{
                        width: `${Math.max(share * 100, bucket.count > 0 ? 1.5 : 0)}%`,
                        background: 'var(--series-1)',
                      }}
                    />
                  </div>
                </td>
                {/* Only the tallest bar is labelled directly; the rest are on
                 * hover, so the shape reads without a wall of numbers. */}
                <td className="w-16 py-0.5 pl-2 text-right text-neutral-500 tabular-nums">
                  <span className={isLargest ? '' : 'opacity-0 group-hover:opacity-100'}>
                    {bucket.count.toLocaleString()}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}
