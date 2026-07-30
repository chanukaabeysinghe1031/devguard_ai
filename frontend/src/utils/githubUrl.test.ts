import { describe, expect, it } from "vitest";

import { isSafeGitHubUrl } from "./githubUrl";

describe("isSafeGitHubUrl", () => {
  it("accepts https github.com URLs", () => {
    expect(isSafeGitHubUrl("https://github.com/org/repo/actions/runs/123")).toBe(true);
  });

  it("accepts https www.github.com URLs", () => {
    expect(isSafeGitHubUrl("https://www.github.com/org/repo")).toBe(true);
  });

  it("rejects non-https protocols", () => {
    expect(isSafeGitHubUrl("http://github.com/org/repo")).toBe(false);
  });

  it("rejects lookalike hosts", () => {
    expect(isSafeGitHubUrl("https://github.com.evil.example/org/repo")).toBe(false);
    expect(isSafeGitHubUrl("https://notgithub.com/org/repo")).toBe(false);
  });

  it("rejects malformed URLs", () => {
    expect(isSafeGitHubUrl("not a url")).toBe(false);
  });

  it("rejects null/undefined/empty values", () => {
    expect(isSafeGitHubUrl(null)).toBe(false);
    expect(isSafeGitHubUrl(undefined)).toBe(false);
    expect(isSafeGitHubUrl("")).toBe(false);
  });
});
