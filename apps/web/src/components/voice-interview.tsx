"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Keyboard,
  Microphone,
  PaperPlaneTilt,
  SpeakerHigh,
  Stop,
} from "@phosphor-icons/react";

import {
  ApiError,
  mirrorApi,
  uploadVoiceTurn,
  type VoiceTurnResult,
} from "@/lib/api";

type VoiceState =
  | "IDLE"
  | "RECORDING"
  | "UPLOADING"
  | "TRANSCRIBING"
  | "THINKING"
  | "SPEAKING"
  | "ERROR";

type PermissionState = "prompt" | "granted" | "denied";

type RecordingDraft = {
  blob: Blob;
  durationMs: number;
  clientTurnId: string;
};

const stateLabels: Record<VoiceState, string> = {
  IDLE: "Ready",
  RECORDING: "Listening",
  UPLOADING: "Uploading",
  TRANSCRIBING: "Transcribing",
  THINKING: "Thinking",
  SPEAKING: "Mirror is speaking",
  ERROR: "Needs attention",
};

function formatTime(total: number) {
  const safe = Math.max(0, total);
  return `${Math.floor(safe / 60).toString().padStart(2, "0")}:${(safe % 60).toString().padStart(2, "0")}`;
}

function preferredMimeType() {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
  ];
  return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate)) ?? "";
}

