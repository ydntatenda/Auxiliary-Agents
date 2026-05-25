import { Mic, Square } from "lucide-react";
import { useRef, useState } from "react";

type Props = {
  onRecordingReady: (blob: Blob | null) => void;
};

export default function VoiceRecorder({ onRecordingReady }: Props) {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const [recording, setRecording] = useState(false);
  const [ready, setReady] = useState(false);

  async function start() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    chunksRef.current = [];
    const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };
    recorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
      onRecordingReady(new Blob(chunksRef.current, { type: "audio/webm" }));
      setReady(true);
    };
    recorderRef.current = recorder;
    recorder.start();
    setRecording(true);
    setReady(false);
  }

  function stop() {
    recorderRef.current?.stop();
    setRecording(false);
  }

  return (
    <div className="voice-rec">
      <button className="rec-btn" onClick={recording ? stop : start} type="button">
        {recording ? <Square size={16} /> : <Mic size={18} />}
      </button>
      <div className="voice-info">
        <div className="vi-title">{recording ? "Recording in browser" : "Record in browser"}</div>
        <div className="vi-sub">
          {recording ? "Speak through the workflow end-to-end." : ready ? "Recording ready" : "Up to 15 minutes"}
        </div>
      </div>
      <div className="waveform" aria-hidden="true">
        {Array.from({ length: 28 }).map((_, index) => (
          <i key={index} style={{ height: `${6 + Math.abs(Math.sin(index * 0.6)) * 18}px` }} />
        ))}
      </div>
    </div>
  );
}
