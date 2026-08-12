/** Colour helpers for generated book spines.
 *
 * Spine colours come from the provider's dominant-cover colour, so they are
 * arbitrary and cannot be checked by hand. Ink is therefore computed from
 * relative luminance rather than picked -- the same reasoning as validating a
 * chart palette instead of eyeballing it.
 */

const FALLBACK_SPINE = '#6b6a66'

function parseHex(hex: string): [number, number, number] | null {
  const match = /^#?([0-9a-f]{6}|[0-9a-f]{3})$/i.exec(hex.trim())
  if (!match) return null

  let body = match[1]
  if (!body) return null
  if (body.length === 3) {
    body = body
      .split('')
      .map((c) => c + c)
      .join('')
  }

  const value = Number.parseInt(body, 16)
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255]
}

/** WCAG relative luminance, 0 (black) to 1 (white). */
export function relativeLuminance(hex: string): number {
  const rgb = parseHex(hex)
  if (!rgb) return 0

  const [r, g, b] = rgb.map((channel) => {
    const c = channel / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }) as [number, number, number]

  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

/** A usable spine colour, falling back when the provider gave none. */
export function spineColor(coverColor: string | null): string {
  return parseHex(coverColor ?? '') ? coverColor! : FALLBACK_SPINE
}

/**
 * Ink that stays legible on a given spine.
 *
 * 0.45 rather than 0.5: white text needs a slightly darker background than the
 * midpoint to hold contrast, because luminance is not perceptually linear.
 */
export function inkOn(background: string): string {
  return relativeLuminance(background) > 0.45 ? '#1a1a19' : '#ffffff'
}
