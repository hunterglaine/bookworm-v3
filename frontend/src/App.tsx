import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import AuthForm from '@/components/AuthForm'
import { api } from '@/lib/api'
import { fetchCurrentUser, logout } from '@/lib/auth'

interface Health {
  status: string
}

export default function App() {
  const queryClient = useQueryClient()

  const { data: user, isPending } = useQuery({
    queryKey: ['currentUser'],
    queryFn: fetchCurrentUser,
  })

  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => api<Health>('/api/v1/health'),
  })

  const signOut = useMutation({
    mutationFn: logout,
    onSuccess: () => queryClient.setQueryData(['currentUser'], null),
  })

  if (isPending) {
    return <main className="grid min-h-screen place-items-center text-neutral-500">Loading…</main>
  }

  if (!user) {
    return (
      <main className="grid min-h-screen place-items-center px-6">
        <AuthForm />
      </main>
    )
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-6 px-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-4xl font-semibold tracking-tight">Bookworm</h1>
          <p className="mt-2 text-neutral-500">Signed in as {user.display_name ?? user.email}.</p>
        </div>
        <button
          type="button"
          onClick={() => signOut.mutate()}
          disabled={signOut.isPending}
          className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm disabled:opacity-50 dark:border-neutral-700"
        >
          {signOut.isPending ? 'Signing out…' : 'Sign out'}
        </button>
      </div>

      <dl className="rounded-lg border border-neutral-200 p-4 text-sm dark:border-neutral-800">
        <div className="flex justify-between">
          <dt className="text-neutral-500">API</dt>
          <dd className={health.isError ? 'text-red-600' : 'font-medium'}>
            {health.isPending
              ? 'checking…'
              : health.isError
                ? 'unreachable — is the backend running?'
                : health.data.status}
          </dd>
        </div>
      </dl>

      <p className="text-sm text-neutral-500">Book search lands in the next phase.</p>
    </main>
  )
}
