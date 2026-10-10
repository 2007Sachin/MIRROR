import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const component = fs.readFileSync(new URL("../../../../apps/web/src/components/voice-interview.tsx", import.meta.url), "utf8");

test("successful voice join clears stale typing-only mode", () => {
  const joinStart = component.indexOf("async function joinInterview()");
  const joinEnd = component.indexOf("async function connectAnalyser", joinStart);
  assert.ok(joinStart >= 0 && joinEnd > joinStart, "joinInterview function is present");
  const join = component.slice(joinStart, joinEnd);
  const voiceStart = join.indexOf("const result = await mirrorApi.startVoiceInterview(sessionId);");
  const typingReset = join.indexOf("textOnlyRef.current = false;", voiceStart);
  assert.ok(voiceStart >= 0, "voice join calls the voice start endpoint");
  assert.ok(typingReset > voiceStart, "a successful voice join clears typing-only state before the next render");
});

test("typing-only mode keeps the composer available and does not offer cancel", () => {
  const toggleStart = component.indexOf("function toggleTextFallback()");
  const toggleEnd = component.indexOf("async function submitTextFallback", toggleStart);
  assert.ok(toggleStart >= 0 && toggleEnd > toggleStart, "text fallback toggle is present");
  assert.match(component.slice(toggleStart, toggleEnd), /if \(textOnlyRef\.current\)/, "typing-only mode cannot close the composer");
  assert.match(component, /showTextFallback \|\| textOnlyRef\.current/, "typing-only mode always renders the composer");
  assert.match(component, /readOnly=\{textRetryPending\}/, "an ambiguous request keeps the original answer immutable until retry");
  assert.match(component, /!textOnlyRef\.current[^\n]*Cancel/, "typing-only mode does not show a no-op Cancel button");
});

test("a text fallback in voice mode restores audio, while typed-only mode stays on text turns", () => {
  const submitStart = component.indexOf("async function submitTextFallback");
  const submitEnd = component.indexOf("async function retryAudio", submitStart);
  assert.ok(submitStart >= 0 && submitEnd > submitStart, "text submission handler is present");
  const submit = component.slice(submitStart, submitEnd);
  assert.ok(submit.indexOf("mirrorApi.sendTextTurn") < submit.indexOf("if (!textOnlyRef.current)"), "branch follows text answer acknowledgment");
  assert.match(submit, /const voicedResult = await mirrorApi\.startVoiceInterview\(sessionId\)/, "voice-enabled text fallback requests the next voice prompt");
  assert.match(submit, /await presentQuestion\(voicedResult, true\)/, "voice-enabled mode preserves question playback");
  assert.match(submit, /await presentTextQuestion\(result\)/, "typing-only mode can progress from the text response");
});
