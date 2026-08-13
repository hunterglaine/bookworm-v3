import { describe, expect, it } from 'vitest'

import {
  AA_NORMAL,
  INK_DARK,
  INK_LIGHT,
  contrastRatio,
  inkOn,
  legibleSpine,
  relativeLuminance,
  spineColor,
} from './color'

/**
 * Spine colours come from the provider, so they are arbitrary and cannot be
 * eyeballed. These pin the contrast decision rather than the appearance.
 */
describe('spineColor', () => {
  it('keeps a usable provider colour', () => {
    expect(spineColor('#908764')).toBe('#908764')
  })

  it('falls back when the provider gave nothing', () => {
    expect(spineColor(null)).toBe('#6b6a66')
  })

  it('falls back on malformed input rather than emitting broken CSS', () => {
    // A bad colour would silently become "transparent" in CSS, which reads as
    // a missing book rather than an obvious defect.
    for (const bad of ['', 'rebeccapurple', '#12', '#gggggg', 'null']) {
      expect(spineColor(bad)).toBe('#6b6a66')
    }
  })

  it('accepts shorthand hex', () => {
    expect(spineColor('#abc')).toBe('#abc')
  })
})

describe('relativeLuminance', () => {
  it('spans black to white', () => {
    expect(relativeLuminance('#000000')).toBeCloseTo(0, 5)
    expect(relativeLuminance('#ffffff')).toBeCloseTo(1, 5)
  })

  it('weights green above red above blue, as perception does', () => {
    const green = relativeLuminance('#00ff00')
    const red = relativeLuminance('#ff0000')
    const blue = relativeLuminance('#0000ff')

    expect(green).toBeGreaterThan(red)
    expect(red).toBeGreaterThan(blue)
  })
})

describe('inkOn', () => {
  it('puts white on dark spines and near-black on light ones', () => {
    expect(inkOn('#1a1a19')).toBe('#ffffff')
    expect(inkOn('#ffffff')).toBe('#1a1a19')
  })

  it.each([
    // Real cover colours from Hardcover, including the near-white one.
    '#908764',
    '#907d68',
    '#e6e6df',
    '#b0b0b0',
    '#808080',
    '#000000',
    '#ffffff',
  ])('never picks the less legible of the two inks on %s', (background) => {
    // The property, rather than a memorised answer: whatever it returns must
    // contrast at least as well as the alternative. A guessed threshold fails
    // this across a whole band of colours.
    const chosen = inkOn(background)
    const other = chosen === INK_LIGHT ? INK_DARK : INK_LIGHT

    expect(contrastRatio(background, chosen)).toBeGreaterThanOrEqual(
      contrastRatio(background, other),
    )
  })

  it('cannot always reach AA on the raw provider colour', () => {
    // Documents why legibleSpine exists: this one tops out below the bar
    // against either ink, so picking the better ink is not sufficient.
    const best = Math.max(contrastRatio('#907d68', INK_LIGHT), contrastRatio('#907d68', INK_DARK))
    expect(best).toBeLessThan(AA_NORMAL)
  })
})

describe('legibleSpine', () => {
  it.each([
    '#908764',
    '#907d68',
    '#e6e6df',
    '#b0b0b0',
    '#808080',
    '#7f7f7f',
    '#000000',
    '#ffffff',
    '#ff0000',
  ])('clears AA on %s', (coverColor) => {
    const { background, ink } = legibleSpine(coverColor)
    expect(contrastRatio(background, ink)).toBeGreaterThanOrEqual(AA_NORMAL)
  })

  it('clears AA on the fallback when the provider gave nothing', () => {
    const { background, ink } = legibleSpine(null)
    expect(contrastRatio(background, ink)).toBeGreaterThanOrEqual(AA_NORMAL)
  })

  it('leaves a colour alone when it is already legible', () => {
    // Black already contrasts at 21:1; nudging it would change the book's
    // appearance for nothing.
    expect(legibleSpine('#000000').background).toBe('#000000')
  })

  it('preserves hue while adjusting lightness', () => {
    // The spine should still look like the cover it came from.
    const { background } = legibleSpine('#907d68')
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(background.slice(i, i + 2), 16))
    expect(r).toBeGreaterThan(g!)
    expect(g).toBeGreaterThan(b!)
  })
})
