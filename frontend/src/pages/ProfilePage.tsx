import { useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useMe, Me, useUpdateProfile, useUploadAvatar } from "../app/auth";
import { api } from "../app/api";
import { Avatar } from "../components/ui/Avatar";
import { useTheme } from "../app/theme";
import { useQuery } from "@tanstack/react-query";
import { pushToast } from "../components/ui/Toast";

type ProfileData = Me;

export default function ProfilePage() {
  const { userId } = useParams();
  const me = useMe();
  const update = useUpdateProfile();
  const upload = useUploadAvatar();
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [theme, setTheme] = useTheme();

  const isSelf = !userId || userId === me.data?.id;
  const profile = useQuery({
    queryKey: ["user", userId ?? "me"],
    enabled: !!me.data,
    queryFn: (): Promise<ProfileData> => {
      if (isSelf) {
        return Promise.resolve(me.data!);
      }
      return api<ProfileData>(`/users/${userId}`);
    },
  });

  if (!profile.data) return <div className="text-meta">Loading…</div>;
  const u = profile.data;
  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-6">
      <header className="flex items-start gap-4">
        <Avatar userId={u.id} displayName={u.display_name} src={u.avatar_url ?? null} size="xl" />
        <div className="flex-1 min-w-0">
          <h1 className="text-h1">{u.display_name}</h1>
          <p className="text-meta">{u.email}</p>
          {u.institution && <p className="text-meta">{u.institution}</p>}
        </div>
        {isSelf && (
          <button
            className="btn-secondary"
            onClick={() => fileRef.current?.click()}
            disabled={upload.isPending}
          >
            {upload.isPending ? "Uploading…" : "Change photo"}
          </button>
        )}
        {isSelf && (
          <input
            type="file"
            ref={fileRef}
            accept="image/png,image/jpeg,image/gif,image/webp"
            className="hidden"
            onChange={async (e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              try {
                await upload.mutateAsync(f);
                pushToast({ kind: "ok", title: "Photo updated" });
              } catch (err) {
                pushToast({
                  kind: "error",
                  title: "Upload failed",
                  body: (err as { message?: string }).message,
                });
              } finally {
                if (fileRef.current) fileRef.current.value = "";
              }
            }}
          />
        )}
      </header>

      {isSelf && (
        <section className="card">
          <h2 className="text-h2 mb-3">Account</h2>
          <div className="grid sm:grid-cols-2 gap-3">
            <Field
              label="Display name"
              defaultValue={u.display_name}
              onCommit={async (v) => {
                await update.mutateAsync({ display_name: v });
                pushToast({ kind: "ok", title: "Name updated" });
              }}
            />
            <Field
              label="Timezone"
              defaultValue={u.timezone}
              onCommit={async (v) => {
                await update.mutateAsync({ timezone: v });
                pushToast({ kind: "ok", title: "Timezone updated" });
              }}
            />
            <Field
              label="Institution"
              defaultValue={u.institution ?? ""}
              onCommit={async (v) => {
                await update.mutateAsync({ institution: v });
                pushToast({ kind: "ok", title: "Institution updated" });
              }}
            />
            <div>
              <label className="label">Theme</label>
              <div className="flex gap-2">
                <button
                  type="button"
                  className={`btn-sm ${theme === "light" ? "btn-primary" : "btn-secondary"}`}
                  onClick={() => setTheme("light")}
                >
                  Light
                </button>
                <button
                  type="button"
                  className={`btn-sm ${theme === "dark" ? "btn-primary" : "btn-secondary"}`}
                  onClick={() => setTheme("dark")}
                >
                  Dark
                </button>
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function Field({
  label,
  defaultValue,
  onCommit,
}: {
  label: string;
  defaultValue: string;
  onCommit: (v: string) => Promise<void>;
}) {
  const [v, setV] = useState(defaultValue);
  return (
    <div>
      <label className="label">{label}</label>
      <div className="flex gap-2">
        <input
          className="input"
          value={v}
          onChange={(e) => setV(e.target.value)}
          onBlur={() => {
            if (v !== defaultValue) onCommit(v);
          }}
        />
      </div>
    </div>
  );
}
