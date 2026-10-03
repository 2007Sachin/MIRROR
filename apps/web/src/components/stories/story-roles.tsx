"use client";

import { Plus } from "@phosphor-icons/react";
import { FormEvent, useEffect, useState } from "react";

import { PageAlert, PageLoading, Section } from "@/components/workspace/page-shell";
import { ApiError, mirrorApi, type RoleProfileSummary, type Story, type StoryRoleFraming } from "@/lib/api";
import { stories as copy } from "@/lib/copy";
import { roleLabel, themesFrom } from "@/lib/story-view";

const t = copy.roles;

type Load =
  | { state: "loading" }
  | { state: "error" }
  | { state: "ready"; framings: StoryRoleFraming[]; roles: RoleProfileSummary[] };

type Editing = { roleProfileId: string; themes: string; emphasis: string; isNew: boolean };

/**
 * The roles one story is useful for. Adding a role never copies the story: it records the
 * exact role, any extra themes for that role, and an optional note on what to emphasize.
 */
export function StoryRoles({ story }: { story: Story }) {
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [editing, setEditing] = useState<Editing | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const archived = Boolean(story.archived_at);

  useEffect(() => {
    let live = true;
    setLoad({ state: "loading" });
    Promise.all([mirrorApi.storyRoles(story.id), mirrorApi.roles()])
      .then(([framings, roles]) => { if (live) setLoad({ state: "ready", framings, roles }); })
      .catch(() => { if (live) setLoad({ state: "error" }); });
    return () => { live = false; };
  }, [story.id, attempt]);

  if (load.state === "loading") return <Section id="story-roles" title={t.title} body={t.intro}><PageLoading /></Section>;
  if (load.state === "error") {
    return (
      <Section id="story-roles" title={t.title} body={t.intro}>
        <PageAlert message={copy.errors.roles} onRetry={() => setAttempt((value) => value + 1)} />
      </Section>
    );
  }

  const { framings, roles } = load;
  const framed = new Set(framings.map((item) => item.role_profile_id));
  const available = roles.filter((role) => !framed.has(role.id));
  const label = (id: string) => roleLabel(id, roles);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing?.roleProfileId || load.state !== "ready") return;
    setBusy(true);
    setActionError("");
    setNotice("");
    try {
      const saved = await mirrorApi.setStoryRole(story.id, editing.roleProfileId, {
        themes: themesFrom(editing.themes),
        emphasis: editing.emphasis.trim() || null,
      });
      const rest = load.framings.filter((item) => item.role_profile_id !== saved.role_profile_id);
      setLoad({ ...load, framings: [...rest, saved] });
      setNotice(editing.isNew ? t.added(label(saved.role_profile_id)) : t.saved);
      setEditing(null);
    } catch (reason) {
      setActionError(reason instanceof ApiError ? reason.message : copy.errors.roleSave);
    } finally {
      setBusy(false);
    }
  }

  async function remove(framing: StoryRoleFraming) {
    if (load.state !== "ready") return;
    setBusy(true);
    setActionError("");
    setNotice("");
    try {
      await mirrorApi.removeStoryRole(story.id, framing.role_profile_id);
      setLoad({ ...load, framings: load.framings.filter((item) => item.id !== framing.id) });
      setNotice(t.removed(label(framing.role_profile_id)));
      if (editing?.roleProfileId === framing.role_profile_id) setEditing(null);
    } catch (reason) {
      setActionError(reason instanceof ApiError ? reason.message : copy.errors.roleRemove);
    } finally {
      setBusy(false);
    }
  }

  const form = editing ? (
    <form className="dh-form is-wide dh-story-role-form" onSubmit={save} aria-busy={busy}>
      {editing.isNew ? (
        <label>
          <span>{t.choose}</span>
          <select
            className="field"
            value={editing.roleProfileId}
            onChange={(event) => setEditing({ ...editing, roleProfileId: event.target.value })}
            disabled={busy}
            required
          >
            {available.map((role) => (
              <option key={role.id} value={role.id}>{label(role.id)}</option>
            ))}
          </select>
        </label>
      ) : null}
      <label>
        <span>{t.themesLabel}</span>
        <input className="field" value={editing.themes} onChange={(event) => setEditing({ ...editing, themes: event.target.value })} disabled={busy} />
        <small>{t.themesHint}</small>
      </label>
      <label>
        <span>{t.emphasisLabel}</span>
        <textarea className="field" rows={2} maxLength={500} value={editing.emphasis} onChange={(event) => setEditing({ ...editing, emphasis: event.target.value })} disabled={busy} />
        <small>{t.emphasisHint}</small>
      </label>
      <div className="dh-action-row">
        <button className="dh-primary-action" type="submit" disabled={busy || !editing.roleProfileId}>{busy ? t.saving : t.save}</button>
        <button className="dh-primary-action is-quiet" type="button" onClick={() => setEditing(null)} disabled={busy}>{t.cancel}</button>
      </div>
    </form>
  ) : null;

  return (
    <Section id="story-roles" title={t.title} body={t.intro}>
      {framings.length ? (
        <ul className="dh-row-list" aria-label={t.title}>
          {framings.map((framing) => (
            <li key={framing.id} className="dh-story-role-row">
              <span className="dh-row-main">
                <strong>{label(framing.role_profile_id)}</strong>
                <small>{framing.themes.length ? framing.themes.join(", ") : t.noExtraThemes}</small>
                {framing.emphasis ? <small>{t.emphasisShown(framing.emphasis)}</small> : null}
              </span>
              {archived ? null : (
                <span className="dh-row-actions">
                  <button
                    type="button"
                    className="dh-text-action"
                    disabled={busy}
                    onClick={() => setEditing({ roleProfileId: framing.role_profile_id, themes: framing.themes.join(", "), emphasis: framing.emphasis ?? "", isNew: false })}
                  >
                    {t.edit}
                  </button>
                  <button type="button" className="dh-text-action is-quiet" disabled={busy} onClick={() => void remove(framing)}>
                    {t.remove}
                  </button>
                </span>
              )}
              {editing && !editing.isNew && editing.roleProfileId === framing.role_profile_id ? form : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="dh-fine-print">{t.none}</p>
      )}

      {archived ? <p className="dh-fine-print">{t.archived}</p> : null}
      {!archived && editing?.isNew ? form : null}
      {!archived && !editing ? (
        available.length ? (
          <div className="dh-action-row">
            <button
              type="button"
              className="dh-text-action"
              disabled={busy}
              onClick={() => { setNotice(""); setEditing({ roleProfileId: available[0].id, themes: "", emphasis: "", isNew: true }); }}
            >
              <Plus size={15} aria-hidden="true" /> {t.add}
            </button>
          </div>
        ) : (
          <p className="dh-fine-print">{roles.length ? t.allLinked : t.noRoles}</p>
        )
      ) : null}
      {notice ? <p className="dh-notice" role="status">{notice}</p> : null}
      {actionError ? <PageAlert message={actionError} /> : null}
    </Section>
  );
}
