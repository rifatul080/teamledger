// Small unit test for the fuzzy score + initials helpers used by the UI.
import { describe, expect, it } from "vitest";
import { fallbackColor, initialsFor } from "../../components/ui/Avatar";

describe("Avatar helpers", () => {
  it("initialsFor returns initials from a multi-word name", () => {
    expect(initialsFor("Ada Lovelace")).toBe("AL");
  });
  it("initialsFor returns ? for empty / unknown", () => {
    expect(initialsFor("")).toBe("?");
    expect(initialsFor("   ")).toBe("?");
  });
  it("initialsFor handles single word", () => {
    expect(initialsFor("Satoshi")).toBe("SA");
  });
  it("fallbackColor is deterministic for the same id", () => {
    expect(fallbackColor("user-1")).toEqual(fallbackColor("user-1"));
  });
  it("fallbackColor differs for different ids in most cases", () => {
    // The hash distribution means most ids land on different hues.
    const cs = new Set<string>();
    for (let i = 0; i < 50; i++) cs.add(fallbackColor(`u${i}`).bg);
    expect(cs.size).toBeGreaterThan(10);
  });
});
