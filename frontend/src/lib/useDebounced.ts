import { useEffect, useState } from 'react'

/**
 * Delays a fast-changing value.
 *
 * Every search box in the app needs this: Hardcover allows 60 requests/minute,
 * and firing on each keystroke spends that budget on prefixes nobody meant to
 * search for.
 */
export function useDebounced<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debounced
}

/** Long enough to outlast typing, short enough not to feel laggy. */
export const SEARCH_DEBOUNCE_MS = 400

/** Below this, a query matches too much to be worth a request. */
export const MIN_QUERY_LENGTH = 2
