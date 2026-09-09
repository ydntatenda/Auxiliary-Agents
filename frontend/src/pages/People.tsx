import { CheckCircle2, FileUp, ShieldCheck } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import {
  CurrentUser,
  WorkerProfile,
  confirmWorkerProfile,
  listWorkerProfiles,
  updateWorkerProfile,
  uploadWorkerCv,
} from "../api/client";


export default function People({ user }: { user: CurrentUser }) {
  const [profiles, setProfiles] = useState<WorkerProfile[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listWorkerProfiles().then(setProfiles).catch((err) => {
      setError(err instanceof Error ? err.message : "Could not load worker profiles.");
    });
  }, []);

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const profile = await uploadWorkerCv(file);
      setProfiles((current) => [profile, ...current.filter((row) => row.member_id !== profile.member_id)]);
      setFile(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "CV extraction failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="workarea">
      <div className="canvas wide">
        <div className="step-eyebrow"><span className="num">People</span><span>{user.org_name}</span></div>
        <h1 className="page-title">Workforce intelligence.</h1>
        <p className="page-sub">
          Build worker-confirmed profiles from CVs. Uropi uses only sourced capabilities and preferences when proposing future roles.
        </p>

        <form className="people-upload" onSubmit={upload}>
          <FileUp size={20} />
          <div className="people-upload-copy">
            <strong>Upload your CV or resume</strong>
            <span>PDF or DOCX, up to 15 MB. Extraction creates a draft for you to correct.</span>
          </div>
          <input
            type="file"
            accept=".pdf,.docx"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            disabled={busy}
          />
          <button className="btn btn-primary" type="submit" disabled={!file || busy}>
            {busy ? "Extracting" : "Create profile"}
          </button>
        </form>

        <div className="privacy-note">
          <ShieldCheck size={15} />
          Sensitive characteristics are excluded. Role recommendations remain optional and require human review.
        </div>
        {error && <div className="error">{error}</div>}

        <div className="profile-grid">
          {profiles.map((profile) => (
            <ProfileCard
              key={profile.id}
              profile={profile}
              editable={user.role === "admin" || user.id === profile.member_id}
              onChange={(next) => setProfiles((rows) => rows.map((row) => row.id === next.id ? next : row))}
            />
          ))}
          {!profiles.length && <div className="lib-empty"><h3>No worker profiles yet.</h3><p>Upload the first CV to establish the workforce layer.</p></div>}
        </div>
      </div>
    </div>
  );
}


function ProfileCard({
  profile,
  editable,
  onChange,
}: {
  profile: WorkerProfile;
  editable: boolean;
  onChange: (profile: WorkerProfile) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(profile.name);
  const [role, setRole] = useState(profile.current_role ?? "");
  const [summary, setSummary] = useState(profile.summary ?? "");
  const [preferences, setPreferences] = useState(profile.career_preferences.join("\n"));
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      const next = await updateWorkerProfile(profile.member_id, {
        name: name.trim(),
        current_role: role.trim() || null,
        summary: summary.trim() || null,
        career_preferences: preferences.split("\n").map((item) => item.trim()).filter(Boolean),
      });
      onChange(next);
      setEditing(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="profile-card">
      <div className="profile-head">
        <div>
          <span className={`sc-pill status-${profile.status}`}>{profile.status}</span>
          <h2>{profile.name}</h2>
          <p>{profile.current_role || "Role not supplied"}</p>
        </div>
        {editable && <button className="btn btn-ghost" type="button" onClick={() => setEditing(!editing)}>{editing ? "Cancel" : "Review profile"}</button>}
      </div>
      {editing ? (
        <div className="profile-editor">
          <label>Name<input className="text-input" value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label>Current role<input className="text-input" value={role} onChange={(e) => setRole(e.target.value)} /></label>
          <label>Summary<textarea className="text-input" rows={3} value={summary} onChange={(e) => setSummary(e.target.value)} /></label>
          <label>Career preferences, one per line<textarea className="text-input" rows={3} value={preferences} onChange={(e) => setPreferences(e.target.value)} /></label>
          <button className="btn btn-primary" type="button" onClick={save} disabled={busy || !name.trim()}>{busy ? "Saving" : "Save corrections"}</button>
        </div>
      ) : (
        <>
          <p className="profile-summary">{profile.summary}</p>
          <div className="skill-list">{profile.skills.map((skill) => <span key={skill.name}>{skill.name} · {skill.level}</span>)}</div>
          <div className="profile-source label-mono">Source: {profile.source_filename || "manual profile"}</div>
          {editable && profile.status === "draft" && (
            <button className="btn btn-secondary" type="button" onClick={async () => onChange(await confirmWorkerProfile(profile.member_id))}>
              <CheckCircle2 size={13} /> Confirm this profile
            </button>
          )}
        </>
      )}
    </article>
  );
}
