import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, Route, Routes } from 'react-router'

import AuthForm from '@/components/AuthForm'
import BookSearch from '@/components/BookSearch'
import { api } from '@/lib/api'
import { fetchCurrentUser, logout } from '@/lib/auth'
import BookDetailPage from '@/routes/BookDetailPage'
import BookshelfPage from '@/routes/BookshelfPage'
import ShelfPage from '@/routes/ShelfPage'
import ShelvesPage from '@/routes/ShelvesPage'

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
    // Wide enough for a shelf of spines. Text-heavy blocks constrain their own
    // line length rather than the whole app being narrowed to suit them.
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-6 py-12">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link to="/" className="text-4xl font-semibold tracking-tight">
            Bookworm
          </Link>
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

      {health.isError && (
        <p role="alert" className="text-sm text-red-600">
          API unreachable — is the backend running?
        </p>
      )}

      <nav className="flex gap-4 text-sm">
        <Link to="/" className="underline-offset-4 hover:underline">
          Search
        </Link>
        <Link to="/bookshelf" className="underline-offset-4 hover:underline">
          Bookshelf
        </Link>
        <Link to="/shelves" className="underline-offset-4 hover:underline">
          Manage shelves
        </Link>
      </nav>

      <Routes>
        <Route path="/" element={<BookSearch />} />
        <Route path="/books/:hardcoverId" element={<BookDetailPage />} />
        <Route path="/bookshelf" element={<BookshelfPage />} />
        <Route path="/shelves" element={<ShelvesPage />} />
        <Route path="/shelves/:shelfId" element={<ShelfPage />} />
        <Route
          path="*"
          element={
            <div className="flex flex-col gap-4">
              <p className="text-neutral-500">Nothing here.</p>
              <Link to="/" className="text-sm underline underline-offset-4">
                Back to search
              </Link>
            </div>
          }
        />
      </Routes>
    </main>
  )
}
