"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader } from "@/components/loader";
import { loading, voiceRoom } from "@/lib/copy";
import { getSupabaseBrowserClient } from "@/lib/supabase";
import {
  Keyboard,
  Microphone,
  MicrophoneSlash,
  SpeakerHigh,
  SpeakerSlash,
  SpinnerGap,
  X,
} from "@phosphor-icons/react";

import {
  ApiError,
  mirrorApi,
  pauseOnPageExit,
  type PracticeMode,
  uploadVoiceTurn,
  type PublicInterviewTurn,
  type VoiceTurnResult,
} from "@/lib/api";
import { lifecycleCopy } from "@/lib/copy-lifecycle";
import { useLifecycle } from "@/lib/use-lifecycle";

type RoomState =
  | "PREPARING"
  | "PREJOIN"
  | "CHECKING_MIC"
  | "CONNECTING"
  | "INTERVIEWER_SPEAKING"
  | "LISTENING"
  | "CANDIDATE_SPEAKING"
  | "PROCESSING"
  | "PAUSED"
  | "ERROR"
  | "COMPLETE";

type PermissionState = "prompt" | "granted" | "denied" | "unavailable";
type CaptionSupport = "checking" | "available" | "unavailable";
type RoomErrorKind = "AUTH" | "NETWORK" | "MIC" | "TRANSCRIPTION" | "TURN" | "SESSION" | "COMPLETION";

type LiveSpeechResult = ArrayLike<{ transcript: string }> & { isFinal: boolean };
type LiveSpeechEvent = Event & {
  resultIndex: number;
  results: ArrayLike<LiveSpeechResult>;
};
type LiveSpeechErrorEvent = Event & { error: string };

interface LiveSpeechRecognition {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: ((event: Event) => void) | null;
  onresult: ((event: LiveSpeechEvent) => void) | null;
  onerror: ((event: LiveSpeechErrorEvent) => void) | null;
  onend: ((event: Event) => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

type SpeechRecognitionWindow = Window & {
  SpeechRecognition?: new () => LiveSpeechRecognition;
  webkitSpeechRecognition?: new () => LiveSpeechRecognition;
};

const VOICE_START_THRESHOLD = 0.032;
const VOICE_CONTINUE_THRESHOLD = 0.018;
const SPEECH_CONFIRMATION_MS = 220;
// How long a student may stay quiet before the answer counts as finished. Students pause to
// think, so this is generous; set NEXT_PUBLIC_VOICE_SILENCE_MS to change it.
const configuredSilence = Number(process.env.NEXT_PUBLIC_VOICE_SILENCE_MS);
const END_OF_TURN_SILENCE_MS = Number.isFinite(configuredSilence) && configuredSilence >= 800 ? configuredSilence : 2500;
const MINIMUM_TURN_MS = 650;
const MAXIMUM_TURN_MS = 120_000;

const stateLabels: Record<RoomState, string> = {
  PREPARING: "Preparing the room",
  PREJOIN: "Ready to join",
  CHECKING_MIC: "Checking your microphone",
  CONNECTING: "Joining the conversation",
  INTERVIEWER_SPEAKING: "Mirror is speaking",
  LISTENING: "Listening",
  CANDIDATE_SPEAKING: "You are speaking",
  PROCESSING: "Mirror is considering your answer",
  PAUSED: "Microphone muted",
  ERROR: "Needs a moment",
  COMPLETE: "Conversation complete",
};

const practiceLabels: Record<PracticeMode, string> = {
  FULL_INTERVIEW: "Full interview",
  FOCUSED_PRACTICE: "Focused practice",
  QUICK_DRILL: "Quick drill",
};

function formatTime(total: number) {
  const safe = Math.max(0, total);
  return `${Math.floor(safe / 60).toString().padStart(2, "0")}:${(safe % 60).toString().padStart(2, "0")}`;
}

function preferredMimeType() {
  if (typeof MediaRecorder === "undefined") return "";
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
  ];
  return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate)) ?? "";
}

function liveSpeechConstructor() {
  if (typeof window === "undefined") return undefined;
  const speechWindow = window as SpeechRecognitionWindow;
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
}

function speakerName(speaker: PublicInterviewTurn["speaker"]) {
  return speaker === "INTERVIEWER" ? "Mirror" : "You";
}

