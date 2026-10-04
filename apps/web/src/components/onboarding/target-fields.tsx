"use client";

import { targetCopy } from "@/lib/copy-targets";
import type { LevelKey } from "@/lib/api-targets";

const t = targetCopy.setup;

export type CountryKey = "in" | "other" | "not_sure";
export type TargetChoice = { company: string; family: boolean; level: LevelKey; country: CountryKey };

/** The role name looks like a Software Development Engineer role (confirmed by the person, never assumed). */
export function looksLikeSde(role: string) {
  return /\b(sde|software\s+(development|dev)\s+engineer|software\s+engineer)\b/i.test(role);
}

/** Body for POST /api/v1/targets, or null when there is nothing to save (no company or not an SDE role). */
export function targetBody(roleProfileId: string, choice: TargetChoice) {
  const company = choice.company.trim();
  if (!company || !choice.family) return null;
  const place = choice.country === "in"
    ? { geography: "in", geography_label: "India" }
    : choice.country === "other"
      ? { geography: "other", geography_label: "Somewhere else" }
      : {};
  return { role_profile_id: roleProfileId, company, level: choice.level, ...place };
}

/** Optional "where and what level" fields inside the role step. Skipping them keeps today's behaviour. */
export function TargetFields({
  value,
  onChange,
  open,
  onToggle,
  disabled,
}: {
  value: TargetChoice;
  onChange: (next: TargetChoice) => void;
  open: boolean;
  onToggle: (open: boolean) => void;
  disabled: boolean;
}) {
  const set = (patch: Partial<TargetChoice>) => onChange({ ...value, ...patch });
  return (
    <details className="ob-target" open={open} onToggle={(event) => onToggle(event.currentTarget.open)}>
      <summary>{t.summary}</summary>
      <p className="op-muted">{t.intro}</p>
      <div className="ob-target-fields">
        <label>
          <span>{t.company}</span>
          <input className="field" value={value.company} onChange={(event) => set({ company: event.target.value })} maxLength={120} disabled={disabled} />
        </label>
        <label className="ob-target-check">
          <input type="checkbox" checked={value.family} onChange={(event) => set({ family: event.target.checked })} disabled={disabled} aria-describedby="ob-family-help" />
          <span>{t.familyConfirm}</span>
        </label>
        <p id="ob-family-help" className="op-muted">{t.familyHelp}</p>
        <fieldset className="ob-target-radios" disabled={disabled} aria-describedby="ob-level-help">
          <legend id="ob-level-legend" tabIndex={-1}>{t.level}</legend>
          {t.levelOptions.map((option) => (
            <label key={option.key}>
              <input type="radio" name="target-level" value={option.key} checked={value.level === option.key} onChange={() => set({ level: option.key as LevelKey })} />
              <span>{option.label}</span>
            </label>
          ))}
          <p id="ob-level-help" className="op-muted">{t.levelHelp}</p>
        </fieldset>
        <fieldset className="ob-target-radios" disabled={disabled}>
          <legend>{t.country}</legend>
          {t.countryOptions.map((option) => (
            <label key={option.key}>
              <input type="radio" name="target-country" value={option.key} checked={value.country === option.key} onChange={() => set({ country: option.key as CountryKey })} />
              <span>{option.label}</span>
            </label>
          ))}
        </fieldset>
      </div>
    </details>
  );
}
