import { describe, expect, it } from "vitest";
import { filterMembers, mentionQueryAt, splitMentions, wsUrlFor } from "../chat";

describe("mentionQueryAt", () => {
  it("detects a bare @ at the caret", () => {
    expect(mentionQueryAt("@", 1)).toEqual({ query: "", start: 0 });
  });

  it("detects a partial name and reports where it starts", () => {
    const text = "hey @Ma";
    expect(mentionQueryAt(text, text.length)).toEqual({ query: "Ma", start: 4 });
  });

  it("keeps the start offset when the mention is mid-sentence", () => {
    const text = "ping @Ada Lovelace about this";
    expect(mentionQueryAt(text, text.indexOf(" about"))).toEqual({
      query: "Ada Lovelace",
      start: 5,
    });
  });

  it("keeps suggesting after a space in a multi-word name", () => {
    const text = "ping @Ada ";
    expect(mentionQueryAt(text, text.length)).toEqual({ query: "Ada ", start: 5 });
  });

  it("returns null when there is no active mention", () => {
    expect(mentionQueryAt("hello world", 11)).toBeNull();
    // "email@example" — the @ must follow whitespace or start the text.
    expect(mentionQueryAt("email@ex", 8)).toBeNull();
  });
});

describe("splitMentions", () => {
  it("marks @name segments and leaves the rest alone", () => {
    const parts = splitMentions("hi @Ada and @Bob, ship it", ["Ada", "Bob"]);
    expect(parts.filter((p) => p.mention).map((p) => p.text)).toEqual(["@Ada", "@Bob"]);
    expect(parts.map((p) => p.text).join("")).toBe("hi @Ada and @Bob, ship it");
  });

  it("prefers the longest matching name", () => {
    const parts = splitMentions("@Ada Lovelace hi", ["Ada", "Ada Lovelace"]);
    expect(parts[0]).toEqual({ text: "@Ada Lovelace", mention: true });
  });

  it("leaves unknown @handles as plain text", () => {
    const parts = splitMentions("ping @Nobody", ["Ada"]);
    expect(parts).toEqual([{ text: "ping @Nobody", mention: false }]);
  });
});

describe("filterMembers", () => {
  const members = [
    { user_id: "1", display_name: "Ada Lovelace" },
    { user_id: "2", display_name: "Bob" },
    { user_id: "3", display_name: "me" },
  ];

  it("matches on a case-insensitive substring", () => {
    expect(filterMembers(members, "ad").map((m) => m.display_name)).toEqual([
      "Ada Lovelace",
    ]);
  });

  it("excludes the current user", () => {
    expect(filterMembers(members, "", "3").map((m) => m.display_name)).toEqual([
      "Ada Lovelace",
      "Bob",
    ]);
  });
});

describe("wsUrlFor", () => {
  it("upgrades the API base to a websocket URL", () => {
    const url = wsUrlFor("/teams/abc/chat");
    expect(url.startsWith("ws://") || url.startsWith("wss://")).toBe(true);
    expect(url).toContain("/api/v1/teams/abc/chat");
  });
});
