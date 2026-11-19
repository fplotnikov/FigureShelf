"""Figure Shelf: soft, original action sounds, synthesised here (no samples, no licences).
python3 models/make_sounds.py  ->  FigureShelf.swiftpm/Resources/Sounds/sfx_<name>.m4a
Each sound is gentle: low volume, soft attacks, no sharp highs. Lengths match the actions
(FigureAction.duration in Model.swift): dance 4.0 s, jump 2.4 s, run 4.0 s, spin 1.6 s, wave 2.4 s."""
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

# jump: three hops (the clip hops 3 times in 2.4 s): soft rising "boing", then a soft landing
jump = silence(2.4)
for h in range(3):
    t0 = h * 0.8
    add(jump, tone(260, 620, 0.28, 0.5, harm=(1.0, 0.15)), t0 + 0.16)
    add(jump, thud(0.7), t0 + 0.6)
save("jump", jump)

# run: light pitter-patter of little paws (two soft taps per stride), fading in and out
run = silence(4.0)
t = 0.15
while t < 3.8:
    v = min(1, t / 0.5, (3.9 - t) / 0.5)
    add(run, thud(0.45 * v, 0.07, 140 + random.uniform(-10, 10)), t)
    add(run, thud(0.35 * v, 0.06, 170 + random.uniform(-10, 10)), t + 0.1)
    t += 0.2
save("run", run)

# dance: a little pentatonic tune on soft mallets, 4 beats per second pairs, gentle bass
dance = silence(4.0)
scale = [392, 440, 523, 587, 659, 784]          # G A C D E G
tune = [0, 2, 4, 2, 3, 1, 2, 0, 0, 2, 4, 5, 4, 2, 1, 0]
for i, k in enumerate(tune):
    add(dance, mallet(scale[k], 0.45, 0.45), 0.1 + i * 0.24)
for i in range(8):
    add(dance, mallet([196, 220, 262, 196][i % 4], 0.6, 0.35), 0.1 + i * 0.48)
save("dance", dance)

# wave: a friendly two-note "hel-lo" chime, then a soft sparkle
wave_ = silence(2.4)
add(wave_, mallet(523, 0.7, 0.5), 0.45)
add(wave_, mallet(784, 0.9, 0.5), 0.75)
for i, f in enumerate((1047, 1319, 1568)):
    add(wave_, mallet(f, 0.5, 0.12), 1.15 + i * 0.09)
save("wave", wave_)

# spin: a soft whoosh that rises and falls with the turn, plus a tiny chime at the end
spin = silence(1.6)
add(spin, noise_sweep(1.4, 0.5, 300, 1600), 0.05)
add(spin, mallet(659, 0.5, 0.18), 1.15)
save("spin", spin)

# choose: a very quiet, round "pop" for picking an animal, colour or extra
pop = tone(520, 760, 0.09, 0.5, harm=(1.0, 0.1), decay=5.0) + silence(0.05)
save("pop", [v * 0.5 for v in pop])

# --------------------------------------------------------------------------------------
# Robots: Run lasts 6 s: a soft "click-whirr" change into the vehicle (0-0.8 s), a gentle
# engine for that kind of vehicle, and the change back at the end (5.2-6 s).
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

engines = {
    "car":    lambda: hum(4.4, 0.35, [(72, 1.0), (144, 0.35), (216, 0.1)], am_hz=7, am=0.25, wobble=0.04),
    "truck":  lambda: [a + b for a, b in zip(hum(4.4, 0.4, [(52, 1.0), (104, 0.4)], am_hz=5, am=0.35),
                                             lp_noise(4.4, 0.08, 300))],
    "bike":   lambda: hum(4.4, 0.35, [(92, 1.0), (184, 0.3)], am_hz=19, am=0.45, wobble=0.05),
    "snow":   lambda: hum(4.4, 0.25, [(128, 1.0), (256, 0.25)], am_hz=14, am=0.35, wobble=0.03),
    "digger": lambda: hum(4.4, 0.38, [(56, 1.0), (112, 0.3)], am_hz=4, am=0.3),
    "jet":    lambda: [a + b for a, b in zip(noise_sweep(4.4, 0.45, 250, 900), hum(4.4, 0.12, [(80, 1.0)]))],
    "plane":  lambda: hum(4.4, 0.3, [(110, 1.0), (220, 0.3)], am_hz=28, am=0.5, wobble=0.03),
    "heli":   lambda: lp_noise(4.4, 0.12, 400, am_hz=6, am=0.85),
    "boat":   lambda: [a + b for a, b in zip(lp_noise(4.4, 0.18, 250, am_hz=4, am=0.5),
                                             hum(4.4, 0.18, [(66, 1.0)], am_hz=3, am=0.3))],
}
for kind, make in engines.items():
    buf = silence(RUN)
    change(buf, 0.05, up=True)
    eng = fade(make(), 0.6, 0.6)
    if kind == "heli":     # soft rotor thumps on top of the hiss
        for k in range(int(4.4 * 6)):
            add(eng, thud(0.25, 0.1, 85), k / 6)
        eng = fade(eng, 0.6, 0.6)
    if kind == "digger":   # a gentle clank now and then
        for k in range(4):
            add(eng, mallet(330, 0.25, 0.12), 0.7 + k * 1.0)
    add(buf, eng, 0.8)
    change(buf, 5.15, up=False)
    save("run_" + kind, buf)

