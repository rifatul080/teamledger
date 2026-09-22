import React from "react";

export type AvatarSize = "xs" | "sm" | "md" | "lg" | "xl";

const SIZE_CLASS: Record<AvatarSize, string> = {
  xs: "w-5 h-5 text-[9px]",
  sm: "w-7 h-7 text-[11px]",
  md: "w-9 h-9 text-sm",
  lg: "w-12 h-12 text-base",
  xl: "w-20 h-20 text-2xl",
};

export function fallbackColor(id: string): { bg: string; fg: string } {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) | 0;
  const hue = Math.abs(h) % 360;
  const lightBg = `hsl(${hue} 70% 88%)`;
  const lightFg = `hsl(${hue} 35% 28%)`;
  return { bg: lightBg, fg: lightFg };
}

export function initialsFor(displayName: string): string {
  const parts = (displayName || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return (parts[0] ?? "?").slice(0, 2).toUpperCase();
  const first = parts[0] ?? "";
  const last = parts[parts.length - 1] ?? "";
  return ((first[0] || "") + (last[0] || "")).toUpperCase();
}

export type AvatarProps = {
  userId: string;
  displayName: string;
  src?: string | null;
  size?: AvatarSize;
  className?: string;
  title?: string;
};

export function Avatar({ userId, displayName, src, size = "md", className = "", title }: AvatarProps) {
  const [failed, setFailed] = React.useState(false);
  const showImg = src && !failed;
  const fb = fallbackColor(userId);
  return (
    <span
      className={`inline-flex items-center justify-center rounded-full overflow-hidden border border-line font-semibold uppercase select-none ${SIZE_CLASS[size]} ${className}`}
      style={!showImg ? { backgroundColor: fb.bg, color: fb.fg } : undefined}
      title={title ?? displayName}
      aria-label={displayName}
      data-user-id={userId}
    >
      {showImg ? (
        <img
          src={src ?? undefined}
          alt={displayName}
          onError={() => setFailed(true)}
          loading="lazy"
          className="w-full h-full object-cover"
        />
      ) : (
        <span aria-hidden="true">{initialsFor(displayName)}</span>
      )}
    </span>
  );
}

export function AvatarStack({
  users,
  size = "xs",
  max = 4,
}: {
  users: { id: string; display_name: string; avatar_url?: string | null }[];
  size?: AvatarSize;
  max?: number;
}) {
  const visible = users.slice(0, max);
  const extra = users.length - visible.length;
  return (
    <span className="inline-flex -space-x-1.5">
      {visible.map((u) => (
        <Avatar
          key={u.id}
          userId={u.id}
          displayName={u.display_name}
          src={u.avatar_url ?? null}
          size={size}
          className="ring-2 ring-paper"
        />
      ))}
      {extra > 0 && (
        <span
          className={`inline-flex items-center justify-center rounded-full bg-paper-sun border border-line text-ink-muted font-semibold ring-2 ring-paper ${SIZE_CLASS[size]}`}
          title={`${extra} more`}
        >
          +{extra}
        </span>
      )}
    </span>
  );
}
