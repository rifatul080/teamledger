// Simple profile view (display name + email).
import { Card } from "../components/ui";
import { useMe } from "../app/auth";

export default function ProfilePage() {
  const me = useMe();
  if (!me.data) return <div>Loading…</div>;
  return (
    <Card>
      <h1 className="text-2xl font-semibold mb-4">Profile</h1>
      <dl className="text-sm grid grid-cols-2 gap-2">
        <dt className="text-slate-500">Email</dt>
        <dd>{me.data.email}</dd>
        <dt className="text-slate-500">Display name</dt>
        <dd>{me.data.display_name}</dd>
        <dt className="text-slate-500">Timezone</dt>
        <dd>{me.data.timezone}</dd>
        <dt className="text-slate-500">Joined</dt>
        <dd>{new Date(me.data.created_at).toLocaleDateString()}</dd>
      </dl>
    </Card>
  );
}
