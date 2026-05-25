import { MonitorUp, Square } from "lucide-react";
import { useRef, useState } from "react";

type Props = {
  onRecordingReady: (blob: Blob | null) => void;
};

const MAX_RECORDING_MS = 15 * 60 * 1000;

export default function ScreenRecorder({ onRecordingReady }: Props) {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const timeoutRef = useRef<number | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const [recording, setRecording] = useState(false);
  const [ready, setReady] = useState(false);

  async function start() {
    const screenStream = await navigator.mediaDevices.getDisplayMedia({
      video: { frameRate: 5 },
      audio: true,
    });
    const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const combined = new MediaStream([
      ...screenStream.getVideoTracks(),
      ...micStream.getAudioTracks(),
    ]);
    chunksRef.current = [];
    const recorder = new MediaRecorder(combined, {
      mimeType: "video/webm;codecs=vp9,opus",
      videoBitsPerSecond: 1_000_000,
    });
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };
    recorder.onstop = () => {
      combined.getTracks().forEach((track) => track.stop());
      screenStream.getTracks().forEach((track) => track.stop());
      micStream.getTracks().forEach((track) => track.stop());
      onRecordingReady(new Blob(chunksRef.current, { type: "video/webm" }));
      setReady(true);
      if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
    };
    recorderRef.current = recorder;
    recorder.start();
    setReady(false);
    setRecording(true);
    timeoutRef.current = window.setTimeout(stop, MAX_RECORDING_MS);
  }

  function stop() {
    recorderRef.current?.stop();
    setRecording(false);
  }

  return (
    <div className="screencap">
      <div className="screen-preview">
        <span>{recording ? "Recording active" : ready ? "Recording ready" : "Screen preview"}</span>
      </div>
      <div>
        <div className="screen-title">Record screen with narration</div>
        <div className="screen-sub">5fps capture with microphone audio. Hard capped at 15 minutes.</div>
        <button className="btn btn-primary" onClick={recording ? stop : start} type="button">
          {recording ? <Square size={14} /> : <MonitorUp size={14} />}
          {recording ? "Stop recording" : "Start recording"}
        </button>
      </div>
    </div>
  );
}
