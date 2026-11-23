"""Figure Shelf: engine sounds for the second set of robot vehicles (Nov 2026), synthesised here.
python3 models/make_vehicle_sounds2.py  ->  FigureShelf.swiftpm/Resources/Sounds/sfx_run_<kind>.m4a
Same rules and helpers as models/make_sounds.py (copied, so running this file only makes these):
gentle, quiet (peak -12 dBFS), 6 s = the robot Run (change, trip, change back).

  train    soft electric hum with a steady clickety-clack and two gentle "choo" puffs
  sub      deep underwater hum with slow soft bubbles
  tractor  slow chugging diesel, low and round
  bus      smooth low engine with a soft door-chime "ding" at the start
  forklift little electric whine that rises and falls (lifting the forks)
  cable    quiet whirr of the wheels on the cable with a slow creak-sway
  rover    light electric purr with soft boing-hops (low gravity)
  airship  slow propeller thrum and a soft airy hush
"""
import math, random, struct, wave, os, subprocess
SR = 22050
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "FigureShelf.swiftpm", "Resources", "Sounds")
os.makedirs(OUT, exist_ok=True)
random.seed(7)

def silence(sec): return [0.0] * int(sec * SR)

def add(buf, snd, at):
    i0 = int(at * SR)
    for i, v in enumerate(snd):
        if i0 + i < len(buf): buf[i0 + i] += v

def env(n, a, r):
    """attack/release in samples, smooth"""
    out = []
    for i in range(n):
        e = 1.0
        if i < a: e = 0.5 - 0.5 * math.cos(math.pi * i / a)
        if i > n - r: e *= 0.5 - 0.5 * math.cos(math.pi * (n - i) / r)
        out.append(e)
    return out

def tone(f0, f1, sec, vol, harm=(1.0, 0.25, 0.08), decay=None):
    n = int(sec * SR); e = env(n, int(0.01 * SR), int(0.06 * SR)); out = []; ph = 0.0
    for i in range(n):
        t = i / n; f = f0 * (f1 / f0) ** t
        ph += 2 * math.pi * f / SR
        v = sum(h * math.sin(ph * (k + 1)) for k, h in enumerate(harm))
        d = math.exp(-t * decay) if decay else 1.0
        out.append(vol * v * e[i] * d)
    return out

def mallet(f, sec, vol):           # soft marimba-like note
    return tone(f, f, sec, vol, harm=(1.0, 0.0, 0.0, 0.18), decay=6.0)

def thud(vol, sec=0.12, f=90):     # soft landing / footstep
    return tone(f * 1.6, f, sec, vol, harm=(1.0, 0.2), decay=9.0)

def noise_sweep(sec, vol, f0, f1):  # whoosh: noise through a moving one-pole low-pass
    n = int(sec * SR); e = env(n, int(0.35 * n), int(0.45 * n)); out = []; y = 0.0
    for i in range(n):
        t = i / n; fc = f0 * (f1 / f0) ** (math.sin(math.pi * t))
        a = 1 - math.exp(-2 * math.pi * fc / SR)
        y += a * (random.uniform(-1, 1) - y)
        out.append(vol * y * e[i] * 2.2)
    return out

def save(name, buf):
    peak = max(1e-9, max(abs(v) for v in buf))
    k = 0.25 / peak                              # keep it quiet: peak at -12 dBFS
    wav = os.path.join(OUT, name + ".wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v * k)) * 32767)) for v in buf))
    m4a = os.path.join(OUT, "sfx_%s.m4a" % name)
    subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "64000", wav, m4a], check=True)
    os.remove(wav)
    print(name, os.path.getsize(m4a), "bytes")

RUN = 6.0

def lp_noise(sec, vol, fc, am_hz=0.0, am=0.0):
    n = int(sec * SR); out = []; y = 0.0
    a = 1 - math.exp(-2 * math.pi * fc / SR)
    for i in range(n):
        y += a * (random.uniform(-1, 1) - y)
        m = 1 - am + am * (0.5 + 0.5 * math.sin(2 * math.pi * am_hz * i / SR)) if am else 1
        out.append(vol * y * 3 * m)
    return out

