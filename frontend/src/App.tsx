import { useQuery } from '@tanstack/react-query'

import { api } from './lib/api'

interface Health {
  status: string
}

export default function App() {
  const { data, isPending, isError } = useQuery({
    queryKey: ['health'],
    queryFn: () => api<Health>('/api/v1/health'),
  })

  const apiStatus = isPending
    ? 'checking…'
    : isError
      ? 'unreachable — is the backend running?'
      : data.status

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-6 px-6">
      <div>
        <h1 className="text-4xl font-semibold tracking-tight">Bookworm</h1>
        <p className="mt-2 text-neutral-500">Search books, track what you read, and shelve them.</p>
      </div>

      <dl className="rounded-lg border border-neutral-200 p-4 text-sm dark:border-neutral-800">
        <div className="flex justify-between">
          <dt className="text-neutral-500">API</dt>
          <dd className={isError ? 'text-red-600' : 'font-medium'}>{apiStatus}</dd>
        </div>
      </dl>
    </main>
  )
}