# --------------------------------------------------------------------------------------
# Animatronics: a very quiet servo "tick-zzt" on the snaps, and a cheerful calliope for dance.
def servo_tick(vol=0.25):
    n = int(0.07 * SR); out = []; y = 0.0
    a = 1 - math.exp(-2 * math.pi * 1800 / SR)
    for i in range(n):
        y += a * (random.uniform(-1, 1) - y)
        out.append(vol * y * math.exp(-i / (0.02 * SR)))
    add(out, mallet(1400, 0.05, vol * 0.4), 0)
    return out

def calliope(f, sec, vol):     # soft reedy organ pipe
    return tone(f, f, sec, vol, harm=(1.0, 0.5, 0.25, 0.12), decay=1.5)

def anim_ticks(sec, steps, every=1, vol=0.22):
    buf = silence(sec)
    for k in range(0, steps, every):
        add(buf, servo_tick(vol), k * sec / steps + 0.005)
    return buf

d = anim_ticks(4.0, 32, every=4, vol=0.15)
melody = [523, 659, 784, 659, 698, 880, 784, 0, 523, 659, 784, 1047, 988, 784, 659, 0]
for i, f in enumerate(melody):
    if f: add(d, calliope(f, 0.26, 0.32), 0.05 + i * 0.25)
for i in range(8):                       # oom-pah bass
    add(d, calliope([131, 196][i % 2], 0.22, 0.25), 0.05 + i * 0.5)
save("anim_dance", d)
save("anim_jump", anim_ticks(2.4, 18, every=3))
save("anim_run", anim_ticks(4.0, 40, every=2, vol=0.16))
save("anim_wave", anim_ticks(2.4, 14))
save("anim_spin", anim_ticks(1.6, 8))

# ---- dinosaurs: a soft, friendly "rawr", heavy padded footsteps, wing whooshes ----
def rawr(sec=0.9, vol=0.3, f0=150, f1=92):
    """a low, rounded rumble that rises a little then sinks: friendly, not scary"""
    n = int(sec * SR); e = env(n, int(0.12 * SR), int(0.35 * SR)); out = []; ph = 0.0; y = 0.0
    for i in range(n):
        t = i / n
        f = f0 * (1 + 0.12 * math.sin(math.pi * min(1, t * 1.6))) * (f1 / f0) ** t
        ph += 2 * math.pi * f / SR
        trill = 0.75 + 0.25 * math.sin(2 * math.pi * 22 * i / SR)
        v = math.sin(ph) + 0.45 * math.sin(2 * ph) + 0.2 * math.sin(3 * ph) + 0.08 * math.sin(5 * ph)
        y += 0.08 * (random.uniform(-1, 1) - y)          # a breath of soft noise
        out.append(vol * (v * trill + 0.6 * y) * e[i])
    return out

def stomp(vol=0.5):
    return [a + b for a, b in zip(thud(vol, 0.22, 55), thud(vol * 0.4, 0.22, 110))]

d = silence(4.0)
add(d, rawr(1.0, 0.3), 0.15)
for k in range(6): add(d, stomp(0.45), 1.3 + k * 0.45)
add(d, rawr(0.7, 0.22, 170, 110), 3.1)
save("dino_dance", d)
d = silence(2.4); add(d, rawr(1.1, 0.3), 0.2); save("dino_wave", d)
d = silence(4.0)
for k in range(9): add(d, stomp(0.5 if k % 2 == 0 else 0.42), 0.15 + k * 0.42)
save("dino_run", d)
d = silence(2.4); add(d, noise_sweep(0.5, 0.12, 200, 600), 0.2); add(d, stomp(0.6), 1.15); save("dino_jump", d)
d = silence(4.0)
for k in range(5): add(d, noise_sweep(0.55, 0.14, 180, 520), 0.1 + k * 0.62)
add(d, noise_sweep(1.0, 0.08, 150, 300), 3.0)
save("dino_fly", d)
