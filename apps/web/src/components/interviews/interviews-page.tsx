"use client";

import Link from "next/link";
import { useState } from "react";

import { InterviewForm } from "@/components/interviews/interview-form";
import { RoleTabs } from "@/components/roles/role-tabs";
import { EmptyState, PageAlert, PageHeader, PageLoading, PageShell, Section, usePageData } from "@/components/workspace/page-shell";
import { mirrorApi, type InterviewEvent } from "@/lib/api";
import { interviews as t, roles as rolesCopy } from "@/lib/copy";
import { formatWhen, groupEvents, promptDebrief, roundLabel, timingLabel } from "@/lib/interview-view";

export function InterviewsPage({ roleProfileId }: { roleProfileId: string }) {
  const { state, data, error, reload, setData } = usePageData(
    () => mirrorApi.interviews(roleProfileId),
    t.errors.load,
    [roleProfileId],
  );
  const [removeError, setRemoveError] = useState("");
  const groups = data ? groupEvents(data) : null;

  async function remove(event: InterviewEvent) {
    if (!window.confirm(t.removeConfirm)) return;
    setRemoveError("");
    try {
      await mirrorApi.deleteInterview(event.id);
      setData((data ?? []).filter((item) => item.id !== event.id));
    } catch {
      setRemoveError(t.errors.remove);
    }
  }

  const list = (events: InterviewEvent[]) => (
    <ul className="dh-row-list">
      {events.map((event) => (
        <li key={event.id}>
          <span className="dh-row-main">
            <strong>
              {roundLabel(event)}
              {event.company_label ? ` · ${event.company_label}` : ""}
            </strong>
            <small>
              {formatWhen(event.scheduled_for)}
              {event.timing === "SOON" ? ` · ${timingLabel(event)}` : ""}
            </small>
            {event.has_debrief ? <small>{t.debriefDone}</small> : null}
          </span>
          <span className="dh-row-actions">
            <Link className="dh-text-action" href={`/roles/${roleProfileId}/interviews/${event.id}`}>
              {promptDebrief(event) ? t.debriefPrompt : t.open}
            </Link>
            <button type="button" className="dh-text-action is-quiet" onClick={() => void remove(event)}>
              {t.remove}
            </button>
          </span>
        </li>
      ))}
    </ul>
  );

  return (
    <PageShell>
      <PageHeader eyebrow={rolesCopy.eyebrow} title={t.title} intro={t.intro} back={{ href: "/roles", label: rolesCopy.detail.back }} />
      <RoleTabs roleProfileId={roleProfileId} current="interviews" />

      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}

      {state === "ready" && groups ? (
        <>
          {removeError ? <PageAlert message={removeError} /> : null}
          {!data?.length ? <EmptyState title={t.empty.title} body={t.empty.body} /> : null}
          {groups.upcoming.length ? (
            <Section id="interviews-upcoming" title={t.upcoming}>
              {list(groups.upcoming)}
            </Section>
          ) : null}
          {groups.past.length ? (
            <Section id="interviews-past" title={t.past}>
              {list(groups.past)}
            </Section>
          ) : null}
          <AddInterview roleProfileId={roleProfileId} onAdded={(event) => setData([...(data ?? []), event])} />
        </>
      ) : null}
    </PageShell>
  );
}

function AddInterview({ roleProfileId, onAdded }: { roleProfileId: string; onAdded: (event: InterviewEvent) => void }) {
  // Remounting the form after each add clears its fields.
  const [formKey, setFormKey] = useState(0);
  const [status, setStatus] = useState("");
  return (
    <Section id="interviews-add" title={t.add.title}>
      <InterviewForm
        key={formKey}
        submitLabel={t.add.submit}
        savingLabel={t.add.saving}
        errorLabel={t.errors.add}
        onSubmit={async (value) => {
          setStatus("");
          onAdded(await mirrorApi.createInterview(roleProfileId, value));
          setFormKey((key) => key + 1);
          setStatus(t.add.added);
        }}
      />
      <p className="dh-fine-print" role="status" aria-live="polite" style={status ? undefined : { margin: 0 }}>
        {status}
      </p>
    </Section>
  );
}
