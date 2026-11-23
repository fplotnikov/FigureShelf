"""Figure Shelf: a dance tune for each kind of figure, synthesised here (no samples, no licences).
python3 models/make_dance_music.py  ->  FigureShelf.swiftpm/Resources/Sounds/sfx_dance_<kind>.m4a

Same rules as models/make_sounds.py (whose helpers this reuses in spirit): gentle, quiet (peak
-12 dBFS), soft attacks, no sharp highs, exactly as long as the dance (4.0 s) so "Again" repeats
it in time. Animals keep the marimba tune (sfx_dance) and animatronics keep their calliope
(sfx_anim_dance); this script adds the other three:

  dino      prehistoric groove: deep frame drums and log drums, a bone shaker, a low wooden
            flute line and two friendly rawrs
  robot     friendly electro tune: soft square-wave arpeggio, a gentle electronic beat
            (soft kick and tick), and beep-boop "talk"
  creature  magical tune: music-box bells on a dreamy (whole-tone) scale, a harp sweep,
            a soft shimmering pad and little sparkles
"""
import math, random, struct, wave, os, subprocess
SR = 22050
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "FigureShelf.swiftpm", "Resources", "Sounds")
os.makedirs(OUT, exist_ok=True)
random.seed(23)
LEN = 4.0


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


def tone(f0, f1, sec, vol, harm=(1.0,), decay=None, attack=0.01, release=0.06, vib=0.0):
    n = int(sec * SR); e = env(n, max(1, int(attack * SR)), max(1, int(release * SR))); out = []; ph = 0.0
    for i in range(n):
        t = i / n; f = f0 * (f1 / f0) ** t
        if vib: f *= 1 + vib * math.sin(2 * math.pi * 5.0 * i / SR)
        ph += 2 * math.pi * f / SR
        v = sum(h * math.sin(ph * (k + 1)) for k, h in enumerate(harm))
        d = math.exp(-t * decay) if decay else 1.0
        out.append(vol * v * e[i] * d)
    return out


def noise(sec, vol, fc, decay):
    n = int(sec * SR); out = []; y = 0.0
    a = 1 - math.exp(-2 * math.pi * fc / SR)
    for i in range(n):
        y += a * (random.uniform(-1, 1) - y)
        out.append(vol * y * math.exp(-i / (decay * SR)))
    return out


def note(name):
    names = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}
    semi = names[name[0]] + (1 if "#" in name else 0) - (1 if "b" in name[1:] else 0) + 12 * (int(name[-1]) - 4)
    return 440 * 2 ** (semi / 12)


def bell(f, sec, vol):
    n = int(sec * SR); out = []
    parts = [(1.0, 1.0, 3.0), (2.0, 0.35, 5.0), (2.76, 0.16, 7.0), (5.4, 0.05, 11.0)]
    e = env(n, int(0.004 * SR), int(0.05 * SR))
    for i in range(n):
        t = i / SR
        v = sum(a * math.sin(2 * math.pi * f * m * t) * math.exp(-t * d) for m, a, d in parts)
        out.append(vol * v * e[i])
    return out


def pluck(f, sec, vol):
    n = int(sec * SR); p = max(2, int(SR / f))
    buf = [random.uniform(-1, 1) for _ in range(p)]
    out = []
    for i in range(n):
        v = buf[i % p]
        buf[i % p] = 0.5 * (v + buf[(i + 1) % p]) * 0.995
        out.append(vol * v)
    e = env(n, int(0.003 * SR), int(0.05 * SR))
    return [o * k for o, k in zip(out, e)]


def save(name, buf):
    f = int(0.03 * SR)
    for i in range(f):
        buf[i] *= i / f; buf[-1 - i] *= i / f
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


# ---------------------------------------------------------------- dinosaurs: prehistoric groove
def frame_drum(vol, f=70):       # deep, round, soft
    return [a + b for a, b in zip(tone(f * 1.5, f, 0.35, vol, harm=(1.0, 0.25), decay=7.0, attack=0.003),
                                  noise(0.35, vol * 0.15, 400, 0.03))]


def log_drum(f, vol):            # hollow wooden tone
    return tone(f, f * 0.97, 0.28, vol, harm=(1.0, 0.0, 0.35), decay=9.0, attack=0.003)


def shaker(vol): return noise(0.09, vol, 3000, 0.02)


def low_flute(f, sec, vol): return tone(f, f, sec, vol, harm=(1.0, 0.2, 0.06), attack=0.08, release=0.15, vib=0.008)


