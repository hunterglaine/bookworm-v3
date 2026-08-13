import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeAll, describe, expect, it } from 'vitest'

import BookActions from './BookActions'
import { readingEntry, shelf } from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { server } from '../test/server'

const HARDCOVER_ID = '175280'

beforeAll(() => {
  // jsdom implements <dialog> but not the modal layer, so showModal/close are
  // stubbed to toggle `open` the way a browser would.
  if (!HTMLDialogElement.prototype.showModal) {
    HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
      this.open = true
    }
    HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
      this.open = false
      this.dispatchEvent(new Event('close'))
    }
  }
})

describe('BookActions', () => {
  it('adds a book only after the dialog is confirmed', async () => {
    // The reason this is a dialog rather than a select: nothing should be
    // written to the database until the user commits.
    const added: string[] = []
    server.use(
      http.get('*/api/v1/shelves', () => HttpResponse.json([shelf({ id: 7, name: 'Sci-fi' })])),
      http.post('*/api/v1/shelves/7/books', async ({ request }) => {
        const body = (await request.json()) as { hardcover_id: string }
        added.push(body.hardcover_id)
        return HttpResponse.json({ id: 1, title: 'Piranesi' }, { status: 201 })
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<BookActions hardcoverId={HARDCOVER_ID} />)

    await user.click(await screen.findByRole('button', { name: /add to shelf/i }))
    await user.click(await screen.findByRole('radio', { name: /sci-fi/i }))
    expect(added).toEqual([])

    await user.click(screen.getByRole('button', { name: 'Add' }))
    await waitFor(() => expect(added).toEqual([HARDCOVER_ID]))
  })

  it('cancelling writes nothing', async () => {
    let posted = false
    server.use(
      http.get('*/api/v1/shelves', () => HttpResponse.json([shelf({ id: 7, name: 'Sci-fi' })])),
      http.post('*/api/v1/shelves/7/books', () => {
        posted = true
        return HttpResponse.json({}, { status: 201 })
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<BookActions hardcoverId={HARDCOVER_ID} />)

    await user.click(await screen.findByRole('button', { name: /add to shelf/i }))
    await user.click(await screen.findByRole('radio', { name: /sci-fi/i }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(posted).toBe(false)
  })

  it('disables shelves the book is already on', async () => {
    // Offering an add that silently succeeds and changes nothing is worse than
    // saying so.
    server.use(
      http.get('*/api/v1/shelves', () =>
        HttpResponse.json([
          shelf({ id: 7, name: 'Sci-fi', contains_book: true }),
          shelf({ id: 8, name: 'Owned', contains_book: false }),
        ]),
      ),
    )

    const user = userEvent.setup()
    renderWithProviders(<BookActions hardcoverId={HARDCOVER_ID} />)
    await user.click(await screen.findByRole('button', { name: /add to shelf/i }))

    expect(await screen.findByRole('radio', { name: /sci-fi/i })).toBeDisabled()
    expect(screen.getByRole('radio', { name: /owned/i })).toBeEnabled()
  })

  it('shows the current reading status as pressed', async () => {
    server.use(
      http.get('*/api/v1/me/books', () =>
        HttpResponse.json([readingEntry({ status: 'reading' })]),
      ),
    )

    renderWithProviders(<BookActions hardcoverId={HARDCOVER_ID} />)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Reading' })).toHaveAttribute(
        'aria-pressed',
        'true',
      ),
    )
    expect(screen.getByRole('button', { name: 'Read' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('clicking the active status clears it', async () => {
    let cleared = false
    server.use(
      http.get('*/api/v1/me/books', () =>
        HttpResponse.json([readingEntry({ status: 'reading' })]),
      ),
      http.delete(`*/api/v1/me/books/${HARDCOVER_ID}`, () => {
        cleared = true
        return new HttpResponse(null, { status: 204 })
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<BookActions hardcoverId={HARDCOVER_ID} />)

    const active = await screen.findByRole('button', { name: 'Reading' })
    await waitFor(() => expect(active).toHaveAttribute('aria-pressed', 'true'))
    await user.click(active)

    await waitFor(() => expect(cleared).toBe(true))
  })

  it('setting a different status puts rather than deletes', async () => {
    let put: string | null = null
    server.use(
      http.get('*/api/v1/me/books', () => HttpResponse.json([])),
      http.put(`*/api/v1/me/books/${HARDCOVER_ID}`, async ({ request }) => {
        const body = (await request.json()) as { status: string }
        put = body.status
        return HttpResponse.json(readingEntry({ status: 'read' }))
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<BookActions hardcoverId={HARDCOVER_ID} />)
    await user.click(await screen.findByRole('button', { name: 'Read' }))

    await waitFor(() => expect(put).toBe('read'))
  })
})
