"""tests for savestate, replay, trace, profiler, wav."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from chip8.cpu import Chip8
from chip8 import savestate, replay, trace as trace_mod, prof
import wav


def make_cpu():
    c = Chip8(seed=42)
    # tiny program: LD V0, 5; LD V1, 10; ADD V0, V1; JP 0x200
    prog = bytes([0x60, 0x05, 0x61, 0x0A, 0x80, 0x14, 0x12, 0x00])
    c.load_rom(prog)
    return c


def test_savestate_roundtrip():
    c = make_cpu()
    for _ in range(3):
        c.cycle()
    snap = savestate.save(c)
    # mutate
    c.v[0] = 99
    c.pc = 0x300
    c.memory[0x200] = 0xFF
    savestate.load(c, snap)
    assert c.v[0] == 15  # 5 + 10
    assert c.pc != 0x300
    assert c.memory[0x200] == 0x60


def test_savestate_preserves_rng():
    c = make_cpu()
    snap = savestate.save(c)
    r1 = c.rng.getstate()
    savestate.load(c, snap)
    r2 = c.rng.getstate()
    assert r1 == r2


def test_replay_records_keys():
    c = make_cpu()
    rec = replay.Recorder(c)
    rec.start()
    c.keys[5] = True
    rec.tick()
    c.keys[5] = False
    rec.tick()
    assert rec.frames == [1 << 5, 0]


def test_replay_playback():
    c = make_cpu()
    frames = [1 << 1, 1 << 2, 0]
    p = replay.Player(c, frames)
    assert p.tick() is True
    assert c.keys[1] is True
    assert p.tick() is True
    assert c.keys[2] is True
    assert p.tick() is True
    assert all(not k for k in c.keys)
    assert p.tick() is False
    assert p.done()


def test_replay_save_load():
    c = make_cpu()
    rec = replay.Recorder(c)
    rec.start()
    rec.frames = [3, 5, 7]
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
    try:
        rec.save(path)
        frames = replay.Recorder.load(path)
        assert frames == [3, 5, 7]
    finally:
        os.unlink(path)


def test_tracer_logs():
    c = make_cpu()
    t = trace_mod.Tracer(c, max_lines=3)
    lines = t.run(10)
    assert len(lines) == 3
    assert "6005" in lines[0] or "60" in lines[0]


def test_profiler_counts():
    c = make_cpu()
    p = prof.Profiler(c)
    p.run(100)
    assert p.total == 100
    assert len(p.op_counts) > 0
    top = p.top_ops(3)
    assert len(top) <= 3


def test_profiler_hot_blocks():
    c = make_cpu()
    p = prof.Profiler(c)
    p.run(200)
    hot = p.hot_blocks()
    assert isinstance(hot, list)


def test_profiler_heatmap():
    c = make_cpu()
    p = prof.Profiler(c)
    p.run(50)
    hm = p.heatmap()
    assert "0x" in hm or "0200" in hm


def test_wav_writes():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    try:
        wav.square_wav(path, freq=440, seconds=0.05)
        assert os.path.getsize(path) > 44  # bigger than header
    finally:
        os.unlink(path)