def rawr(sec, vol, f0, f1):
    n = int(sec * SR); e = env(n, int(0.12 * SR), int(0.3 * SR)); out = []; ph = 0.0
    for i in range(n):
        t = i / n
        f = f0 * (1 + 0.12 * math.sin(math.pi * min(1, t * 1.6))) * (f1 / f0) ** t
        ph += 2 * math.pi * f / SR
        trill = 0.75 + 0.25 * math.sin(2 * math.pi * 22 * i / SR)
        out.append(vol * (math.sin(ph) + 0.45 * math.sin(2 * ph) + 0.2 * math.sin(3 * ph)) * trill * e[i])
    return out


d = silence(LEN)
beat = 0.5                        # 120 bpm
for i in range(8):
    t = 0.03 + i * beat
    add(d, frame_drum(0.5 if i % 2 == 0 else 0.35), t)
    add(d, log_drum(note(["D3", "F3", "A3", "F3"][i % 4]), 0.28), t + 0.25)
    add(d, shaker(0.12), t + 0.125); add(d, shaker(0.09), t + 0.375)
line = [("D4", 0.75), ("F4", 0.25), ("G4", 0.5), ("A4", 0.5), ("G4", 0.5), ("F4", 0.5), ("D4", 0.75)]
t = 0.3
for n_, dur in line:
    add(d, low_flute(note(n_), dur * 0.95, 0.2), t); t += dur * 0.8
add(d, rawr(0.6, 0.16, 160, 105), 0.05)
add(d, rawr(0.55, 0.14, 180, 120), 3.35)
save("dance_dino", d)

# ---------------------------------------------------------------- robots: friendly electro tune
def sq(f, sec, vol): return tone(f, f, sec, vol, harm=(1.0, 0, 1 / 3, 0, 1 / 5, 0, 1 / 7), decay=5.0, attack=0.004)
def kick(vol): return tone(120, 45, 0.18, vol, harm=(1.0,), decay=10.0, attack=0.002)
def tick(vol): return noise(0.05, vol, 4500, 0.012)
def blip(f0, f1, vol): return tone(f0, f1, 0.1, vol, harm=(1.0, 0, 0.25), decay=6.0, attack=0.003)


d = silence(LEN)
arp = ["A4", "C5", "E5", "A5", "F4", "A4", "C5", "F5", "G4", "B4", "D5", "G5", "E4", "G#4", "B4", "E5"]
for i, n_ in enumerate(arp):
    add(d, sq(note(n_), 0.22, 0.17), 0.03 + i * 0.25)
for i in range(8):
    t = 0.03 + i * 0.5
    add(d, kick(0.45), t)
    add(d, tick(0.12), t + 0.25)
    add(d, sq(note(["A2", "F2", "G2", "E2"][i // 2]), 0.45, 0.16), t)
for t, (a, b) in zip([0.9, 1.05, 2.9, 3.05, 3.2], [(600, 1000), (1000, 750), (700, 1200), (1200, 900), (900, 1300)]):
    add(d, blip(a, b, 0.11), t)
save("dance_robot", d)

# ---------------------------------------------------------------- creatures: magical tune
def pad(freqs, sec, vol):
    n = int(sec * SR); e = env(n, int(0.8 * SR), int(0.9 * SR)); out = []
    for i in range(n):
        t = i / SR
        v = sum(math.sin(2 * math.pi * f * t * (1 + 0.002 * math.sin(2 * math.pi * 0.7 * t + k)))
                for k, f in enumerate(freqs))
        out.append(vol * v / len(freqs) * e[i])
    return out


def sparkle(vol): return tone(2800, 3300, 0.12, vol, decay=8.0, attack=0.003, release=0.03)


d = silence(LEN)
add(d, pad([note("C4"), note("E4"), note("G#4"), note("D5")], LEN, 0.22), 0)    # dreamy whole-tone chord
melody = ["C6", "D6", "E6", "F#6", "G#6", "F#6", "E6", "D6", "E6", "G#6", "A#6", "G#6", "F#6", "E6", "D6", "C6"]
for i, n_ in enumerate(melody):
    add(d, bell(note(n_) / 2, 0.8, 0.22 if i % 4 == 0 else 0.16), 0.05 + i * 0.25)
for i, n_ in enumerate(["C4", "D4", "E4", "F#4", "G#4", "A#4", "C5", "D5", "E5", "F#5"]):   # harp sweep up
    add(d, pluck(note(n_), 0.7, 0.14), 0.05 + i * 0.045)
for i, n_ in enumerate(["E5", "D5", "C5", "A#4", "G#4", "F#4", "E4", "D4"]):               # and gently down
    add(d, pluck(note(n_), 0.7, 0.1), 2.05 + i * 0.05)
for t in [0.6, 1.4, 2.6, 3.4]:
    add(d, sparkle(0.05), t)
save("dance_creature", d)
