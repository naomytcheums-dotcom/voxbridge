// AudioWorkletProcessor that downsamples the mic input to 16kHz mono PCM16
// and posts each block to the main thread as a transferable ArrayBuffer.
//
// The resampling here is nearest-neighbour, which is good enough for speech
// recognition but not audiophile-grade — a production build should swap
// this for a proper band-limited resampler.
class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._targetRate = 16000;
    this._ratio = sampleRate / this._targetRate;
    this._carry = 0;
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (!channel || channel.length === 0) return true;

    const samples = [];
    let pos = this._carry;
    while (pos < channel.length) {
      samples.push(channel[Math.floor(pos)]);
      pos += this._ratio;
    }
    this._carry = pos - channel.length;

    if (samples.length > 0) {
      const int16 = new Int16Array(samples.length);
      for (let i = 0; i < samples.length; i++) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      this.port.postMessage(int16.buffer, [int16.buffer]);
    }
    return true;
  }
}

registerProcessor("pcm-processor", PCMProcessor);
