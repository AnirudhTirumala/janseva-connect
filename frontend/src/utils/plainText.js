/**
 * Defensive cleanup for assistant replies before they are rendered as text.
 *
 * The system prompt asks the model for plain text, but a model is not a
 * contract: it will still reach for **bold**, `#` headings, or a pipe table
 * now and then. The chat bubble renders its content as text (never as HTML -
 * that would make model output an XSS vector), so leftover Markdown shows up
 * as literal asterisks and pipes.
 *
 * This strips the handful of markers that actually appear, and turns a pipe
 * table into readable lines, without pulling in a Markdown renderer.
 */
export function toReadableText(value) {
  if (typeof value !== 'string') return ''
  return value
    .split('\n')
    .map((line) => {
      // A table separator row ("|---|---|") carries no information as text.
      if (/^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(line) && line.includes('-')) return null
      let text = line
      if (text.trim().startsWith('|')) {
        // "| Scheme | Documents |" -> "Scheme — Documents"
        text = text.trim().replace(/^\||\|$/g, '').split('|').map((cell) => cell.trim()).filter(Boolean).join(' — ')
      }
      return text
        .replace(/<br\s*\/?>/gi, '\n')
        .replace(/\*\*(.+?)\*\*/g, '$1')
        .replace(/(^|\s)\*(?!\s)(.+?)(?<!\s)\*/g, '$1$2')
        .replace(/`{1,3}([^`]+)`{1,3}/g, '$1')
        .replace(/^\s*#{1,6}\s*/, '')
    })
    .filter((line) => line !== null)
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}
