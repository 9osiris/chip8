"""save and restore full machine state."""
import io
import struct


def save(cpu):
    """capture everything needed to resume exactly."""
    buf = io.BytesIO()
    buf.write(struct.pack(">H", cpu.pc))
    buf.write(struct.pack(">H", cpu.i))
    buf.write(bytes(cpu.v))
    buf.write(struct.pack(">B", cpu.delay))
    buf.write(struct.pack(">B", cpu.sound))
    buf.write(struct.pack(">B", len(cpu.stack)))
    for addr in cpu.stack:
        buf.write(struct.pack(">H", addr))
    # memory from 0x200 up (font is constant, low ram rarely used by roms)
    buf.write(bytes(cpu.memory[0x200:]))
    buf.write(bytes(cpu.display))
    buf.write(struct.pack(">B", 1 if cpu.waiting_for_key else 0))
    # rng state so replays stay deterministic
    rng_state = cpu.rng.getstate()
    rng_bytes = repr(rng_state).encode("utf-8")
    buf.write(struct.pack(">I", len(rng_bytes)))
    buf.write(rng_bytes)
    return buf.getvalue()


def load(cpu, data):
    """restore a snapshot from save()."""
    buf = io.BytesIO(data)
    cpu.pc = struct.unpack(">H", buf.read(2))[0]
    cpu.i = struct.unpack(">H", buf.read(2))[0]
    cpu.v = bytearray(buf.read(16))
    cpu.delay = struct.unpack(">B", buf.read(1))[0]
    cpu.sound = struct.unpack(">B", buf.read(1))[0]
    n = struct.unpack(">B", buf.read(1))[0]
    cpu.stack = []
    for _ in range(n):
        cpu.stack.append(struct.unpack(">H", buf.read(2))[0])
    mem = buf.read(4096 - 0x200)
    cpu.memory[0x200:0x200 + len(mem)] = mem
    disp = buf.read(len(cpu.display))
    cpu.display = bytearray(disp)
    cpu.waiting_for_key = bool(struct.unpack(">B", buf.read(1))[0])
    rng_len = struct.unpack(">I", buf.read(4))[0]
    rng_state = eval(buf.read(rng_len).decode("utf-8"))
    cpu.rng.setstate(rng_state)
    cpu.draw_flag = True
