import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { type Credentials, login, register } from '@/lib/auth'

type Mode = 'login' | 'register'

const MIN_PASSWORD_LENGTH = 12

export default function AuthForm() {
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')

  const submit = useMutation({
    mutationFn: (credentials: Credentials) =>
      mode === 'login' ? login(credentials) : register(credentials),
    onSuccess: (user) => {
      // Seed the cache directly -- the response is the same shape /me returns,
      // so refetching it immediately would be a wasted round trip.
      queryClient.setQueryData(['currentUser'], user)
    },
  })

  const isRegistering = mode === 'register'

  return (
    <form
      className="mx-auto flex w-full max-w-sm flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        submit.mutate({
          email,
          password,
          ...(isRegistering && displayName ? { display_name: displayName } : {}),
        })
      }}
    >
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Bookworm</h1>
        <p className="mt-1 text-sm text-neutral-500">
          {isRegistering ? 'Create an account to start shelving.' : 'Sign in to your shelves.'}
        </p>
      </div>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-neutral-500">Email</span>
        <input
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="rounded-md border border-neutral-300 px-3 py-2 dark:border-neutral-700 dark:bg-neutral-900"
        />
      </label>

      {isRegistering && (
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-neutral-500">Display name (optional)</span>
          <input
            type="text"
            maxLength={100}
            autoComplete="nickname"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            className="rounded-md border border-neutral-300 px-3 py-2 dark:border-neutral-700 dark:bg-neutral-900"
          />
        </label>
      )}

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-neutral-500">Password</span>
        <input
          type="password"
          required
          minLength={isRegistering ? MIN_PASSWORD_LENGTH : undefined}
          autoComplete={isRegistering ? 'new-password' : 'current-password'}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="rounded-md border border-neutral-300 px-3 py-2 dark:border-neutral-700 dark:bg-neutral-900"
        />
        {isRegistering && (
          <span className="text-xs text-neutral-500">
            At least {MIN_PASSWORD_LENGTH} characters. Length beats punctuation.
          </span>
        )}
      </label>

      {submit.isError && (
        <p role="alert" className="text-sm text-red-600">
          {submit.error.message}
        </p>
      )}

      <button
        type="submit"
        disabled={submit.isPending}
        className="rounded-md bg-neutral-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900"
      >
        {submit.isPending ? 'Working…' : isRegistering ? 'Create account' : 'Sign in'}
      </button>

      <button
        type="button"
        className="text-sm text-neutral-500 underline underline-offset-4"
        onClick={() => {
          setMode(isRegistering ? 'login' : 'register')
          submit.reset()
        }}
      >
        {isRegistering ? 'Already have an account? Sign in' : 'Need an account? Register'}
      </button>
    </form>
  )
}
