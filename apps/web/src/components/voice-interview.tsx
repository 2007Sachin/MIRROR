"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
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
  uploadVoiceTurn,
  type PublicInterviewTurn,
  type VoiceTurnResult,
} from "@/lib/api";

type RoomState =
  | "PREPARING"
  | "PREJOIN"
  | "CONNECTING"
  | "INTERVIEWER_SPEAKING"
  | "LISTENING"
  | "CANDIDATE_SPEAKING"
  | "PROCESSING"
  | "PAUSED"
  | "ERROR"
  | "COMPLETE";

type PermissionState = "prompt" | "granted" | "denied";
type CaptionSupport = "checking" | "available" | "unavailable";

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
const END_OF_TURN_SILENCE_MS = 1150;
const MINIMUM_TURN_MS = 650;
const MAXIMUM_TURN_MS = 120_000;

const stateLabels: Record<RoomState, string> = {
  PREPARING: "Preparing the room",
  PREJOIN: "Ready to join",
  CONNECTING: "Joining the interview",
  INTERVIEWER_SPEAKING: "Mirror is speaking",
  LISTENING: "Listening",
  CANDIDATE_SPEAKING: "You are speaking",
  PROCESSING: "Mirror is considering your answer",
  PAUSED: "Microphone muted",
  ERROR: "Needs attention",
  COMPLETE: "Interview complete",
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
  const roomStateRef = useRef<RoomState>("PREPARING");
  const submitInFlightRef = useRef(false);
  const completionInFlightRef = useRef(false);
  const uploadAbortRef = useRef<AbortController | null>(null);
  const redirectTimerRef = useRef<number | null>(null);
  const deadlineRef = useRef<number | null>(null);

  const [phase, setPhase] = useState("INTRO");
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
        if (session.status === "COMPLETED") {
          router.replace("/dashboard");
          return;
        }
        if (session.status === "ASSESSING") {
          void completeInterview();
          return;
        }
        if (session.status !== "READY" && session.status !== "ACTIVE") {
          setError("This interview room is not ready yet.");
          transition("ERROR");
          return;
        }
        setPhase(session.phase);
        setRemainingFromServer(
          Math.max(0, session.total_time_budget_seconds - session.elapsed_seconds),
        );
        if (session.status === "ACTIVE") {
          const result = await mirrorApi.startVoiceInterview(sessionId);
          if (!active) return;
          await presentQuestion(result, false);
          await refreshTranscript();
        } else {
          transition("PREJOIN");
        }
      } catch (caught) {
        if (!active) return;
        setError(
          caught instanceof ApiError
            ? caught.message
            : "Mirror could not prepare this interview room.",
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
      setError("Mirror's audio is unavailable. The question remains visible.");
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
      setError("The microphone stopped unexpectedly. Select the microphone to reconnect.");
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
      setLiveCaption("");
      submitInFlightRef.current = false;
      await presentQuestion(result, true);
    } catch (caught) {
      if (!mountedRef.current || (caught instanceof DOMException && caught.name === "AbortError")) return;
      const apiError = caught instanceof ApiError ? caught : null;
      setError(
        apiError?.code === "TRANSCRIPTION_FAILED"
          ? "I couldn't hear that clearly. When you're ready, say your answer again."
          : apiError?.message ?? "The conversation was interrupted. Try that answer again.",
      );
      setLiveCaption("");
      transition("ERROR");
    } finally {
      if (uploadAbortRef.current === abortController) uploadAbortRef.current = null;
      submitInFlightRef.current = false;
    }
  }

  async function joinInterview() {
    if (roomStateRef.current === "CONNECTING") return;
    setError("");
    transition("CONNECTING");
    let stream: MediaStream | null = null;
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
        throw new Error("Voice capture is not supported by this browser.");
      }
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      if (!mountedRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      const AudioContextConstructor = window.AudioContext
        ?? (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioContextConstructor) throw new Error("Audio analysis is not supported.");
      const context = new AudioContextConstructor();
      audioContextRef.current = context;
      await context.resume();
      const analyser = context.createAnalyser();
      analyser.fftSize = 1024;
      analyser.smoothingTimeConstant = 0.72;
      context.createMediaStreamSource(stream).connect(analyser);
      analyserRef.current = analyser;
      configureLiveTranscription();
      joinedRef.current = true;
      setJoined(true);
      setPermission("granted");
      const result = await mirrorApi.startVoiceInterview(sessionId);
      await refreshTranscript();
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
        setError("Microphone access is blocked. Allow it in browser settings to join by voice.");
      } else {
        setError(
          caught instanceof ApiError
            ? caught.message
            : "Mirror could not connect your microphone. Check the device and try again.",
        );
      }
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
      setError(caught instanceof ApiError ? caught.message : "Mirror could not send that answer.");
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
      setError(caught instanceof ApiError ? caught.message : "Mirror's audio is still unavailable.");
      transition("ERROR");
    }
  }

  function resumeConversation() {
    setError("");
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
      router.replace("/dashboard");
    } catch (caught) {
      if (!mountedRef.current) return;
      setError(caught instanceof ApiError ? caught.message : "Mirror could not end the interview.");
      closingRef.current = false;
      setClosing(false);
      transition("ERROR");
    } finally {
      completionInFlightRef.current = false;
    }
  }

  async function endInterview() {
    await completeInterview();
  }

  const transcriptTurns = transcript.slice(-8);
  const processing = roomState === "CONNECTING" || roomState === "PROCESSING";

  return (
    <main className={`interview-room interview-room--${roomState.toLowerCase()}`}>
      <header className="interview-room-header">
        <div className="interview-room-brand">
          <span className="interview-room-mark">M</span>
          <div>
            <strong>Mirror interview</strong>
            <span>Private practice room</span>
          </div>
        </div>
        <div className="interview-room-meta">
          <span className="interview-room-phase">{phase.replaceAll("_", " ")}</span>
          <time aria-label={`${remaining} seconds remaining`}>{formatTime(remaining)}</time>
        </div>
      </header>

      {!joined ? (
        <section className="interview-prejoin" aria-labelledby="prejoin-title">
          <div className="interview-prejoin-preview">
            <div className="interview-presence interview-presence--preview" aria-hidden="true">
              <span>M</span>
              <i /><i /><i />
            </div>
            <div className="interview-prejoin-device">
              <span className={`interview-device-dot ${permission === "denied" ? "is-denied" : ""}`} />
              {permission === "denied" ? "Microphone blocked" : "Microphone ready to connect"}
            </div>
          </div>
          <div className="interview-prejoin-copy">
            <p className="mono">Your private interview room</p>
            <h1 id="prejoin-title" className="display">Ready to meet Mirror?</h1>
            <p>
              This works like a live call. Mirror asks a question, listens while you answer,
              and responds when you finish speaking—no recording or submit buttons.
            </p>
            {error ? <p role="alert" className="interview-inline-error">{error}</p> : null}
            <button
              type="button"
              className="interview-join-button"
              onClick={() => void joinInterview()}
              disabled={roomState === "CONNECTING"}
            >
              {roomState === "CONNECTING" ? <SpinnerGap className="interview-spinner" size={19} /> : <Microphone size={19} />}
              {roomState === "CONNECTING" ? "Joining…" : "Join interview"}
            </button>
            <small>
              Live captions use your browser&apos;s speech service when supported. Mirror&apos;s
              confirmed server transcript remains the interview record.
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
                  {greeting ? <p className="interview-greeting">{greeting}</p> : null}
                  <h1 className="display">{questionBody || "Preparing the next question…"}</h1>
                </div>
              </article>

              <article className="interview-participant interview-participant--candidate">
                <div className="interview-participant-label">
                  <span>You</span>
                  <small>{muted ? "Muted" : "Candidate"}</small>
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
                  <p>{roomState === "CANDIDATE_SPEAKING" ? "Keep going—Mirror is listening." : stateLabels[roomState]}</p>
                )}
              </article>
            </section>

            <aside className="interview-transcript" aria-label="Conversation transcript">
              <div className="interview-transcript-heading">
                <div>
                  <span className="mono">Conversation</span>
                  <h2 className="display">Live transcript</h2>
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
              <span>{error}</span>
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
                    ? "Mirror could not speak this question. You can read it above and answer normally."
                    : "Hear the question again"}
                >
                  {audioFailed ? <SpeakerSlash size={21} /> : <SpeakerHigh size={21} />}
                  <span>{audioFailed ? "Retry voice" : "Replay"}</span>
                </button>
              ) : null}
            </div>
            <button
              type="button"
              className="interview-leave-button"
              onClick={() => void endInterview()}
              disabled={processing || roomState === "CANDIDATE_SPEAKING" || closing}
              title={roomState === "CANDIDATE_SPEAKING" ? "Pause briefly so Mirror can save your final answer" : undefined}
            >
              <X size={20} />
              <span>End interview</span>
            </button>
          </footer>
        </>
      )}
    </main>
  );
}