export function VoiceInterview({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const recordingStartedRef = useRef(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const thinkingTimerRef = useRef<number | null>(null);
  const redirectTimerRef = useRef<number | null>(null);
  const mountedRef = useRef(false);
  const recordingStartPendingRef = useRef(false);
  const submitInFlightRef = useRef(false);
  const uploadAbortRef = useRef<AbortController | null>(null);
  const deadlineRef = useRef<number | null>(null);

  const [phase, setPhase] = useState("INTRO");
  const [remaining, setRemaining] = useState(0);
  const [question, setQuestion] = useState("");
  const [turnId, setTurnId] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioFailed, setAudioFailed] = useState(false);
  const [voiceState, setVoiceState] = useState<VoiceState>("IDLE");
  const [permission, setPermission] = useState<PermissionState>("prompt");
  const [recording, setRecording] = useState<RecordingDraft | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [showTextFallback, setShowTextFallback] = useState(false);
  const [typedAnswer, setTypedAnswer] = useState("");
  const [closing, setClosing] = useState(false);

  function setRemainingFromServer(seconds: number) {
    const safeSeconds = Math.max(0, seconds);
    deadlineRef.current = Date.now() + safeSeconds * 1000;
    setRemaining(safeSeconds);
  }

  function stopMedia() {
    const recorder = recorderRef.current;
    if (recorder) {
      recorder.ondataavailable = null;
      recorder.onstop = null;
      recorder.onerror = null;
      if (recorder.state !== "inactive") recorder.stop();
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    recorderRef.current = null;
  }

  useEffect(() => {
    mountedRef.current = true;
    let active = true;
    async function load() {
      try {
        const session = await mirrorApi.session(sessionId);
        if (session.status === "COMPLETED" || session.status === "ASSESSING") {
          router.replace(`/app/report/${sessionId}`);
          return;
        }
        if (session.status !== "READY" && session.status !== "ACTIVE") {
          setError("This session is not ready to begin.");
          setVoiceState("ERROR");
          return;
        }
        const result = await mirrorApi.startVoiceInterview(sessionId);
        if (!active) return;
        await presentQuestion(result, true);
      } catch (caught) {
        if (!active) return;
        try {
          const session = await mirrorApi.session(sessionId);
          const fallback = session.status === "READY"
            ? await mirrorApi.startInterview(sessionId)
            : null;
          const turns = fallback ? [] : await mirrorApi.interviewTurns(sessionId);
          const latest = [...turns].reverse().find((turn) => turn.speaker === "INTERVIEWER");
          setQuestion(fallback?.question_text ?? latest?.text ?? "Continue when you are ready.");
          setPhase(fallback?.phase ?? latest?.phase ?? session.phase);
          setRemainingFromServer(fallback?.remaining_time_seconds ?? Math.max(
            0,
            session.total_time_budget_seconds - session.elapsed_seconds,
          ));
          const isClosing = (fallback?.turn_type ?? latest?.turn_type) === "CLOSING";
          setClosing(isClosing);
          setAudioFailed(true);
          setError("Voice playback is unavailable. You can continue with the question shown.");
        } catch {
          setError(caught instanceof ApiError ? caught.message : "Mirror could not load this interview.");
          setVoiceState("ERROR");
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
      mountedRef.current = false;
      uploadAbortRef.current?.abort();
      uploadAbortRef.current = null;
      stopMedia();
      audioRef.current?.pause();
      if (thinkingTimerRef.current) window.clearTimeout(thinkingTimerRef.current);
      if (redirectTimerRef.current) window.clearTimeout(redirectTimerRef.current);
    };
  // The session identity is stable for the lifetime of this route.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router, sessionId]);

  useEffect(() => {
    if (loading) return;
    const timer = window.setInterval(() => {
      if (deadlineRef.current === null) return;
      setRemaining(Math.max(0, Math.ceil((deadlineRef.current - Date.now()) / 1000)));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [loading]);

  async function presentQuestion(result: VoiceTurnResult, autoplay: boolean) {
    if (!mountedRef.current) return;
    setQuestion(result.question_text);
    setPhase(result.phase);
    setRemainingFromServer(result.remaining_time_seconds);
    setTurnId(result.turn_id);
    setAudioUrl(result.audio_url);
    setAudioFailed(result.audio_status === "FAILED");
    const isClosing = result.turn_type === "CLOSING";
    setClosing(isClosing);
    setVoiceState("IDLE");
    if (result.audio_status === "READY" && result.audio_url && autoplay) {
      await playAudio(result.audio_url, isClosing);
    }
  }

  async function playAudio(url = audioUrl, navigateAfter = closing) {
    if (!url || !mountedRef.current) return;
    audioRef.current?.pause();
    const player = audioRef.current ?? new Audio();
    audioRef.current = player;
    player.src = url;
    player.onended = () => {
      if (!mountedRef.current) return;
      setVoiceState("IDLE");
      if (navigateAfter) router.replace(`/app/report/${sessionId}`);
    };
    player.onerror = () => {
      if (!mountedRef.current) return;
      setVoiceState("IDLE");
      setAudioFailed(true);
      setError("Question audio could not be played. The question remains available as text.");
    };
    setVoiceState("SPEAKING");
    try {
      await player.play();
    } catch {
      if (!mountedRef.current) return;
      setVoiceState("IDLE");
      setError("Select Play question to hear Mirror's response.");
    }
  }

  async function startRecording() {
    if (
      recordingStartPendingRef.current
      || closing
      || (voiceState !== "IDLE" && voiceState !== "ERROR")
    ) return;
    recordingStartPendingRef.current = true;
    setError("");
    let acquiredStream: MediaStream | null = null;
    try {
      acquiredStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      if (!mountedRef.current) {
        acquiredStream.getTracks().forEach((track) => track.stop());
        return;
      }
      setPermission("granted");
      streamRef.current = acquiredStream;
      chunksRef.current = [];
      const mimeType = preferredMimeType();
      const recorder = new MediaRecorder(acquiredStream, mimeType ? { mimeType } : undefined);
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const durationMs = Math.max(0, Date.now() - recordingStartedRef.current);
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        stopMedia();
        if (!mountedRef.current) return;
        if (durationMs < 300 || blob.size === 0) {
          setError("That recording was too short. Try again when you are ready.");
          setVoiceState("ERROR");
          return;
        }
        setRecording({ blob, durationMs, clientTurnId: crypto.randomUUID() });
        setVoiceState("IDLE");
      };
      recorder.onerror = () => {
        stopMedia();
        if (!mountedRef.current) return;
        setError("The browser stopped recording unexpectedly. Please try again.");
        setVoiceState("ERROR");
      };
      recordingStartedRef.current = Date.now();
      recorder.start(250);
      setRecording(null);
      setVoiceState("RECORDING");
    } catch (caught) {
      acquiredStream?.getTracks().forEach((track) => track.stop());
      stopMedia();
      if (!mountedRef.current) return;
      const denied = caught instanceof DOMException && (
        caught.name === "NotAllowedError" || caught.name === "SecurityError"
      );
      if (denied) {
        setPermission("denied");
        setShowTextFallback(true);
        setError("Microphone access is blocked. Allow it in browser settings, or type your answer instead.");
      } else {
        setError("Mirror could not start the microphone. Check that another app is not using it.");
      }
      setVoiceState("ERROR");
    } finally {
      recordingStartPendingRef.current = false;
    }
  }

  function stopRecording() {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }

  async function submitRecording() {
    if (
      !recording
      || submitInFlightRef.current
      || (voiceState !== "IDLE" && voiceState !== "ERROR")
    ) return;
    submitInFlightRef.current = true;
    const abortController = new AbortController();
    uploadAbortRef.current = abortController;
    setError("");
    setUploadProgress(0);
    setVoiceState("UPLOADING");
    try {
      const result = await uploadVoiceTurn(
        sessionId,
        recording.blob,
        recording.durationMs,
        recording.clientTurnId,
        setUploadProgress,
        () => {
          if (!mountedRef.current) return;
          setVoiceState("TRANSCRIBING");
          thinkingTimerRef.current = window.setTimeout(() => setVoiceState("THINKING"), 1200);
        },
        abortController.signal,
      );
      if (thinkingTimerRef.current) window.clearTimeout(thinkingTimerRef.current);
      if (!mountedRef.current) return;
      setRecording(null);
      await presentQuestion(result, true);
    } catch (caught) {
      if (thinkingTimerRef.current) window.clearTimeout(thinkingTimerRef.current);
      if (!mountedRef.current || (caught instanceof DOMException && caught.name === "AbortError")) return;
      const apiError = caught instanceof ApiError ? caught : null;
      if (apiError?.code === "TRANSCRIPTION_FAILED") setRecording(null);
      setError(apiError?.message ?? "Mirror could not process that recording. Try again.");
      setVoiceState("ERROR");
    } finally {
      if (uploadAbortRef.current === abortController) uploadAbortRef.current = null;
      submitInFlightRef.current = false;
    }
  }

  async function retryAudio() {
    if (!turnId || busy) return;
    setError("");
    setVoiceState("THINKING");
    try {
      const result = await mirrorApi.retryTurnAudio(turnId);
      if (!mountedRef.current) return;
      await presentQuestion(result, true);
    } catch (caught) {
      if (!mountedRef.current) return;
      setError(caught instanceof ApiError ? caught.message : "Question audio is still unavailable.");
      setVoiceState("ERROR");
    }
  }

  async function submitTextFallback(event: FormEvent) {
    event.preventDefault();
    const text = typedAnswer.trim();
    if (!text || busy || closing) return;
    setError("");
    setVoiceState("THINKING");
    try {
      const result = await mirrorApi.sendTextTurn(sessionId, text, crypto.randomUUID());
      if (!mountedRef.current) return;
      setTypedAnswer("");
      setQuestion(result.question_text);
      setPhase(result.phase);
      setRemainingFromServer(result.remaining_time_seconds);
      setTurnId(null);
      setAudioUrl(null);
      setAudioFailed(true);
      const isClosing = result.turn_type === "CLOSING";
      setClosing(isClosing);
      setVoiceState("IDLE");
      if (isClosing) {
        redirectTimerRef.current = window.setTimeout(() => router.replace(`/app/report/${sessionId}`), 1800);
      }
    } catch (caught) {
      if (!mountedRef.current) return;
      setError(caught instanceof ApiError ? caught.message : "Mirror could not send that answer.");
      setVoiceState("ERROR");
    }
  }

  async function endInterview() {
    if (busy || closing) return;
    stopMedia();
    audioRef.current?.pause();
    setVoiceState("THINKING");
    try {
      await mirrorApi.endInterview(sessionId);
      if (!mountedRef.current) return;
      router.replace(`/app/report/${sessionId}`);
    } catch (caught) {
      if (!mountedRef.current) return;
      setError(caught instanceof ApiError ? caught.message : "Mirror could not end the interview.");
      setVoiceState("ERROR");
    }
  }

  const busy = [
    "RECORDING",
    "UPLOADING",
    "TRANSCRIBING",
    "THINKING",
    "SPEAKING",
  ].includes(voiceState);

  return (
    <main className="shell flex min-h-[calc(100dvh-4rem)] flex-col py-6 sm:py-12">
      <header className="flex items-center justify-between border-b border-[var(--line)] pb-4">
        <p className="display text-xl font-semibold tracking-[-0.03em]">Mirror</p>
        <div className="mono flex gap-3 text-[11px] text-[var(--silver)] sm:gap-5 sm:text-xs">
          <span>{phase.replace("_", " ")}</span>
          <time aria-label={`${remaining} seconds remaining`}>{formatTime(remaining)}</time>
        </div>
      </header>

      <section className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center py-8 sm:py-12">
        <div className="flex items-center justify-between gap-4">
          <p className="mono text-xs uppercase tracking-[0.16em] text-[var(--pulse)]">Interviewer</p>
          <p aria-live="polite" className="text-xs text-[var(--silver)]">{stateLabels[voiceState]}</p>
        </div>
        <h1 aria-live="polite" className="display mt-5 text-3xl font-medium leading-tight tracking-[-0.04em] sm:text-5xl">
          {loading ? "Preparing your first question…" : question}
        </h1>

        <div className="mt-10 border-y border-[var(--line)] py-6 sm:mt-12">
          {closing ? (
            <button type="button" className="button-primary w-full sm:w-auto" onClick={() => router.replace("/app")}>
              Continue
            </button>
          ) : voiceState === "RECORDING" ? (
            <button type="button" className="button-primary w-full sm:w-auto" onClick={stopRecording}>
              <Stop size={19} weight="fill" aria-hidden /> Stop recording
            </button>
          ) : recording ? (
            <div className="flex flex-col gap-3 sm:flex-row">
              <button type="button" className="button-primary" onClick={submitRecording} disabled={busy}>
                <PaperPlaneTilt size={19} aria-hidden /> Submit recording
              </button>
              <button type="button" className="button-secondary" onClick={startRecording} disabled={busy}>
                Record again
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="button-primary w-full sm:w-auto"
              onClick={startRecording}
              disabled={loading || busy || !question}
            >
              <Microphone size={20} aria-hidden /> Start recording
            </button>
          )}

          {voiceState === "UPLOADING" ? (
            <div
              className="mt-4"
              role="progressbar"
              aria-label="Recording upload progress"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={uploadProgress}
            >
              <div className="h-1 overflow-hidden rounded-full bg-[var(--slate)]">
                <div className="h-full bg-[var(--pulse)] transition-[width]" style={{ width: `${uploadProgress}%` }} />
              </div>
              <p className="mono mt-2 text-xs text-[var(--silver)]">{uploadProgress}% uploaded</p>
            </div>
          ) : null}

          {permission === "prompt" ? (
            <p className="mt-4 text-sm leading-6 text-[var(--silver)]">Your browser will ask for microphone access when you start recording.</p>
          ) : null}
          {permission === "denied" ? (
            <p className="mt-4 text-sm leading-6 text-[var(--silver)]">Microphone access is denied. Update this site's permission in your browser settings to use voice.</p>
          ) : null}
          {error ? <p role="alert" className="mt-4 text-sm leading-6 text-[#f1a09a]">{error}</p> : null}

          <div className="mt-5 flex flex-wrap gap-4 text-sm">
            {audioUrl && voiceState !== "SPEAKING" ? (
              <button type="button" className="inline-flex min-h-11 items-center gap-2 text-[var(--silver)] hover:text-[var(--paper)]" onClick={() => playAudio()} disabled={busy}>
                <SpeakerHigh size={18} aria-hidden /> Play question
              </button>
            ) : null}
            {audioFailed && turnId ? (
              <button type="button" className="min-h-11 text-[var(--silver)] underline-offset-4 hover:underline" onClick={retryAudio} disabled={busy}>
                Retry question audio
              </button>
            ) : null}
            <button
              type="button"
              className="inline-flex min-h-11 items-center gap-2 text-[var(--silver)] hover:text-[var(--paper)]"
              onClick={() => setShowTextFallback((value) => !value)}
              disabled={busy || closing}
              aria-pressed={showTextFallback}
            >
              <Keyboard size={18} aria-hidden /> {showTextFallback ? "Hide text answer" : "Type instead"}
            </button>
          </div>
        </div>

        {showTextFallback ? (
          <form className="mt-6" onSubmit={submitTextFallback}>
            <label htmlFor="typed-answer" className="sr-only">Type your answer</label>
            <textarea
              id="typed-answer"
              className="field min-h-32 resize-y leading-7"
              placeholder="Type your answer"
              value={typedAnswer}
              onChange={(event) => setTypedAnswer(event.target.value)}
              maxLength={20_000}
              disabled={busy}
            />
            <button type="submit" className="button-secondary mt-3 w-full sm:w-auto" disabled={busy || !typedAnswer.trim()}>
              Send text answer
            </button>
          </form>
        ) : null}

        <button type="button" className="mt-8 min-h-11 self-start text-sm text-[var(--silver)] underline-offset-4 hover:underline" onClick={endInterview} disabled={busy || closing}>
          End interview
        </button>
      </section>
    </main>
  );
}