def hum(sec, vol, freqs, am_hz=0.0, am=0.0, wobble=0.0):
    n = int(sec * SR); out = []; ph = [0.0] * len(freqs)
    for i in range(n):
        t = i / SR
        w = 1 + wobble * math.sin(2 * math.pi * 0.7 * t)
        v = 0.0
        for k, (f, g) in enumerate(freqs):
            ph[k] += 2 * math.pi * f * w / SR
            v += g * math.sin(ph[k])
        m = 1 - am + am * (0.5 + 0.5 * math.sin(2 * math.pi * am_hz * t)) if am else 1
        out.append(vol * v * m)
    return out

def fade(snd, a, r):
    n = len(snd); e = env(n, int(a * SR), int(r * SR))
    return [v * e[i] for i, v in enumerate(snd)]

def change(buf, at, up=True):
    """soft click-whirr: two little clicks and a gentle rising (or falling) whirr"""
    f0, f1 = (220, 520) if up else (520, 220)
    add(buf, tone(f0, f1, 0.6, 0.25, harm=(1.0, 0.3, 0.1)), at + 0.08)
    for k, dt in enumerate((0.0, 0.62)):
        add(buf, mallet(880 if k == 0 else 660, 0.12, 0.18), at + dt)


def bubbles(sec, vol, every):
    out = silence(sec); t = 0.2
    while t < sec - 0.3:
        add(out, tone(500 + random.uniform(-80, 120), 900, 0.07, vol, harm=(1.0,), decay=8.0), t)
        t += every * random.uniform(0.6, 1.4)
    return out

def puffs(sec, vol, times):
    out = silence(sec)
    for t in times:
        add(out, fade(lp_noise(0.5, vol, 900), 0.05, 0.35), t)
    return out

def clacks(sec, vol, every):
    out = silence(sec); t = 0.1
    while t < sec - 0.2:
        add(out, thud(vol, 0.08, 140), t); add(out, thud(vol * 0.8, 0.08, 120), t + 0.14)
        t += every
    return out

def mix(*parts):
    n = min(len(p) for p in parts)
    return [sum(p[i] for p in parts) for i in range(n)]

engines = {
    "train":    lambda: mix(hum(4.4, 0.25, [(60, 1.0), (120, 0.3)], am_hz=2, am=0.15),
                            clacks(4.4, 0.3, 0.55), puffs(4.4, 0.25, [0.4, 2.6])),
    "sub":      lambda: mix(hum(4.4, 0.3, [(46, 1.0), (92, 0.25)], am_hz=0.8, am=0.25, wobble=0.03),
                            bubbles(4.4, 0.12, 0.5)),
    "tractor":  lambda: hum(4.4, 0.4, [(44, 1.0), (88, 0.45), (132, 0.1)], am_hz=3.5, am=0.55),
    "bus":      lambda: mix(hum(4.4, 0.35, [(58, 1.0), (116, 0.3)], am_hz=4, am=0.2, wobble=0.02),
                            lp_noise(4.4, 0.06, 300)),
    "forklift": lambda: hum(4.4, 0.25, [(150, 1.0), (300, 0.2)], am_hz=0.5, am=0.4, wobble=0.12),
    "cable":    lambda: mix(lp_noise(4.4, 0.1, 500, am_hz=9, am=0.5),
                            hum(4.4, 0.12, [(90, 1.0)], am_hz=0.4, am=0.6)),
    "rover":    lambda: hum(4.4, 0.25, [(130, 1.0), (260, 0.2)], am_hz=11, am=0.3, wobble=0.04),
    "airship":  lambda: mix(hum(4.4, 0.28, [(70, 1.0), (140, 0.2)], am_hz=9, am=0.5),
                            lp_noise(4.4, 0.08, 350, am_hz=0.3, am=0.4)),
}
for kind, make in engines.items():
    buf = silence(RUN)
    change(buf, 0.05, up=True)
    eng = fade(make(), 0.6, 0.6)
    if kind == "bus":       # a soft "ding" as the doors close
        add(eng, mallet(988, 0.5, 0.12), 0.1); add(eng, mallet(784, 0.6, 0.12), 0.35)
    if kind == "rover":     # soft boing hops
        for k in range(4):
            add(eng, tone(200, 380, 0.25, 0.18, harm=(1.0, 0.15)), 0.5 + k * 1.0)
    add(buf, eng, 0.8)
    change(buf, 5.15, up=False)
    save("run_" + kind, buf)
