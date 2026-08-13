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

export const INK_LIGHT = '#ffffff'
export const INK_DARK = '#1a1a19'

/** WCAG contrast ratio between two colours, 1 (identical) to 21 (black/white). */
export function contrastRatio(a: string, b: string): number {
  const [lighter, darker] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x) as [
    number,
    number,
  ]
  return (lighter + 0.05) / (darker + 0.05)
}

/**
 * Ink that stays legible on a given spine.
 *
 * Picks whichever of the two inks actually contrasts more, rather than
 * splitting on a luminance threshold. A threshold has to be guessed, and a
 * guessed one is wrong across a band: at 0.45 this returned white for #908764
 * -- a real cover colour -- giving 3.6:1 where dark ink gives 4.9:1.
 *
 * The crossover falls near luminance 0.20, which is not somewhere anyone would
 * think to put it by eye.
 */
export function inkOn(background: string): string {
  return contrastRatio(background, INK_LIGHT) >= contrastRatio(background, INK_DARK)
    ? INK_LIGHT
    : INK_DARK
}

/** WCAG AA for normal text. Spine titles are small, so this is the bar. */
export const AA_NORMAL = 4.5

function toHex(rgb: [number, number, number]): string {
  return `#${rgb.map((c) => Math.round(c).toString(16).padStart(2, '0')).join('')}`
}

function mix(from: string, towards: string, amount: number): string {
  const a = parseHex(from)
  const b = parseHex(towards)
  if (!a || !b) return from
  return toHex([0, 1, 2].map((i) => a[i]! + (b[i]! - a[i]!) * amount) as [number, number, number])
}

/**
 * A spine colour its title can actually be read on.
 *
 * Some cover colours cannot carry small text at all: #907d68, a real one, tops
 * out at 4.41:1 against either ink. Rather than accept an illegible title or
 * drop the bar, the background is nudged away from the ink until it clears AA.
 * Hue is preserved -- only lightness moves -- so the book still looks like its
 * cover.
 */
export function legibleSpine(coverColor: string | null): { background: string; ink: string } {
  let background = spineColor(coverColor)
  const ink = inkOn(background)
  const away = ink === INK_LIGHT ? '#000000' : '#ffffff'

  // Small steps so a colour that is already close barely moves. Bounded
  // because a fixed point is not guaranteed for a malformed input.
  for (let step = 0; step < 24 && contrastRatio(background, ink) < AA_NORMAL; step += 1) {
    background = mix(background, away, 0.05)
  }

  return { background, ink }
}
