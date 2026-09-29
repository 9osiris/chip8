"""square-wave wav generator for chip-8 beeps.

writes a 16-bit mono wav with a square wave at the given frequency
and duration. used to render the sound timer as an actual file.
"""
import struct
import wave


def square_wav(path, freq=440, seconds=0.2, rate=22050, volume=0.3):
    n = int(rate * seconds)
    amp = int(32767 * volume)
    frames = bytearray()
    period = rate / freq
    for i in range(n):
        # square: high for first half of period, low for second
        sample = amp if (i % period) < (period / 2) else -amp
        frames += struct.pack("<h", sample)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return path


def beep_for_st(st_value, path="/tmp/chip8_beep.wav"):
    """one beep per sound-timer tick, 60 ticks = 1 second."""
    seconds = st_value / 60.0
    return square_wav(path, freq=880, seconds=seconds)


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/chip8_beep.wav"
    freq = float(sys.argv[2]) if len(sys.argv) > 2 else 440
    secs = float(sys.argv[3]) if len(sys.argv) > 3 else 0.2
    square_wav(out, freq=freq, seconds=secs)
    print(f"wrote {out}")
