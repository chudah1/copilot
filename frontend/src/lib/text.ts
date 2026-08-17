const BLOCK_CLOSE_TAG = /<\s*\/\s*(?:p|div|li|body|html|article|section|h[1-6])\s*>/gi;
const BLOCK_OPEN_TAG = /<\s*(?:p|div|li|body|html|article|section|h[1-6])\b[^>]*>/gi;
const BREAK_TAG = /<\s*(?:br|hr)\s*\/?>/gi;

/** Convert provider markup into readable text without rendering untrusted HTML. */
export function cleanRichText(value: string | null | undefined): string {
  if (!value) return "";

  return value
    .replace(/\\n/g, "\n")
    .replace(BLOCK_CLOSE_TAG, "\n")
    .replace(BLOCK_OPEN_TAG, "\n")
    .replace(BREAK_TAG, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&quot;/gi, '"')
    .replace(/(?:&#39;|&apos;)/gi, "'")
    .replace(/\n[ \t]*\n[ \t]*\n+/g, "\n\n")
    .trim();
}
