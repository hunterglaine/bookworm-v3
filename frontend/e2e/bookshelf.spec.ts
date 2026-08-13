import { expect, test } from '@playwright/test'

import { signedInBookshelf } from './fixtures'

/**
 * The cases jsdom cannot answer.
 *
 * Every assertion here is about geometry or paint order -- both of which
 * require a real layout engine. These pin the two Phase 7 bugs that got through
 * typechecking, linting and 102 backend tests.
 */
test.beforeEach(async ({ page }) => {
  await signedInBookshelf(page)
  await page.goto('/bookshelf')
  await expect(page.getByRole('link', { name: 'Sci-fi' })).toBeVisible()
})

test('spines render for every book on a shelf', async ({ page }) => {
  const shelf = page.locator('[data-rfd-droppable-id="1"]')
  await expect(shelf.getByRole('link')).toHaveCount(4)
})

test('hovering a spine reveals its cover', async ({ page }) => {
  const spine = page.getByRole('link', { name: /^Piranesi by/ })
  await spine.hover()

  const cover = page.locator('img[src^="data:image"]').last()
  await expect(cover).toBeVisible()
})

test('the cover stays on screen when the first spine is hovered', async ({ page }) => {
  // Covers are centred on their spine and much wider, so the leftmost book
  // would overhang the viewport without clamping.
  //
  // This does not test clipping: boundingBox() reports geometry whether or not
  // an ancestor clips the element, so a clipped cover still measures as being
  // on screen. Clipping is covered by the ancestor check below.
  await page.getByRole('link', { name: /^Piranesi by/ }).hover()

  const cover = page.locator('img[src^="data:image"]').last()
  const box = await cover.boundingBox()
  const viewport = page.viewportSize()

  expect(box).not.toBeNull()
  expect(box!.width).toBeGreaterThan(80)
  expect(box!.x).toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport!.width)
  expect(box!.y).toBeGreaterThanOrEqual(0)
})

test('the hovered cover escapes every clipping and stacking ancestor', async ({ page }) => {
  // The second bug: the drag library puts a transform on each draggable, and a
  // transform creates a stacking context, so later spines painted over the
  // cover regardless of its z-index. The row also clips, because overflow-x
  // forces the other axis to a non-visible value.
  //
  // Asserted structurally rather than by hit-testing: the cover carries
  // pointer-events: none so it does not block hover on the spine beneath, and
  // elementFromPoint skips such elements. What actually makes it immune is
  // having no ancestor that clips or transforms.
  await page.getByRole('link', { name: /^Piranesi by/ }).hover()

  const result = await page.evaluate(() => {
    const cover = [...document.querySelectorAll('img')].at(-1)
    if (!cover) return { error: 'no cover rendered' }

    // The cover's immediate wrapper clips it to rounded corners, which is
    // fine. What matters is everything above that: the wrapper must hang off
    // <body>, not off the shelf row.
    const wrapper = cover.parentElement
    if (!wrapper) return { error: 'cover has no wrapper' }

    const offenders: string[] = []
    for (let node = wrapper.parentElement; node && node !== document.body; node = node.parentElement) {
      const style = getComputedStyle(node)
      if (style.transform !== 'none') offenders.push(`transform on ${node.tagName}`)
      if (!['visible', ''].includes(style.overflowX)) offenders.push(`overflow-x on ${node.tagName}`)
      if (!['visible', ''].includes(style.overflowY)) offenders.push(`overflow-y on ${node.tagName}`)
    }

    return {
      portalled: wrapper.parentElement === document.body,
      position: getComputedStyle(wrapper).position,
      offenders,
    }
  })

  expect(result).toEqual({ portalled: true, position: 'fixed', offenders: [] })
})

test('a shelf with many books still fits its case', async ({ page }) => {
  const shelf = page.locator('[data-rfd-droppable-id="1"]')
  const shelfBox = await shelf.boundingBox()
  const caseBox = await page.locator('.bookcase').boundingBox()

  expect(shelfBox).not.toBeNull()
  expect(caseBox).not.toBeNull()
  expect(shelfBox!.x).toBeGreaterThanOrEqual(caseBox!.x)
  expect(shelfBox!.x + shelfBox!.width).toBeLessThanOrEqual(caseBox!.x + caseBox!.width + 1)
})

test('a long title is truncated rather than overflowing its spine', async ({ page }) => {
  const spine = page.getByRole('link', { name: /^A Wizard of Earthsea/ })
  const spineBox = await spine.boundingBox()
  const titleBox = await spine.locator('span').first().boundingBox()

  expect(spineBox).not.toBeNull()
  expect(titleBox).not.toBeNull()
  expect(titleBox!.height).toBeLessThanOrEqual(spineBox!.height)
})
