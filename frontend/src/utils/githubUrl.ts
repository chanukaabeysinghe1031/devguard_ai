/** Guards against rendering unsafe/spoofed links sourced from webhook payloads. */
export function isSafeGitHubUrl(url: string | null | undefined): boolean {
  if (!url) return false;
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return false;
  }
  if (parsed.protocol !== "https:") return false;
  return parsed.hostname === "github.com" || parsed.hostname === "www.github.com";
}
