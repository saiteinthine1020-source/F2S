import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

function sourceFiles(path: string): string[] {
  return readdirSync(path).flatMap((entry) => {
    const candidate = join(path, entry);
    return statSync(candidate).isDirectory() ? sourceFiles(candidate) : [candidate];
  });
}

describe("credential storage boundary", () => {
  it("contains no browser persistent-storage access in application source", () => {
    const source = sourceFiles(join(process.cwd(), "src"))
      .map((path) => readFileSync(path, "utf8"))
      .join("\n");
    expect(source).not.toMatch(/\b(?:localStorage|sessionStorage|indexedDB)\b/u);
  });

  it("contains no obvious hardcoded visible JSX text", () => {
    const violations = sourceFiles(join(process.cwd(), "src"))
      .filter((path) => path.endsWith(".tsx"))
      .filter((path) => />[ \t]*[A-Za-z][^<{\r\n]*</u.test(readFileSync(path, "utf8")));
    expect(violations).toEqual([]);
  });
});