export function VoiceInterview({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const recognitionRef = useRef<LiveSpeechRecognition | null>(null);
  const recognitionActiveRef = useRef(false);
  const recognitionShouldRunRef = useRef(false);
  const recognitionRestartTimerRef = useRef<number | null>(null);
  const captionsEnabledRef = useRef(true);
  const vadFrameRef = useRef<number | null>(null);
  const meterRef = useRef<HTMLDivElement | null>(null);
  const recordingStartedRef = useRef(0);
  const possibleSpeechStartedRef = useRef<number | null>(null);
  const silenceStartedRef = useRef<number | null>(null);
  const hasSpeechRef = useRef(false);
  const discardCaptureRef = useRef(false);
  const mountedRef = useRef(false);
  const joinedRef = useRef(false);
  const mutedRef = useRef(false);
  const closingRef = useRef(false);
  const accessTokenRef = useRef<string | undefined>(undefined);
  const [stepAway, setStepAway] = useState<"closed" | "menu" | "confirm">("closed");
  const [savingDraft, setSavingDraft] = useState(false);
  const [welcomeLine, setWelcomeLine] = useState<string | null>(null);
  const roomStateRef = useRef<RoomState>("PREPARING");
  const submitInFlightRef = useRef(false);
  const completionInFlightRef = useRef(false);
  const pendingVoiceRef = useRef<{ blob: Blob; durationMs: number; clientTurnId: string } | null>(null);
  const uploadAbortRef = useRef<AbortController | null>(null);
  const redirectTimerRef = useRef<number | null>(null);
  const deadlineRef = useRef<number | null>(null);

  const [phase, setPhase] = useState("INTRO");
  const [targetRole, setTargetRole] = useState("");
  const [practiceMode, setPracticeMode] = useState<PracticeMode>("FULL_INTERVIEW");
  const [remaining, setRemaining] = useState(0);
  const [question, setQuestion] = useState("");
  const [turnId, setTurnId] = useState<string | null>(null);
  // The opening turn is stored as "<spoken welcome>\n\n<first question>" so the
  // welcome is voiced and recorded with the turn. Split it for display only.
  const { greeting, questionBody } = useMemo(() => {
    const break_ = question.indexOf("\n\n");
    if (break_ === -1) return { greeting: "", questionBody: question };
    return {
      greeting: question.slice(0, break_).trim(),
      questionBody: question.slice(break_ + 2).trim(),
    };
  }, [question]);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioFailed, setAudioFailed] = useState(false);
  const [roomState, setRoomState] = useState<RoomState>("PREPARING");
  const [permission, setPermission] = useState<PermissionState>("prompt");
  const [joined, setJoined] = useState(false);
  const [muted, setMuted] = useState(false);
  const [error, setError] = useState("");
  const [errorKind, setErrorKind] = useState<RoomErrorKind | null>(null);
  const [showTextFallback, setShowTextFallback] = useState(false);
  const [typedAnswer, setTypedAnswer] = useState("");
  const [closing, setClosing] = useState(false);
  const [transcript, setTranscript] = useState<PublicInterviewTurn[]>([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [liveCaption, setLiveCaption] = useState("");
  const [captionsEnabled, setCaptionsEnabled] = useState(true);
  const [captionSupport, setCaptionSupport] = useState<CaptionSupport>("checking");

  function transition(next: RoomState) {
    roomStateRef.current = next;
    setRoomState(next);
  }

  function setRemainingFromServer(seconds: number) {
    const safeSeconds = Math.max(0, seconds);
    deadlineRef.current = Date.now() + safeSeconds * 1000;
    setRemaining(safeSeconds);
  }

  async function refreshTranscript() {
    try {
      const turns = await mirrorApi.interviewTurns(sessionId);
      if (mountedRef.current) setTranscript(turns);
    } catch {
      // Conversation can continue if the optional transcript panel cannot refresh.
    }
  }

  function stopVad() {
    if (vadFrameRef.current !== null) cancelAnimationFrame(vadFrameRef.current);
    vadFrameRef.current = null;
    meterRef.current?.style.setProperty("--voice-level", "0");
  }

  function configureLiveTranscription() {
    if (recognitionRef.current) return recognitionRef.current;
    const Recognition = liveSpeechConstructor();
    if (!Recognition) {
      setCaptionSupport("unavailable");
      return null;
    }

    const recognition = new Recognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = navigator.language || "en-US";
    recognition.onstart = () => {
      recognitionActiveRef.current = true;
    };
    recognition.onresult = (event) => {
      const fragments: string[] = [];
      for (let index = 0; index < event.results.length; index += 1) {
        const fragment = event.results[index]?.[0]?.transcript?.trim();
        if (fragment) fragments.push(fragment);
      }
      const nextCaption = fragments.join(" ").replace(/\s+/g, " ").trim();
      if (mountedRef.current && nextCaption) setLiveCaption(nextCaption);
    };
    recognition.onerror = (event) => {
      recognitionActiveRef.current = false;
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        recognitionShouldRunRef.current = false;
        if (mountedRef.current) setCaptionSupport("unavailable");
      }
    };
    recognition.onend = () => {
      recognitionActiveRef.current = false;
      if (
        !recognitionShouldRunRef.current
        || !captionsEnabledRef.current
        || !mountedRef.current
      ) return;
      recognitionRestartTimerRef.current = window.setTimeout(() => {
        recognitionRestartTimerRef.current = null;
        startLiveTranscription(false);
      }, 180);
    };
    recognitionRef.current = recognition;
    setCaptionSupport("available");
    return recognition;
  }

  function startLiveTranscription(clearCaption = true) {
    if (!captionsEnabledRef.current) return;
    const recognition = configureLiveTranscription();
    if (!recognition) return;
    recognitionShouldRunRef.current = true;
    if (clearCaption) setLiveCaption("");
    if (recognitionActiveRef.current) return;
    try {
      recognition.start();
    } catch {
      if (recognitionRestartTimerRef.current !== null) {
        window.clearTimeout(recognitionRestartTimerRef.current);
      }
      recognitionRestartTimerRef.current = window.setTimeout(() => {
        recognitionRestartTimerRef.current = null;
        if (recognitionShouldRunRef.current) startLiveTranscription(false);
      }, 220);
    }
  }

  function stopLiveTranscription(clearCaption: boolean) {
    recognitionShouldRunRef.current = false;
    if (recognitionRestartTimerRef.current !== null) {
      window.clearTimeout(recognitionRestartTimerRef.current);
      recognitionRestartTimerRef.current = null;
    }
    const recognition = recognitionRef.current;
    if (recognitionActiveRef.current && recognition) {
      try {
        if (clearCaption) recognition.abort();
        else recognition.stop();
      } catch {
        // The browser may already be closing this recognition session.
      }
    }
    recognitionActiveRef.current = false;
    if (clearCaption) setLiveCaption("");
  }

  function stopCapture(discard: boolean) {
    stopVad();
    stopLiveTranscription(discard);
    discardCaptureRef.current = discard;
    const recorder = recorderRef.current;
    recorderRef.current = null;
    if (recorder?.state === "recording") recorder.stop();
  }

  function releaseMedia() {
    stopCapture(true);
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    analyserRef.current?.disconnect();
    analyserRef.current = null;
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      void audioContextRef.current.close();
    }
    audioContextRef.current = null;
    recognitionRef.current = null;
  }

  useEffect(() => {
    mountedRef.current = true;
    let active = true;

    async function prepareRoom() {
      setCaptionSupport(liveSpeechConstructor() ? "available" : "unavailable");
      try {
        const session = await mirrorApi.session(sessionId);
        if (!active) return;
        setTargetRole(session.target_role);
        setPracticeMode(session.practice_mode ?? "FULL_INTERVIEW");
        if (session.status === "COMPLETED") {
          transition("COMPLETE");
          return;
        }
        if (session.status === "ASSESSING") {
          transition("COMPLETE");
          return;
        }
        if (session.status !== "READY" && session.status !== "ACTIVE") {
          setError("This room isn't ready yet. Please try again in a moment.");
          transition("ERROR");
          return;
        }
        setPhase(session.phase);
        setRemainingFromServer(
          Math.max(0, session.total_time_budget_seconds - session.elapsed_seconds),
        );
        if (session.status === "ACTIVE") {
          await refreshTranscript();
          transition("PREJOIN");
        } else {
          transition("PREJOIN");
        }
      } catch (caught) {
        if (!active) return;
        setError(
          caught instanceof ApiError
            ? caught.message
            : "We couldn't get this room ready just now. Please try again in a moment.",
        );
        transition("ERROR");
      }
    }

    void prepareRoom();
    return () => {
      active = false;
      mountedRef.current = false;
      uploadAbortRef.current?.abort();
      audioRef.current?.pause();
      releaseMedia();
      if (redirectTimerRef.current) window.clearTimeout(redirectTimerRef.current);
    };
    // The session identity is stable for the lifetime of this route.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router, sessionId]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (deadlineRef.current === null) return;
      setRemaining(Math.max(0, Math.ceil((deadlineRef.current - Date.now()) / 1000)));
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  async function presentQuestion(result: VoiceTurnResult, autoplay: boolean) {
    if (!mountedRef.current) return;
    setQuestion(result.question_text);
    setPhase(result.phase);
    setRemainingFromServer(result.remaining_time_seconds);
    setTurnId(result.turn_id);
    setAudioUrl(result.audio_url);
    setAudioFailed(result.audio_status === "FAILED");
    const isClosing = result.turn_type === "CLOSING";
    closingRef.current = isClosing;
    setClosing(isClosing);

    if (autoplay && joinedRef.current && result.audio_status === "READY" && result.audio_url) {
      await playQuestion(result.audio_url, isClosing);
      return;
    }
    if (isClosing) {
      transition("COMPLETE");
      redirectTimerRef.current = window.setTimeout(
        () => void completeInterview(),
        1800,
      );
      return;
    }
    if (joinedRef.current && !mutedRef.current) beginListening();
    else transition(joinedRef.current ? "PAUSED" : "PREJOIN");
  }

  async function playQuestion(url = audioUrl, navigateAfter = closingRef.current) {
    if (!url || !mountedRef.current) return;
    stopCapture(true);
    const player = audioRef.current ?? new Audio();
    audioRef.current = player;
    player.pause();
    player.src = url;
    player.onended = () => {
      if (!mountedRef.current) return;
      if (navigateAfter) {
        transition("COMPLETE");
        redirectTimerRef.current = window.setTimeout(
          () => void completeInterview(),
          900,
        );
      } else if (mutedRef.current) {
        transition("PAUSED");
      } else {
        beginListening();
      }
    };
    player.onerror = () => {
      if (!mountedRef.current) return;
      setAudioFailed(true);
      setError("Mirror's voice isn't available right now. You can still read the question and answer as usual.");
      if (navigateAfter) void completeInterview();
      else if (!mutedRef.current) beginListening();
    };
    transition("INTERVIEWER_SPEAKING");
    try {
      await player.play();
    } catch {
      if (!mountedRef.current) return;
      setError("Select Replay question to hear Mirror.");
      if (navigateAfter) void completeInterview();
      else if (!mutedRef.current) beginListening();
    }
  }

  function monitorVoice() {
    const analyser = analyserRef.current;
    if (!analyser || !recorderRef.current) return;
    const samples = new Uint8Array(analyser.fftSize);

    const sample = () => {
      const recorder = recorderRef.current;
      if (!analyserRef.current || !recorder || recorder.state !== "recording") return;
      analyserRef.current.getByteTimeDomainData(samples);
      let sum = 0;
      for (const value of samples) {
        const normalized = (value - 128) / 128;
        sum += normalized * normalized;
      }
      const rms = Math.sqrt(sum / samples.length);
      meterRef.current?.style.setProperty(
        "--voice-level",
        Math.min(1, rms * 10).toFixed(3),
      );
      const now = performance.now();

      if (!hasSpeechRef.current) {
        if (rms >= VOICE_START_THRESHOLD) {
          possibleSpeechStartedRef.current ??= now;
          if (now - possibleSpeechStartedRef.current >= SPEECH_CONFIRMATION_MS) {
            hasSpeechRef.current = true;
            silenceStartedRef.current = null;
            transition("CANDIDATE_SPEAKING");
          }
        } else {
          possibleSpeechStartedRef.current = null;
        }
      } else if (rms < VOICE_CONTINUE_THRESHOLD) {
        silenceStartedRef.current ??= now;
        if (
          now - silenceStartedRef.current >= END_OF_TURN_SILENCE_MS
          && now - recordingStartedRef.current >= MINIMUM_TURN_MS
        ) {
          stopCapture(false);
          return;
        }
      } else {
        silenceStartedRef.current = null;
        if (roomStateRef.current !== "CANDIDATE_SPEAKING") {
          transition("CANDIDATE_SPEAKING");
        }
      }

      if (
        hasSpeechRef.current
        && now - recordingStartedRef.current >= MAXIMUM_TURN_MS
      ) {
        stopCapture(false);
        return;
      }
      vadFrameRef.current = requestAnimationFrame(sample);
    };

    vadFrameRef.current = requestAnimationFrame(sample);
  }

  function beginListening() {
    if (
      !mountedRef.current
      || !joinedRef.current
      || mutedRef.current
      || closingRef.current
      || submitInFlightRef.current
      || !streamRef.current
      || recorderRef.current
    ) return;

    chunksRef.current = [];
    discardCaptureRef.current = false;
    hasSpeechRef.current = false;
    possibleSpeechStartedRef.current = null;
    silenceStartedRef.current = null;
    const mimeType = preferredMimeType();
    const recorder = new MediaRecorder(
      streamRef.current,
      mimeType ? { mimeType } : undefined,
    );
    recorderRef.current = recorder;
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };
    recorder.onerror = () => {
      recorderRef.current = null;
      stopVad();
      if (!mountedRef.current) return;
      setError("Your microphone paused unexpectedly. Select the microphone to reconnect.");
      transition("ERROR");
    };
    recorder.onstop = () => {
      const durationMs = Math.max(0, performance.now() - recordingStartedRef.current);
      const hadSpeech = hasSpeechRef.current;
      const discarded = discardCaptureRef.current;
      const blob = new Blob(chunksRef.current, {
        type: recorder.mimeType || "audio/webm",
      });
      chunksRef.current = [];
      if (!mountedRef.current || discarded) return;
      if (!hadSpeech || durationMs < MINIMUM_TURN_MS || blob.size === 0) {
        transition(mutedRef.current ? "PAUSED" : "LISTENING");
        if (!mutedRef.current) window.setTimeout(beginListening, 120);
        return;
      }
      void submitVoice(blob, Math.round(durationMs), crypto.randomUUID());
    };
    recordingStartedRef.current = performance.now();
    recorder.start(250);
    transition("LISTENING");
    startLiveTranscription();
    monitorVoice();
  }

  async function submitVoice(blob: Blob, durationMs: number, clientTurnId: string) {
    if (submitInFlightRef.current) return;
    submitInFlightRef.current = true;
    const abortController = new AbortController();
    uploadAbortRef.current = abortController;
    setError("");
    setErrorKind(null);
    pendingVoiceRef.current = { blob, durationMs, clientTurnId };
    setUploadProgress(0);
    transition("PROCESSING");
    try {
      const result = await uploadVoiceTurn(
        sessionId,
        blob,
        durationMs,
        clientTurnId,
        setUploadProgress,
        () => undefined,
        abortController.signal,
      );
      if (!mountedRef.current) return;
      await refreshTranscript();
      pendingVoiceRef.current = null;
      setLiveCaption("");
      submitInFlightRef.current = false;
      await presentQuestion(result, true);
    } catch (caught) {
      if (!mountedRef.current || (caught instanceof DOMException && caught.name === "AbortError")) return;
      const apiError = caught instanceof ApiError ? caught : null;
      setErrorKind(apiError?.status === 401 ? "AUTH" : apiError?.code === "TRANSCRIPTION_FAILED" ? "TRANSCRIPTION" : navigator.onLine ? "TURN" : "NETWORK");
      if (apiError?.code === "TRANSCRIPTION_FAILED") pendingVoiceRef.current = null;
      setError(
        apiError?.code === "TRANSCRIPTION_FAILED"
          ? "I couldn't hear that clearly. When you're ready, say your answer again."
          : apiError?.message ?? "The conversation was interrupted. Whenever you're ready, please try that answer again.",
      );
      setLiveCaption("");
      transition("ERROR");
    } finally {
      if (uploadAbortRef.current === abortController) uploadAbortRef.current = null;
      submitInFlightRef.current = false;
    }
  }

  async function joinInterview() {
    if (roomStateRef.current === "CONNECTING" || roomStateRef.current === "CHECKING_MIC") return;
    setError("");
    transition("CONNECTING");
    let stream: MediaStream | null = null;
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
        throw new Error("This browser can't use voice. You can type your answer instead.");
      }
      stream = streamRef.current ?? await requestMicrophone();
      if (!mountedRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      stopVad();
      await connectAnalyser(stream);
      configureLiveTranscription();
      joinedRef.current = true;
      setJoined(true);
      setPermission("granted");
      const result = await mirrorApi.startVoiceInterview(sessionId);
      await refreshTranscript();
      await playWelcome(result);
      await presentQuestion(result, true);
    } catch (caught) {
      stream?.getTracks().forEach((track) => track.stop());
      releaseMedia();
      joinedRef.current = false;
      setJoined(false);
      const denied = caught instanceof DOMException
        && (caught.name === "NotAllowedError" || caught.name === "SecurityError");
      if (denied) {
        setPermission("denied");
        setShowTextFallback(true);
        setErrorKind("MIC");
        setError("Microphone access is blocked. Allow it in browser settings to join by voice.");
      } else {
        setPermission(caught instanceof ApiError ? "granted" : "unavailable");
        setErrorKind(caught instanceof ApiError && caught.status === 401 ? "AUTH" : "MIC");
        setError(
          caught instanceof ApiError
            ? caught.message
            : "We couldn't connect your microphone. Please check your device and try again.",
        );
      }
      transition("ERROR");
    }
  }

  async function connectAnalyser(stream: MediaStream) {
    if (analyserRef.current && audioContextRef.current) return;
    const AudioContextConstructor = window.AudioContext
      ?? (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextConstructor) throw new Error("Audio features aren't supported in this browser.");
    const context = new AudioContextConstructor();
    audioContextRef.current = context;
    await context.resume();
    const analyser = context.createAnalyser();
    analyser.fftSize = 1024;
    analyser.smoothingTimeConstant = 0.72;
    context.createMediaStreamSource(stream).connect(analyser);
    analyserRef.current = analyser;
  }

  function monitorMicrophonePreview() {
    const analyser = analyserRef.current;
    if (!analyser) return;
    const samples = new Uint8Array(analyser.fftSize);
    const sample = () => {
      if (!analyserRef.current || joinedRef.current) return;
      analyserRef.current.getByteTimeDomainData(samples);
      let sum = 0;
      for (const value of samples) {
        const normalized = (value - 128) / 128;
        sum += normalized * normalized;
      }
      meterRef.current?.style.setProperty("--voice-level", Math.min(1, Math.sqrt(sum / samples.length) * 10).toFixed(3));
      vadFrameRef.current = requestAnimationFrame(sample);
    };
    vadFrameRef.current = requestAnimationFrame(sample);
  }

  async function requestMicrophone() {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      throw new Error("This browser can't use voice. You can type your answer instead.");
    }
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    const track = stream.getAudioTracks()[0];
    if (!track) {
      stream.getTracks().forEach((item) => item.stop());
      throw new Error("No microphone was found.");
    }
    track.onended = () => {
      if (!mountedRef.current || !joinedRef.current) return;
      stopCapture(true);
      setErrorKind("MIC");
      setError("Mirror can't hear you because the microphone disconnected. Reconnect it, then try again.");
      transition("ERROR");
    };
    return stream;
  }

  async function testMicrophone() {
    if (roomStateRef.current === "CHECKING_MIC") return;
    setError("");
    setErrorKind(null);
    transition("CHECKING_MIC");
    try {
      const stream = await requestMicrophone();
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = stream;
      await connectAnalyser(stream);
      monitorMicrophonePreview();
      setPermission("granted");
      transition("PREJOIN");
    } catch (caught) {
      const denied = caught instanceof DOMException && (caught.name === "NotAllowedError" || caught.name === "SecurityError");
      setPermission(denied ? "denied" : "unavailable");
      setErrorKind("MIC");
      setError(denied
        ? "Microphone access is blocked. Allow it in browser settings, then check again."
        : caught instanceof Error ? caught.message : "We couldn't find a working microphone.");
      transition("ERROR");
    }
  }

  async function joinWithTyping() {
    if (roomStateRef.current === "CONNECTING") return;
    setError("");
    setErrorKind(null);
    transition("CONNECTING");
    try {
      const result = await mirrorApi.startVoiceInterview(sessionId);
      if (!mountedRef.current) return;
      joinedRef.current = true;
      setJoined(true);
      setShowTextFallback(true);
      await refreshTranscript();
      await presentQuestion(result, false);
      transition("PAUSED");
    } catch (caught) {
      setErrorKind(caught instanceof ApiError && caught.status === 401 ? "AUTH" : "SESSION");
      setError(caught instanceof ApiError ? caught.message : "We couldn't open the conversation just now. Please try again.");
      transition("ERROR");
    }
  }

  function toggleMute() {
    if (!joinedRef.current || closingRef.current) return;
    const next = !mutedRef.current;
    mutedRef.current = next;
    setMuted(next);
    streamRef.current?.getAudioTracks().forEach((track) => {
      track.enabled = !next;
    });
    if (next) {
      stopCapture(true);
      transition("PAUSED");
    } else if (roomStateRef.current !== "INTERVIEWER_SPEAKING") {
      beginListening();
    }
  }

  function toggleCaptions() {
    if (captionSupport !== "available") return;
    const next = !captionsEnabledRef.current;
    captionsEnabledRef.current = next;
    setCaptionsEnabled(next);
    if (!next) {
      stopLiveTranscription(true);
      return;
    }
    if (
      joinedRef.current
      && !mutedRef.current
      && (roomStateRef.current === "LISTENING" || roomStateRef.current === "CANDIDATE_SPEAKING")
    ) {
      startLiveTranscription();
    }
  }

  function toggleTextFallback() {
    const next = !showTextFallback;
    setShowTextFallback(next);
    if (next) {
      stopCapture(true);
      transition("PAUSED");
    } else if (joinedRef.current && !mutedRef.current && !closingRef.current) {
      beginListening();
    }
  }

  async function submitTextFallback(event: FormEvent) {
    event.preventDefault();
    const text = typedAnswer.trim();
    if (!text || submitInFlightRef.current || closingRef.current) return;
    submitInFlightRef.current = true;
    setError("");
    transition("PROCESSING");
    try {
      await mirrorApi.sendTextTurn(sessionId, text, crypto.randomUUID());
      if (!mountedRef.current) return;
      setTypedAnswer("");
      setShowTextFallback(false);
      const voicedResult = await mirrorApi.startVoiceInterview(sessionId);
      await refreshTranscript();
      submitInFlightRef.current = false;
      await presentQuestion(voicedResult, true);
    } catch (caught) {
      if (!mountedRef.current) return;
      setError(caught instanceof ApiError ? caught.message : "We couldn't send that answer just now. Please try again.");
      transition("ERROR");
    } finally {
      submitInFlightRef.current = false;
    }
  }

  async function retryAudio() {
    if (!turnId || roomStateRef.current === "PROCESSING") return;
    setError("");
    transition("PROCESSING");
    try {
      const result = await mirrorApi.retryTurnAudio(turnId);
      if (!mountedRef.current) return;
      await presentQuestion(result, true);
    } catch (caught) {
      if (!mountedRef.current) return;
      setError(caught instanceof ApiError ? caught.message : "Mirror's voice still isn't available. You can read the question above.");
      transition("ERROR");
    }
  }

  function resumeConversation() {
    setError("");
    setErrorKind(null);
    if (pendingVoiceRef.current) {
      const pending = pendingVoiceRef.current;
      void submitVoice(pending.blob, pending.durationMs, pending.clientTurnId);
      return;
    }
    if (audioUrl && roomStateRef.current === "ERROR" && audioFailed) {
      void playQuestion();
    } else if (joinedRef.current && !mutedRef.current) {
      beginListening();
    }
  }

  async function completeInterview() {
    if (roomStateRef.current === "CONNECTING" || completionInFlightRef.current) return;
    completionInFlightRef.current = true;
    audioRef.current?.pause();
    releaseMedia();
    transition("PROCESSING");
    try {
      await mirrorApi.endInterview(sessionId);
      if (!mountedRef.current) return;
      transition("COMPLETE");
    } catch (caught) {
      if (!mountedRef.current) return;
      setError(caught instanceof ApiError ? caught.message : "We couldn't end the conversation just now. Please try again.");
      setErrorKind(caught instanceof ApiError && caught.status === 401 ? "AUTH" : "COMPLETION");
      closingRef.current = false;
      setClosing(false);
      transition("ERROR");
    } finally {
      completionInFlightRef.current = false;
    }
  }

  // A resumed conversation opens with a short welcome before the last question is asked again.
  async function playWelcome(result: VoiceTurnResult) {
    if (!result.welcome_back || !result.welcome_text) return;
    setWelcomeLine(result.welcome_text);
    const url = result.welcome_audio_url;
    if (url) {
      await new Promise<void>((resolve) => {
        const clip = new Audio(url);
        clip.onended = () => resolve();
        clip.onerror = () => resolve();
        void clip.play().catch(() => resolve());
      });
    }
    if (mountedRef.current) setWelcomeLine(null);
  }

  async function endInterview() {
    setStepAway("closed");
    await completeInterview();
  }

  function openStepAway() {
    stopCapture(true);
    audioRef.current?.pause();
    setStepAway("menu");
  }

  function stayInConversation() {
    setStepAway("closed");
    resumeConversation();
  }

  async function saveAndContinueLater() {
    setSavingDraft(true);
    try {
      await mirrorApi.pauseSession(sessionId);
      releaseMedia();
      router.replace("/dashboard");
    } catch {
      setError(voiceRoom.stepAway.saveFailed);
      setSavingDraft(false);
      setStepAway("closed");
    }
  }

  useLifecycle(sessionId, joined, {
    onOpenElsewhere: () => {
      releaseMedia();
      setErrorKind("SESSION");
      setError(lifecycleCopy.openElsewhere);
    },
    onConnectionLost: () => {
      setErrorKind("NETWORK");
      setError(lifecycleCopy.connectionDropped);
      transition("ERROR");
    },
  });

  useEffect(() => {
    const offline = () => {
      if (!joinedRef.current) return;
      stopCapture(true);
      setErrorKind("NETWORK");
      setError("Connection interrupted. Your completed answers are saved. Reconnect before continuing.");
      transition("ERROR");
    };
    const online = () => {
      if (errorKind !== "NETWORK") return;
      setError("");
      setErrorKind(null);
      if (joinedRef.current && !mutedRef.current) beginListening();
    };
    window.addEventListener("offline", offline);
    window.addEventListener("online", online);
    return () => {
      window.removeEventListener("offline", offline);
      window.removeEventListener("online", online);
    };
  }, [errorKind]);

  // Closing or leaving the tab saves the place instead of losing it.
  useEffect(() => {
    const refresh = () => {
      void getSupabaseBrowserClient().auth.getSession().then(({ data }) => {
        accessTokenRef.current = data.session?.access_token;
      });
    };
    refresh();
    const timer = window.setInterval(refresh, 4 * 60 * 1000);
    const onPageHide = () => {
      if (joinedRef.current && !completionInFlightRef.current && roomStateRef.current !== "COMPLETE") {
        pauseOnPageExit(sessionId, accessTokenRef.current);
      }
    };
    window.addEventListener("pagehide", onPageHide);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("pagehide", onPageHide);
    };
  }, [sessionId]);

  if (roomState === "PREPARING") {
    return (
      <main className="interview-room interview-room--preparing">
        <Loader page label={loading.room.label} note={loading.room.note} />
      </main>
    );
  }

  const transcriptTurns = transcript.slice(-8);
  const processing = roomState === "CONNECTING" || roomState === "CHECKING_MIC" || roomState === "PROCESSING";

  return (
    <main className={`interview-room interview-room--${roomState.toLowerCase()}`}>
      <header className="interview-room-header">
        <div className="interview-room-brand">
          <span className="interview-room-mark">M</span>
          <div>
            <strong>Mirror</strong>
            <span>{targetRole || "Interview practice"}</span>
          </div>
        </div>
        <div className="interview-room-meta">
          <span className="interview-room-phase">{phase.replaceAll("_", " ")}</span>
          <time aria-label={`${remaining} seconds remaining`}>{formatTime(remaining)} remaining</time>
        </div>
      </header>

      {roomState === "COMPLETE" ? (
        <section className="interview-complete" aria-labelledby="interview-complete-title">
          <p className="mono">Conversation saved</p>
          <h1 id="interview-complete-title" className="display">Interview complete</h1>
          <p>Your answers are safe. Mirror is preparing your review; you can open it now and it will update when ready.</p>
          <div>
            <button type="button" onClick={() => router.push(`/app/report/${sessionId}`)}>View review</button>
            <button type="button" className="is-quiet" onClick={() => router.push("/dashboard")}>Return to Home</button>
          </div>
        </section>
      ) : !joined ? (
        <section className="interview-prejoin" aria-labelledby="prejoin-title">
          <div className="interview-prejoin-preview">
            <div className="interview-presence interview-presence--preview" aria-hidden="true">
              <span>M</span>
              <i /><i /><i />
            </div>
            <div className="interview-prejoin-device">
              <span className={`interview-device-dot ${permission === "denied" || permission === "unavailable" ? "is-denied" : ""}`} />
              {permission === "granted" ? "Microphone ready" : permission === "denied" ? "Microphone blocked" : permission === "unavailable" ? "Microphone unavailable" : "Microphone permission required"}
            </div>
            {permission === "granted" ? (
              <div ref={meterRef} className="interview-voice-meter interview-voice-meter--preview" aria-label="Live microphone level">
                {Array.from({ length: 13 }, (_, index) => <i key={index} />)}
              </div>
            ) : null}
          </div>
          <div className="interview-prejoin-copy">
            <p className="mono">{practiceLabels[practiceMode]} · {targetRole || "Interview practice"}</p>
            <h1 id="prejoin-title" className="display">Ready when you are.</h1>
            <p>
              This works like a live call. Mirror asks a question, listens while you answer,
              and responds when you finish speaking. There are no trick questions, and you can mute or stop whenever you like.
            </p>
            {error ? <p role="alert" className="interview-inline-error">{error}</p> : null}
            {permission !== "granted" ? <button
              type="button"
              className="interview-mic-test-button"
              onClick={() => void testMicrophone()}
              disabled={roomState === "CHECKING_MIC"}
            >
              {roomState === "CHECKING_MIC" ? <SpinnerGap className="interview-spinner" size={19} /> : <Microphone size={19} />}
              {roomState === "CHECKING_MIC" ? "Checking microphone…" : "Check microphone"}
            </button> : null}
            <button
              type="button"
              className="interview-join-button"
              onClick={() => void joinInterview()}
              disabled={processing || permission !== "granted"}
            >
              {roomState === "CONNECTING" ? <SpinnerGap className="interview-spinner" size={19} /> : <Microphone size={19} />}
              {roomState === "CONNECTING" ? "Joining…" : permission === "granted" ? "Start interview" : "Enable microphone first"}
            </button>
            {permission === "denied" || permission === "unavailable" ? (
              <button type="button" className="interview-text-entry-button" onClick={() => void joinWithTyping()} disabled={processing}>
                Continue with typing
              </button>
            ) : null}
            <small>
              Your interview audio and confirmed transcript are saved for your review. Live captions use your browser&apos;s speech service when supported and are not the interview record.
            </small>
          </div>
        </section>
      ) : (
        <>
          <div className="interview-call-layout">
            <section className="interview-stage" aria-label="Interview participants">
              <article className="interview-participant interview-participant--mirror">
                <div className="interview-participant-label">
                  <span>Mirror</span>
                  <small>Interviewer</small>
                </div>
                <div className="interview-presence" aria-hidden="true">
                  <span>M</span>
                  <i /><i /><i />
                </div>
                <div
                  className={`interview-question${greeting ? " interview-question--opening" : ""}`}
                  aria-live="polite"
                >
                  <span>
                    {roomState === "INTERVIEWER_SPEAKING"
                      ? "Mirror is speaking"
                      : greeting ? "Welcome" : "Current question"}
                  </span>
                  {welcomeLine ? <p className="interview-greeting" role="status">{welcomeLine}</p> : null}
                  {greeting ? <p className="interview-greeting">{greeting}</p> : null}
                  <h1 className="display">{questionBody || "Preparing the next question…"}</h1>
                </div>
              </article>

              <article className="interview-participant interview-participant--candidate">
                <div className="interview-participant-label">
                  <span>You</span>
                  <small>{muted ? "Muted" : "Microphone on"}</small>
                </div>
                <div ref={meterRef} className="interview-voice-meter" aria-hidden="true">
                  {Array.from({ length: 13 }, (_, index) => <i key={index} />)}
                </div>
                {liveCaption && captionsEnabled ? (
                  <div className="interview-live-caption" aria-live="polite">
                    <span>You · Live</span>
                    <p>{liveCaption}</p>
                  </div>
                ) : (
                  <p>{roomState === "CANDIDATE_SPEAKING" ? "Take your time. Mirror is listening." : stateLabels[roomState]}</p>
                )}
              </article>
            </section>

            <aside className="interview-transcript" aria-label="Conversation transcript">
              <div className="interview-transcript-heading">
                <div>
                  <span className="mono">Conversation</span>
                  <h2 className="display">Conversation</h2>
                </div>
                <span className={`interview-live-dot ${!captionsEnabled || captionSupport !== "available" ? "is-off" : ""}`}>
                  {captionSupport === "available"
                    ? captionsEnabled ? "Captions on" : "Captions off"
                    : "Turn transcript"}
                </span>
              </div>
              <div className="interview-transcript-list">
                {transcriptTurns.length ? transcriptTurns.map((turn) => (
                  <article key={turn.id} className={`interview-transcript-turn is-${turn.speaker.toLowerCase()}`}>
                    <span>{speakerName(turn.speaker)}</span>
                    <p>{turn.text}</p>
                  </article>
                )) : !liveCaption || !captionsEnabled ? (
                  <p className="interview-transcript-empty">The conversation will appear here as it unfolds.</p>
                ) : null}
                {liveCaption && captionsEnabled ? (
                  <article className="interview-transcript-turn is-candidate is-live" aria-live="polite">
                    <span>You · Live</span>
                    <p>{liveCaption}</p>
                  </article>
                ) : null}
                {roomState === "PROCESSING" ? (
                  <div className="interview-thinking" role="status">
                    <i /><i /><i /> Mirror is considering your answer
                  </div>
                ) : null}
              </div>
            </aside>
          </div>

          {showTextFallback ? (
            <form className="interview-text-composer" onSubmit={submitTextFallback}>
              <div>
                <label htmlFor="typed-answer">Type your answer</label>
                <span>Voice pauses while you type.</span>
              </div>
              <textarea
                id="typed-answer"
                value={typedAnswer}
                onChange={(event) => setTypedAnswer(event.target.value)}
                placeholder="Write naturally, as you would say it…"
                maxLength={20_000}
                disabled={processing}
                autoFocus
              />
              <div>
                <button type="button" onClick={toggleTextFallback}>Cancel</button>
                <button type="submit" disabled={processing || !typedAnswer.trim()}>Send answer</button>
              </div>
            </form>
          ) : null}

          {error ? (
            <div className="interview-error-banner" role="alert">
              <span><strong>{errorKind === "NETWORK" ? "Connection interrupted. " : errorKind === "MIC" ? "Microphone unavailable. " : ""}</strong>{error}</span>
              {!processing && !closing ? <button type="button" onClick={resumeConversation}>Continue</button> : null}
            </div>
          ) : null}

          <footer className="interview-controls" aria-label="Interview controls">
            <div className="interview-call-status" aria-live="polite">
              <span className={`interview-status-dot is-${roomState.toLowerCase()}`} />
              <div>
                <strong>{stateLabels[roomState]}</strong>
                {roomState === "PROCESSING" ? <small>{uploadProgress < 100 ? "Sending your answer securely" : "Preparing the next question"}</small> : null}
              </div>
            </div>
            <div className="interview-control-cluster">
              <button
                type="button"
                className={muted ? "is-active" : ""}
                onClick={toggleMute}
                disabled={processing || closing}
                aria-pressed={muted}
                aria-label={muted ? "Unmute microphone" : "Mute microphone"}
              >
                {muted ? <MicrophoneSlash size={21} /> : <Microphone size={21} />}
                <span>{muted ? "Unmute" : "Mute"}</span>
              </button>
              <button
                type="button"
                className={showTextFallback ? "is-active" : ""}
                onClick={toggleTextFallback}
                disabled={processing || closing}
                aria-pressed={showTextFallback}
              >
                <Keyboard size={21} />
                <span>Type</span>
              </button>
              <button
                type="button"
                className={captionsEnabled && captionSupport === "available" ? "is-active" : ""}
                onClick={toggleCaptions}
                disabled={captionSupport !== "available"}
                aria-pressed={captionsEnabled && captionSupport === "available"}
                aria-label={captionsEnabled ? "Turn live captions off" : "Turn live captions on"}
                title={captionSupport === "unavailable" ? "Live captions are not supported by this browser" : undefined}
              >
                <strong className="interview-cc-icon">CC</strong>
                <span>Captions</span>
              </button>
              {(audioUrl || audioFailed) ? (
                <button
                  type="button"
                  className={audioFailed ? "is-degraded" : ""}
                  onClick={() => audioFailed ? void retryAudio() : void playQuestion()}
                  disabled={processing}
                  title={audioFailed
                    ? "Mirror's voice isn't available for this question. You can read it above and answer as usual."
                    : "Hear the question again"}
                >
                  {audioFailed ? <SpeakerSlash size={21} /> : <SpeakerHigh size={21} />}
                  <span>{audioFailed ? "Retry voice" : "Replay"}</span>
                </button>
              ) : null}
            </div>
            {roomState === "CANDIDATE_SPEAKING" ? (
              <button type="button" className="interview-done-button" onClick={() => stopCapture(false)}>
                <span>{voiceRoom.doneAnswering}</span>
              </button>
            ) : null}
            <button
              type="button"
              className="interview-leave-button"
              onClick={openStepAway}
              disabled={processing || roomState === "CANDIDATE_SPEAKING" || closing}
              title={roomState === "CANDIDATE_SPEAKING" ? "Pause briefly so Mirror can save your final answer" : undefined}
            >
              <X size={20} />
              <span>{voiceRoom.stepAway.button}</span>
            </button>
          </footer>
        </>
      )}
      {stepAway !== "closed" ? (
        <div className="interview-dialog-backdrop" role="presentation">
          <div className="interview-dialog" role="dialog" aria-modal="true" aria-labelledby="step-away-title">
            {stepAway === "menu" ? (
              <>
                <h2 id="step-away-title">{voiceRoom.stepAway.title}</h2>
                <p>{voiceRoom.stepAway.body}</p>
                <div className="interview-dialog-actions">
                  <button type="button" className="is-primary" disabled={savingDraft} onClick={() => void saveAndContinueLater()}>
                    {savingDraft ? voiceRoom.stepAway.saving : voiceRoom.stepAway.save}
                  </button>
                  <button type="button" disabled={savingDraft} onClick={() => setStepAway("confirm")}>
                    {voiceRoom.stepAway.end}
                  </button>
                  <button type="button" className="is-quiet" disabled={savingDraft} onClick={stayInConversation}>
                    {voiceRoom.stepAway.stay}
                  </button>
                </div>
              </>
            ) : (
              <>
                <h2 id="step-away-title">{voiceRoom.stepAway.end}</h2>
                <p>{voiceRoom.endConfirm.body}</p>
                <div className="interview-dialog-actions">
                  <button type="button" className="is-primary" onClick={() => void endInterview()}>
                    {voiceRoom.endConfirm.confirm}
                  </button>
                  <button type="button" className="is-quiet" onClick={() => setStepAway("menu")}>
                    {voiceRoom.endConfirm.cancel}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      ) : null}
    </main>
  );
}
