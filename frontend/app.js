const callBtn = document.getElementById("callBtn");
const statusEl = document.getElementById("status");
const transcriptEl = document.getElementById("transcript");

let ws = null;
let micContext = null;
let micStream = null;

// --- playback state: schedules incoming audio chunks back-to-back so
// speech sounds continuous instead of chopped into gaps between chunks ---
let playbackContext = null;
let nextStartTime = 0;
let activeSources = [];

function setStatus(text) {
  statusEl.textContent = text;
}

function addLine(role, text) {
  const div = document.createElement("div");
  div.className = `line ${role}`;
  div.textContent = text;
  transcriptEl.appendChild(div);
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
}

async function startCall() {
  micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  micContext = new AudioContext();
  await micContext.audioWorklet.addModule("pcm-processor.js");

  playbackContext = new AudioContext();
  nextStartTime = 0;

  const protocol = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${protocol}://${location.host}/ws`);
  ws.binaryType = "arraybuffer";

  ws.onopen = () => {
    setStatus("listening");
    const source = micContext.createMediaStreamSource(micStream);
    const worklet = new AudioWorkletNode(micContext, "pcm-processor");
    worklet.port.onmessage = (event) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(event.data);
      }
    };
    source.connect(worklet);
  };

  ws.onmessage = async (event) => {
    if (typeof event.data === "string") {
      handleControlMessage(JSON.parse(event.data));
    } else {
      await playAudioChunk(event.data);
    }
  };

  ws.onclose = () => setStatus("call ended");

  callBtn.textContent = "End call";
  callBtn.classList.add("active");
}

function handleControlMessage(msg) {
  if (msg.type === "transcript") {
    addLine("user", msg.text);
  } else if (msg.type === "assistant_text") {
    addLine("assistant", msg.text);
    setStatus("speaking");
  } else if (msg.type === "stop_audio") {
    stopPlayback();
    setStatus("listening");
  } else if (msg.type === "assistant_done") {
    setStatus("listening");
  }
}

async function playAudioChunk(arrayBuffer) {
  const audioData = await playbackContext.decodeAudioData(arrayBuffer.slice(0));
  const source = playbackContext.createBufferSource();
  source.buffer = audioData;
  source.connect(playbackContext.destination);

  const now = playbackContext.currentTime;
  const startAt = Math.max(now, nextStartTime);
  source.start(startAt);
  nextStartTime = startAt + audioData.duration;

  activeSources.push(source);
  source.onended = () => {
    activeSources = activeSources.filter((s) => s !== source);
  };
}

function stopPlayback() {
  for (const source of activeSources) {
    try {
      source.stop();
    } catch {
      // already stopped — ignore
    }
  }
  activeSources = [];
  nextStartTime = playbackContext ? playbackContext.currentTime : 0;
}

function endCall() {
  ws?.close();
  micStream?.getTracks().forEach((track) => track.stop());
  micContext?.close();
  playbackContext?.close();
  callBtn.textContent = "Start call";
  callBtn.classList.remove("active");
  setStatus("idle");
}

callBtn.addEventListener("click", () => {
  if (callBtn.classList.contains("active")) {
    endCall();
  } else {
    startCall().catch((err) => {
      console.error(err);
      setStatus("microphone error");
    });
  }
});
