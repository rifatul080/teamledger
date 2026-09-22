import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { CommandPalette, usePalette } from "./CommandPalette";
import { useTheme } from "../app/theme";

/**
 * Host that wires up the palette to global app-level shortcuts and routes.
 * Each page can call `usePalette().open()` from anywhere; this host owns
 * the singleton instance and the navigation side-effects.
 */
export default function CommandPaletteHost() {
  const palette = usePalette();
  const nav = useNavigate();
  const [, , toggle] = useTheme();
  const initRef = useRef(false);

  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;
    const onNav = (e: Event) => {
      const det = (e as CustomEvent<string>).detail;
      if (typeof det === "string") nav(det);
    };
    const onTheme = () => toggle();
    const onShortcuts = () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "?" }));
      palette.open();
    };
    window.addEventListener("tl:nav", onNav);
    window.addEventListener("tl:theme-toggle", onTheme);
    window.addEventListener("tl:show-shortcuts", onShortcuts);
    return () => {
      window.removeEventListener("tl:nav", onNav);
      window.removeEventListener("tl:theme-toggle", onTheme);
      window.removeEventListener("tl:show-shortcuts", onShortcuts);
    };
  }, [nav, palette, toggle]);

  // Global G-then-* shortcuts: `g d` -> dashboard, `g t` -> teams.
  useEffect(() => {
    let lastG = 0;
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName ?? "";
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      const now = Date.now();
      if (e.key.toLowerCase() === "g" && now - lastG < 800) {
        return; // wait for second key
      }
      if (e.key.toLowerCase() === "g") {
        lastG = now;
        return;
      }
      if (now - lastG < 800) {
        if (e.key.toLowerCase() === "d") nav("/dashboard");
        else if (e.key.toLowerCase() === "t") nav("/teams");
        else if (e.key.toLowerCase() === "n") nav("/notifications");
        lastG = 0;
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [nav]);

  return <CommandPalette palette={palette} />;
}
