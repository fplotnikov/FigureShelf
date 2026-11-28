"""Gentle water sounds for the swimmers (Mosasaurus, Elasmosaurus, Ichthyosaurus, Megalodon).
python3 models/new10dino/make_sea_sounds.py -> FigureShelf.swiftpm/Resources/Sounds/sfx_sea_<name>.m4a
Synthesised like models/make_sounds.py (filtered noise and sine blips, no samples), quiet
(peaks at -12 dBFS), soft starts and ends. Lengths match the moves: run 4.0 s, jump 2.4 s, wave 2.4 s.
Dance keeps the prehistoric dance tune."""
import math, random, struct, wave, os, subprocess
SR = 22050
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "FigureShelf.swiftpm", "Resources", "Sounds")
random.seed(11)

def silence(sec): return [0.0] * int(sec * SR)

def add(buf, snd, at):
    i0 = int(at * SR)
    for i, v in enumerate(snd):
        if 0 <= i0 + i < len(buf): buf[i0 + i] += v

def env(n, a, r):
    out = []
    for i in range(n):
        e = 1.0
        if i < a: e = 0.5 - 0.5 * math.cos(math.pi * i / a)
        if i > n - r: e *= 0.5 - 0.5 * math.cos(math.pi * (n - i) / r)
        out.append(e)
    return out

def swish(sec, vol, f0, f1, att=0.35):
    """water swish: noise through a moving low-pass, rounded"""
    n = int(sec * SR); e = env(n, int(att * n), int((0.95 - att) * n)); out = []; y = y2 = 0.0
    for i in range(n):
        t = i / n; fc = f0 * (f1 / f0) ** math.sin(math.pi * t)
        a = 1 - math.exp(-2 * math.pi * fc / SR)
        y += a * (random.uniform(-1, 1) - y); y2 += a * (y - y2)
        out.append(vol * y2 * e[i] * 3.0)
    return out

def bubble(f, vol, sec=0.07):
    """a tiny round bubble: a sine that glides up and fades"""
    n = int(sec * SR); out = []; ph = 0.0
    for i in range(n):
        t = i / n
        ph += 2 * math.pi * f * (1 + 0.9 * t) / SR
        out.append(vol * math.sin(ph) * math.sin(math.pi * t) * (1 - t))
    return out

def bubbles(buf, at, count, spread, vol=0.18, f=(500, 900)):
    for _ in range(count):
        add(buf, bubble(random.uniform(*f), vol * random.uniform(0.6, 1.0)), at + random.uniform(0, spread))

def splash(vol, sec=0.7):
    """soft splash: a noise burst that darkens as it fades"""
    n = int(sec * SR); out = []; y = y2 = 0.0
    for i in range(n):
        t = i / n
        fc = 2400 * (1 - t) ** 2 + 180
        a = 1 - math.exp(-2 * math.pi * fc / SR)
        y += a * (random.uniform(-1, 1) - y); y2 += a * (y - y2)
        e = min(1, t / 0.03) * math.exp(-5 * t)
        out.append(vol * y2 * e * 3.0)
    return out

def save(name, buf):
    peak = max(1e-9, max(abs(v) for v in buf))
    k = 0.25 / peak
    wav = os.path.join(OUT, name + ".wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v * k)) * 32767)) for v in buf))
    m4a = os.path.join(OUT, "sfx_%s.m4a" % name)
    subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "64000", wav, m4a], check=True)
    os.remove(wav)
    print(name, os.path.getsize(m4a), "bytes")

# run: a calm swim loop, a swish on every tail beat, a few bubbles
d = silence(4.0)
t = 0.1; k = 0
while t < 3.6:
    v = min(1, (t + 0.3) / 0.6, (3.9 - t) / 0.6)
    add(d, swish(0.5, 0.16 * v, 160, 520 if k % 2 == 0 else 430), t)
    t += 0.5; k += 1
for at in (0.6, 1.7, 2.9):
    bubbles(d, at, 4, 0.35, 0.12)
save("sea_run", d)

# jump: gathers speed, whooshes out of the water, a soft splash back in, then bubbles
d = silence(2.4)
add(d, swish(0.45, 0.12, 150, 420), 0.05)
add(d, swish(0.7, 0.16, 200, 900), 0.5)
add(d, splash(0.5), 1.78)
bubbles(d, 1.95, 9, 0.35, 0.16)
save("sea_jump", d)

# wave: three quick friendly flicks and a bubble sparkle
d = silence(2.4)
for k in range(3):
    add(d, swish(0.28, 0.14, 260, 800), 0.62 + k * 0.38)
bubbles(d, 1.85, 5, 0.25, 0.14, (700, 1200))
save("sea_wave", d)
