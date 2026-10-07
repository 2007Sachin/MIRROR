"use client";

import { ROLE_FAMILIES, familyHint, familyLabel, familyLevels, targetCopy } from "@/lib/copy-targets";
import type { LevelKey } from "@/lib/api-targets";

const t = targetCopy.setup;

export type CountryKey = "in" | "other" | "not_sure";
/** `family` is a role-family key the person confirmed, or null for "Something else" (no target). */
export type TargetChoice = { company: string; family: string | null; level: LevelKey; country: CountryKey };

/** The role family a role name hints at (confirmed by the person, never assumed). */
export function suggestedFamily(role: string): string | null {
  return familyHint(role);
}

/** Body for POST /api/v1/targets, or null when there is nothing to save (no company or no role family). */
export function targetBody(roleProfileId: string, choice: TargetChoice) {
  const company = choice.company.trim();
  if (!company || !choice.family) return null;
  const level = familyLevels(choice.family).some((option) => option.key === choice.level) ? choice.level : "not_sure";
  const place = choice.country === "in"
    ? { geography: "in", geography_label: "India" }
    : choice.country === "other"
      ? { geography: "other", geography_label: "Somewhere else" }
      : {};
  return { role_profile_id: roleProfileId, company, role_family: choice.family, level, ...place };
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
  const levels = familyLevels(value.family);
  return (
    <details className="ob-target" open={open} onToggle={(event) => onToggle(event.currentTarget.open)}>
      <summary>{t.summary}</summary>
      <p className="op-muted">{t.intro}</p>
      <div className="ob-target-fields">
        <label>
          <span>{t.company}</span>
          <input className="field" value={value.company} onChange={(event) => set({ company: event.target.value })} maxLength={120} disabled={disabled} />
        </label>
        <fieldset className="ob-target-radios" disabled={disabled} aria-describedby="ob-family-help">
          <legend>{t.family}</legend>
          {ROLE_FAMILIES.map((option) => (
            <label key={option.key}>
              <input type="radio" name="target-family" value={option.key} checked={value.family === option.key} onChange={() => set({ family: option.key, level: "not_sure" })} />
              <span>{familyLabel(option.key)}</span>
            </label>
          ))}
          <label>
            <input type="radio" name="target-family" value="" checked={value.family === null} onChange={() => set({ family: null, level: "not_sure" })} />
            <span>{t.familyNone}</span>
          </label>
          <p id="ob-family-help" className="op-muted">{t.familyHelp}</p>
        </fieldset>
        {levels.length > 0 && (
          <fieldset className="ob-target-radios" disabled={disabled} aria-describedby="ob-level-help">
            <legend id="ob-level-legend" tabIndex={-1}>{t.level}</legend>
            {levels.map((option) => (
              <label key={option.key}>
                <input type="radio" name="target-level" value={option.key} checked={value.level === option.key} onChange={() => set({ level: option.key })} />
                <span>{option.label}</span>
              </label>
            ))}
            <p id="ob-level-help" className="op-muted">{t.levelHelp}</p>
          </fieldset>
        )}
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
