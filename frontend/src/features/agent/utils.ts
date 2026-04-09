export function deriveSessionTitle(input: string, maxLength = 30) {
  const condensed = input.trim().replace(/\s+/g, " ");

  if (!condensed) {
    return "默认会话";
  }

  if (condensed.length <= maxLength) {
    return condensed;
  }

  const sliced = condensed.slice(0, maxLength).trim();
  const punctuationPattern = /[，。！？、：；,.!?]$/u;
  const normalized = punctuationPattern.test(sliced)
    ? sliced.replace(punctuationPattern, "，")
    : `${sliced.slice(0, -1).replace(punctuationPattern, "")}，`;

  return `${normalized}...`;
}
