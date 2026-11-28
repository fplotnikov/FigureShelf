# Figure Shelf (version 2)

A calm toy app: pick an animal from the shelf, change its color, dress it up with a hat,
glasses, a mask and something round its neck, then make it dance, jump, run, spin or wave. Tap **See in my room** to put
it on the real floor with the camera.

Everything is open from the start. No story, no missions, no locks, no scores, no
popups. Soft sounds play only when a move or a choice is tapped (speaker button turns them off). Every change can be undone with the round arrow button, and the
app remembers the last animal when it is opened again.

## What's inside

| | |
|---|---|
| Animals | Bunny, Kitty, Bear, Penguin, Frog, Fox, plus Lion, Zebra, Ostrich, Horse, Tiger, Beaver, Raccoon, Elephant, Hippo, Rhino, Mouse, Turtle, plus Shark, Mole, Bee, Parrot, Koala, Panda, plus Deer, Red Panda, Moose, Kangaroo, Giraffe, Capybara |
| Animatronics | Raccoon, Moth, Crocodile, Ram, Pelican, Armadillo, Lynx, Frog Singer, Vulture, Anteater, plus Elephant, Pangolin, Ostrich, Lobster, Chameleon, Walrus, Kangaroo, Sloth (Fedir's vintage theme-park performers; they move in stiff servo steps) |
| Robots | Supercar, Jet, Motorcycle, Big Truck, Helicopter, Rally, Seaplane, Snowmobile, Excavator, Speedboat, plus Locomotive, Submarine, Tractor, City Bus, Forklift, Cable Car, Lunar Rover, Airship (Fedir's robot designs; each turns into its vehicle to run) |
| Creatures | Mosskip, Glassfin, Cindermole, Cloudlope, Thimblebat, Pebblenewt, Bloomusk, Velvetide, Lanternquill, Dunewisp, plus Pleatbill, Coilusk, Siftrunk, Spindlecrab, Ripplemantis, Tuftwhale, Knotcko, Cupspinner (Fedir's own imaginary creatures) |
| Colors | Normal, Sunny, Ocean, Mint, Berry, Night, Snow |
| Patterns (the 30 animals) | Plain, Dots, Stripes, Checks, Stars, Hearts, on any color |
| Accessories (one per group, all at once) | Hats: party hat, crown, top hat, cowboy, beanie, cap, wizard, pirate, chef, flower crown, viking, propeller, flower clip, Santa, sun hat, unicorn horn, bunny ears, builder's hard hat. Glasses: sunglasses, round, hearts, stars, goggles, 3D, monocle, googly eyes, robot visor, pixel shades, cat-eye. Masks: hero, butterfly, red nose, moustache, ninja, snorkel, white beard, whiskers, piggy snout. Neck: bow tie, scarf, cape, lei, medal, tie, pearls, bell collar, fairy wings, backpack |
| Actions | Dance, Jump, Run, Spin, Wave, plus **Again** to keep repeating |

On the shelf, drag sideways on the animal to turn it around. In the room, tap the
floor to move it, pinch to resize, twist with two fingers (or use the round turn buttons) to
turn it. In the room the menu slides away after 15 seconds without a touch; any touch brings it
back, and the tip at the top fades after 5 seconds.

All six animals are animated 3D toy figures: the look was generated with Meshy from
original prompts (cute chibi vinyl toys, not any existing character), and the moves are
our own (ear and tail bones and toy-style dance, jump, run, wave and idle clips made in
Blender). Each color is a pre-painted texture. The older shape-built animals are still in
the code and are used only if a model file fails to load.

## How the animals are made

| Step | Tool | Script / output |
|---|---|---|
| Design image (front view, A-pose) | Meshy text-to-image (nano-banana-2) | `models/meshy_<animal>/<animal>_design.png` |
| 3D model, ~20k triangles, painted texture | Meshy image-to-3D (meshy-t2.5 smart topology + meshy-n1 texture) | `<animal>_static.glb` |
| Body skeleton + skin weights | Meshy auto-rig | `<animal>_rigged.glb` |
| Ear/tail bones, our clips, 7 color textures, hat/glasses fit, ARKit USDZ | Blender 5.3, headless | `models/make_meshy_animal.py` -> `models/<animal>.usdz`, `<animal>_clips.json`, `<animal>_skins/` |

Rebuild one animal: `blender -b --factory-startup --python models/make_meshy_animal.py -- fox`
then copy `models/fox.usdz`, `fox_clips.json` and the skins (as JPEG) into
`FigureShelf.swiftpm/Resources/`. Every USDZ passes `usdchecker --arkit`.

All clips share one timeline at 30 fps: idle 1-60, dance 61-180, jump 181-252, run
253-372, wave 373-444 (seconds are in each `_clips.json`).

The first, all-Blender Bunny (`models/make_bunny.py`) is kept in `models/blender_bunny/`
as a fallback.

## How the creatures are made

Fedir drew ten imaginary creatures (pictures in `creatures/`). Each became a figure like this:

| Step | Tool | Output |
|---|---|---|
| 3D model from Fedir's picture, ~21k triangles, painted texture | Meshy image-to-3D (meshy-t2.5 smart topology + meshy-n1 texture), 15 credits each | `models/creatures/<name>/<name>_static.glb` |
| Measure the body (front/side/top/bottom views with a 2 cm grid) | Blender, `models/creatures/probe_creature.py` | `models/creatures/probe/` |
| Our own skeleton, skin weights, moves, colors, extras fit, thumbnail, ARKit USDZ | Blender, `models/make_meshy_animal.py` (creature section) | `models/<name>.usdz`, `_clips.json`, `_skins/`, `_thumb.png` |

No Meshy rig is used for the creatures. The script turns each model so its body runs
front-to-back, builds a spine (hips, spine, chest, neck, head) and chains for legs, ears,
tails, wings (Thimblebat), arms (Cindermole) and tentacles (Velvetide) from points measured
on the probe views, weights them with Blender's bone heat, and bakes one set of moves per
body kind: four-legged (dance = bounce and sway with paw taps, jump = hop, run = trot in
place, wave = lift a front paw), upright (Cindermole), bat (wings flap) and cuttlefish
(tentacles wiggle). Ears, ribbons and tails sway as soft chains. Then the figure is turned
back so it stands like Fedir's picture; when it runs, the app turns it to run head first
(`bodyYaw` in the clips JSON). Same clip layout as the animals.

Colors: **Normal** is the Meshy texture exactly. The other colors rotate the hue of the whole
texture (greys, whites and dark eyes barely change). Night also darkens, Snow fades to white.

Rebuild one creature, then copy it into the app (also checks it with `usdchecker --arkit`):

    blender -b --factory-startup --python models/make_meshy_animal.py -- mosskip
    models/install_creature.sh mosskip

### The second set of creatures (11–18)

Nov 22, 2026: Pleatbill, Coilusk, Siftrunk, Spindlecrab, Ripplemantis, Tuftwhale, Knotcko and
Cupspinner. Pictures are `creatures/11-…png` to `18-…png` and task ids are in
`models/creatures/meshy_tasks.txt`. They use the same path as the first ten; their entries are at
the end of `CREATURES` in `make_meshy_animal.py` (read from the probe views).

How each one moves:

- **Pleatbill and Knotcko** stand on two legs. Pleatbill's legs are found automatically.
  Knotcko's raised leg, its arms and its knotted tail (soft sway) are placed by hand.
- **Coilusk, Siftrunk, Spindlecrab, Ripplemantis and Cupspinner** walk on four or more legs.
  - The legs are found automatically (`legs=dict(top, count)`), except Coilusk's four sucker legs,
    which join under its belly and are placed by hand.
  - The legs that moves use are the front and back pair. Middle legs (the crab's, the mantis's and
    the spider's extras) ride along with the body.
- **Extra parts:**
  - The crab's claws and the mantis's fan arms are arms, so they wave.
  - The mantis's antennae sway like ears.
  - Siftrunk's trunk is a soft chain on the head.
  - Coilusk's swirl shell sways a little.
- **Tuftwhale** uses the bat moves: its big side fins flap like wings, its lower fins are its legs,
  and its tail sways.
- **Coilusk and Siftrunk** stand at an angle in their pictures (yaw 38° and 36°). Siftrunk is built
  a little bigger (0.27 m long) because it is so low.

Accessory fit fixed by hand: `python3 models/creatures2/fit_fix.py` (Tuftwhale's hat, the crab's
and Siftrunk's bow ties and Siftrunk's hat). Screenshots: `screenshots-creatures-2/`.

## How the animatronics are made

Fedir designed ten vintage theme-park performers (pictures in `animatronics/`). Same path as the
robots: Meshy image-to-3D (15 credits) and Meshy auto-rig (5 credits), then
`models/make_meshy_animal.py` (animatronic branch) and `models/install_creature.sh`.

Their moves are "servo" style (`servo()` in the script): each clip only moves in steps. Inside a
step the pose snaps in about 0.12 s with a small overshoot and settle, then holds still. Idle looks
left and right in snaps, dance is a showtime routine (arm raises, head bobs and tilts, waist pivots,
8 snaps a second), the jump keeps the knees locked, run is a stiff march, wave goes up in steps.
In the app, Spin turns in eight clunky steps like a turntable and the turns while running round
are stepped too. Sounds: very quiet servo ticks on the snaps and a little calliope tune for the
dance (`models/make_sounds.py`). Each arm is settled on its own (performers often hold one arm out).

### The second set of animatronics (11–18)

Nov 22, 2026: Elephant, Pangolin, Ostrich, Lobster, Chameleon, Walrus, Kangaroo and Sloth.
Pictures are `animatronics/11-…png` to `18-…png` and task ids are in
`models/animatronics2/meshy_tasks.txt`.

- **Seven of them** use the same path as the first ten (`ANIMATRONICS` in `make_meshy_animal.py`):
  Meshy model, Meshy auto-rig, our stiff servo-step moves, the quiet servo sounds and the calliope
  dance tune.
- **Different file names:** Elephant, Ostrich and Kangaroo are also toy animals, so their files and
  app cases are `showelephant`, `skateostrich` and `showkangaroo`. The chooser shows the plain
  names, in the Animatronics section.
- **The Ostrich:** Meshy refused to rig her (thin legs on roller skates; no credits charged). She
  gets our own two-legged creature rig instead (`CREATURES["skateostrich"]`, static model in
  `models/creatures/skateostrich/`). Her moves are the smoother creature ones rather than servo
  steps; she still has the animatronic sounds and dance tune.
- **Screenshots:** `screenshots-animatronics-2/`.

## How the robots are made

Fedir designed ten robots that are also vehicles (pictures in `robots/`).

| Step | Tool | Output |
|---|---|---|
| Robot 3D model from Fedir's picture | Meshy image-to-3D (meshy-t2.5 + meshy-n1), 15 credits | `models/creatures/<name>/<name>_static.glb` |
| Robot skeleton + skin weights | Meshy auto-rig, 5 credits | `models/meshy_<name>/<name>_rigged.glb` |
| Vehicle picture in the robot's own colours (no logos) | Meshy image-to-image from the robot picture (nano-banana-2), 6 credits | `models/robots/vehicles/<name>_vehicle.png` |
| Vehicle 3D model | Meshy image-to-3D, 15 credits | `models/robots/vehicles/<name>_vehicle.glb` |
| Robot moves, colours, extras fit, thumbnail, USDZ | Blender, `models/make_meshy_animal.py` (robot branch) | `models/<name>.usdz` ... |
| Vehicle: facing forward, toy size, 1024 px texture, USDZ | Blender, `models/make_vehicle.py` | `models/<name>_vehicle.usdz`, `_vehicle.json` |

Robot moves: a calm idle with a slow head turn, a stiff "robot dance" of held poses, jump and a
big wave. **Run** is different for robots (6 s, done in the app, `FigureRig.robotRun`): the robot
spins and folds away while its vehicle grows on the same spot (0.8 s), the vehicle travels like
itself, then changes back. Cars, the truck and the snowmobile drive the circle with a little
bounce and lean, the motorcycle leans most, the excavator crawls a smaller circle, the jet and
seaplane take off, fly a banked loop and land, the helicopter lifts straight up, circles with a
spinning rotor disc and comes down, the speedboat glides with a gentle bob and roll. Each kind has
its own soft engine sound plus a soft "click-whirr" for the change (`models/make_sounds.py`).
Vehicles keep their Normal colours.

Rebuild one robot: `blender -b --factory-startup --python models/make_vehicle.py -- jet`, then
`blender -b --factory-startup --python models/make_meshy_animal.py -- jet`, then
`models/install_creature.sh jet`.

### The second set of robots (11–18)

Nov 22, 2026: Locomotive, Submarine, Tractor, City Bus, Forklift, Cable Car, Lunar Rover and
Airship. Pictures are `robots/11-…png` to `18-…png` and task ids are in
`models/robots/meshy_tasks.txt`. They use the same path as the first ten (`ROBOTS` in
`make_meshy_animal.py`, `KINDS` in `make_vehicle.py`). The Lunar Rover's vehicle model came out
facing backwards, so it is turned round (`TURN` in `make_vehicle.py`).

Each vehicle has its own way of travelling on Run (`FigureRig.robotRun`):

- **Locomotive:** a steady chug with a small rock.
- **City Bus:** a smooth drive with a little sway.
- **Tractor:** slow and bumpy, with a big-wheel wobble.
- **Forklift:** a smaller circle, tipping back now and then as if lifting its forks. The forks
  themselves do not move; the vehicle is one piece.
- **Submarine:** floats just above the ground with its nose dipping and rising like a dive.
- **Cable Car:** rises as if hanging from a cable and glides round with a pendulum sway (no cable
  is drawn).
- **Lunar Rover:** floaty low-gravity hops.
- **Airship:** lifts off slowly and floats a wider loop.

Engine sounds (soft, 6 s, with the change click-whirr) come from
`models/make_vehicle_sounds2.py`: `sfx_run_train`, `_sub`, `_tractor`, `_bus`, `_forklift`,
`_cable`, `_rover` and `_airship`. Screenshots: `screenshots-robots-2/`.

### Meshy credits used

| | Credits |
|---|---|
| Kitty test (image 6, model 15, rig 5, two Meshy animations 6) | 32 |
| Bear, Penguin, Frog, Fox, Bunny (image 6 + model 15 + rig 5 each, no retries) | 130 |
| Ten creatures (image-to-3D 15 each, no retries) | 150 |
| Ten robots: model 15 + rig 5 + vehicle picture 6 + vehicle model 15 each, no retries | 410 |
| Ten animatronics: model 15 + rig 5 each, no retries | 200 |
| **Total** | **922** (balance afterwards: about 2,178 of 3,100) |

Second batch: 12 more animals and 12 dinosaurs (Nov 2026)

| | Credits |
|---|---|
| 12 animals: picture 6 + model 15 + rig 5 each | 312 |
| 12 toy-style dinosaurs, replaced before use: pictures 72 + models 180 + 6 Meshy rigs 30 | 282 |
| 12 realistic dinosaur pictures + 2 retries (Velociraptor, Allosaurus) | 84 |
| 12 realistic dinosaur models (meshy-t2.5 smart topology + meshy-n1) | 180 |
| **Total** | **858** of the 880 allowed (balance afterwards 1,320) |

Third batch: 6 more animals (Nov 20, 2026)

| | Credits |
|---|---|
| Shark, Mole, Bee, Parrot, Koala, Panda: picture 6 + model 15 + rig 5 each, no retries | **156** (balance afterwards 1,164) |

Fourth batch: 6 more animals (Nov 22, 2026)

| | Credits |
|---|---|
| Deer, Red Panda, Moose, Kangaroo, Giraffe, Capybara: picture 6 + model 15 + rig 5 each, no retries | **156** (balance afterwards 1,008) |

Fedir's second set of creatures (Nov 22, 2026)

| | Credits |
|---|---|
| Pleatbill, Coilusk, Siftrunk, Spindlecrab, Ripplemantis, Tuftwhale, Knotcko, Cupspinner: image-to-3D 15 each from Fedir's pictures, no retries | **120** (balance afterwards 888) |

Fedir's second set of robots (Nov 22, 2026)

| | Credits |
|---|---|
| Locomotive, Submarine, Tractor, City Bus, Forklift, Cable Car, Lunar Rover, Airship: robot model 15 + rig 5 + vehicle picture 6 + vehicle model 15 each, no retries | **328** (balance afterwards 560) |

Fedir's second set of animatronics (Nov 22, 2026)

| | Credits |
|---|---|
| Elephant, Pangolin, Ostrich, Lobster, Chameleon, Walrus, Kangaroo, Sloth: model 15 each + 7 rigs at 5 (the Ostrich rig was refused, free) | **155** (balance afterwards 405) |

Ten more prehistoric figures (Nov 28, 2026)

| | Credits |
|---|---|
| Styracosaurus, Iguanodon, Carnotaurus, Therizinosaurus, Gallimimus, Dilophosaurus, Mosasaur, Elasmosaurus, Ichthyosaur, Megalodon: picture 6 + model 15 each, no Meshy rig, no retries | **210** (balance afterwards 195) |

## Ten more prehistoric figures (6 dinosaurs, 4 sea species)

Nov 28, 2026, in the Dinosaurs group, all available straight away. Art: `dinosaurs/13-…png` to
`22-…png` (Meshy text-to-image, nano-banana-2, the same museum style as the first 12), 3D:
meshy-t2.5 smart topology 20k + meshy-n1, no Meshy rig. Task ids: `models/new10dino/meshy_tasks.txt`.
Calm poses, closed mouths, feathers on Therizinosaurus and Gallimimus.

- **Dinosaurs** (Styracosaurus, Iguanodon, Carnotaurus, Therizinosaurus, Gallimimus, Dilophosaurus):
  the same path as the 12 dinosaurs below (`_dino(...)` entries in `models/make_meshy_animal.py`, our
  own rig, same moves, sounds and dance tune). Therizinosaurus has long arms, so its wave lifts the
  arm half as far (`arm_wave`).
- **Sea species** (Mosasaur, Elasmosaurus, Ichthyosaur, Megalodon): a new swimming kind (`_sea(...)`,
  `derive_swim_skeleton`). The spine runs along the body centre line (top of the body just off the
  midline, bottom on the midline, so dorsal fins and flippers don't pull it about), the tail has six
  bones, the neck is split into three bones for Elasmosaurus, and two-bone flippers are found as the
  parts that stick out sideways (Megalodon: the two pectoral fins; its tail does the rest). They
  float 3 cm above the ground: the rest pose itself is lifted, so hats and glasses (measured at rest)
  sit right. Clips, same frame layout: idle = a gentle floating sway, dance = a body wave with
  flipper strokes, jump = a breach leap (dip, arc out nose up, over the top, back in and bob),
  run = a swim loop (the app moves it round the circle), wave = a flipper wave (Megalodon: a friendly
  tail flick). Megalodon keeps its mouth closed.
- **Sounds:** the sea species get soft water swishes, a splash and bubbles for run, jump and wave
  (`python3 models/new10dino/make_sea_sounds.py` -> `sfx_sea_run/jump/wave.m4a`; `SoundBoard`
  `swimmer:`); dance keeps the prehistoric tune.
- **Rebuild:** `blender -b --factory-startup --python models/make_meshy_animal.py -- megalodon`, then
  `models/install_creature.sh megalodon`. Eye points for the sea species are set with `eye=` (a
  fraction of the head length from the snout) after checking the glasses in the simulator.
- **Screenshots:** `screenshots-dinosaurs-2/` (`fs_*` on the shelf, `wear_*` with a hat, glasses and
  bow tie, `move_*` mid-move, `fs_new10_sheet.png` all ten). `models/new10dino/shot.sh` takes them in
  the Simulator (the look goes in as a launch argument; autoplay starts about 6.5 s after launch).
- Build 4 (version 1.1) in the Xcode project and Package.swift.

## The fourth batch (Deer, Red Panda, Moose, Kangaroo, Giraffe, Capybara)

Nov 22, 2026, the same path as the batch below: `ANIMALS2` in `models/make_meshy_animal.py`, art in
`animals4/`, task ids in `models/new6b/meshy_tasks.txt`. Python was swapped for Capybara (a snake
has no legs for the two-legged rig and moves).

- **Deer picture:** the deer stood on a display disc. I painted the disc out before the 3D step
  (`animals4/01-deer-original.png` is the untouched picture).
- **Pattern maps:** baked with `bake_position_map.py` (768, then 512 px in the app). All 30 maps
  together are 9.1 MB.
- **Fit by hand:** `python3 models/new6b/fit_fix.py`, run after `measure_nose.py`.
  - The glasses had been placed at the snout tip, so they slid sideways in the angled shelf view;
    they now sit at eye height on the face.
  - The moose's dark eyes on dark fur were missed: its eyes, nose and bow tie are set by hand.
  - The red panda's scarf went round its muzzle; it now sits under the chin.
  - The kangaroo's hats sank between its ears.
- **Finding eyes:** `models/new6b/find_eyes.py -- <name> [lumMax] [minY]` finds the eye centres from
  the colour texture and the position map (the darkest spots on the front of the head).
- **Screenshots:** `screenshots-new-animals-4/`.

## The six newest animals (Shark, Mole, Bee, Parrot, Koala, Panda)

Same path as the 12 animals below (`ANIMALS2` in `models/make_meshy_animal.py`): Meshy picture
(nano-banana-2, art in `animals3/`), image-to-3D (meshy-t2.5 smart topology 20k + meshy-n1, T-pose),
Meshy auto-rig, then the Blender script and `models/install_creature.sh`. Task ids are in
`models/new6/meshy_tasks.txt`. The mole's picture stood on a pedestal: it was painted out before the
3D step (`animals3/02-mole-original.png` is the untouched one). The shark and the bee stand upright
like the other toys (the shark on short legs with fin arms, the bee's wings ride on the back).

Fit by hand after a rebuild: `measure_nose.py` for each, then `python3 models/new6/fit_fix.py`.
It fixes the bow tie and scarf on the round one-piece bodies (shark, parrot: the ring is centred
forward with `neckCZ`), the mole's bow tie (under the chin, not on the snout), the parrot's glasses
(on the eyes, not the beak tip), the koala's eyes (the dark nose had been read as the eyes) and the
shark's hat (on the head beside the fin). `models/new6/probe_fit.py -- <name>` prints the surface
profile used to pick the numbers.

## The 12 new animals and the dinosaurs

- **Animals** (Lion, Zebra, Ostrich, Horse, Tiger, Beaver, Raccoon, Elephant, Hippo, Rhino, Mouse,
  Turtle): toy style, Meshy humanoid rig, same moves as the other animals. Art: `animals2/`.
  The raccoon is called `raccoonkid` in files (the animatronic is `raccoon`). Eye points are read by
  hand from front views: `models/new24/eye_fix.py` (run it after a rebuild, then `measure_nose.py`).
- **Dinosaurs** (T. rex, Triceratops, Stegosaurus, Velociraptor, Brachiosaurus, Spinosaurus,
  Ankylosaurus, Pteranodon, Parasaurolophus, Diplodocus, Pachycephalosaurus, Allosaurus): realistic,
  museum-style models (art in `dinosaurs/`, the first toy-style art in `dinosaurs/toy_style_old/`).
  They use our own rig: `derive_dino_skeleton` in `models/make_meshy_animal.py` finds the spine, tail,
  legs, small arms and wings from the mesh. Moves are slow and heavy: stomps with a tail swish, a heavy
  hop that settles, a forward-leaning run (four-legged ones trot), a tiny-arm wave (or a lifted front
  foot); Pteranodon flaps, takes off and glides its run loop. Sounds: a soft rawr (dance, wave), padded
  footsteps (run), wing whooshes (Pteranodon). Colors stay natural: Normal is the real texture, the
  others are gentle hue shifts. Rebuild one: `blender -b --factory-startup --python
  models/make_meshy_animal.py -- trex`, then `models/install_creature.sh trex`.

### Licenses

- **Meshy outputs:** on a paid Meshy plan the generated models belong to the account owner
  and may be used commercially, as long as they are not published to the Meshy Community
  and the prompts/inputs do not infringe anyone's rights (our prompts are original text).
  Free-plan outputs would instead be CC BY 4.0 (attribution required). Meshy's terms also
  forbid using the outputs to train competing AI models. Sources: Meshy help center
  ("What is the ownership of the generated models?",
  https://help.meshy.ai/en/articles/10137554-what-is-the-ownership-of-the-generated-models;
  "Can I use my generated assets for commercial projects?",
  https://help.meshy.ai/en/articles/9992001-can-i-use-my-generated-assets-for-commercial-projects)
  and the Terms of Service (https://www.meshy.ai/terms-of-use). Check the current terms
  before publishing to the App Store.
- **Rigs and clips:** the ear/tail bones, weights and all app animations are made by our
  own scripts; Meshy's preset animations are not shipped.
- **Blender** (GPL) is only a tool here; its license does not apply to the models it exports.

## Patterns

The **Colors** tab has a second row for the 24 animals: **Plain, Dots, Stripes, Checks, Stars
and Hearts**. Any pattern goes with any of the 7 colors (6 x 7 looks per animal). For dinosaurs,
creatures, robots and animatronics the row is hidden. Each change is one undo step, it is saved with
the look, and Reset sets it back to Plain. No Meshy credits were used.

How it works: Meshy textures are cut into many small pieces, so a pattern drawn flat on the
picture would break at every seam. `models/bake_position_map.py` (Blender, headless) bakes a
**position map** for each animal: every texel of its texture gets the 3D point on the body it
belongs to (rest pose).

    blender -b --factory-startup --python models/bake_position_map.py -- panda 768
    sips -Z 512 models/panda_pos.png --out FigureShelf.swiftpm/Resources/panda_pos.png

It also writes `"posBox"` (the body's box) into `<animal>_clips.json`. The 24 maps are 512 px PNGs,
7.3 MB in all. In the app, `PatternPainter.swift` works the pattern out from those 3D points, so
dots stay round and stripes run round the body without breaks. Dots and checks are a 3D grid and
stripes are bands round the body. Stars and hearts are wrapped round the body (and laid flat on the
top of the head). Each pattern is painted over the chosen color texture.

- **Pattern colors:** each color has its own pattern ink: orange on Sunny, deep blue on Ocean,
  teal on Mint, purple on Berry, gold on Night and sky blue on Snow. Normal uses a lighter or deeper
  shade of the fur.
- **Details stay:** eyes, noses and dark lines keep their own color.
- **Painting:** it takes a moment, in the background, the first time a color and pattern are
  combined (the plain color shows meanwhile). Then it is kept for that session.

Screenshots: `screenshots-patterns/`.

## Things to wear

The **Accessories** tab has four groups: Hats, Glasses, Masks and Neck (48 things in all; 17 were added in Nov 2026: Santa, sun hat, unicorn, bunny ears, builder; googly, visor, pixel, cat-eye; beard, whiskers, piggy; tie, pearls, bell, wings, backpack). One item from each group
can be worn at the same time; tap a worn item again (or "None") to take it off, and every
change is one undo step. The snorkel mask covers the eyes, so glasses hide while it is on.
All items are built in code from simple rounded shapes (`FigureBuilder.addWear`), so they
add nothing to the app size. They sit on the measured head top, eyes and neck of each
figure (clips JSON `fit`), turn with the face, and follow the head and neck bones while the
figure moves. The round **Reset** button next to undo takes everything off, sets the
color back to Normal, stops the move and turns the figure back to its starting angle (it keeps
the chosen animal); one Undo brings the look back. The red nose and moustache sit on each figure's nose tip, measured by
`models/measure_nose.py` (and set by hand with `models/pick_nose.py` where the snout is
unusual). Older saved looks with one extra are moved into the right slot.

## App icon

The icon (Nov 2026) is a clay-style bunny in a party hat between a fox and a panda on a little
wooden shelf, on a warm orange background. Fedir picked it from options made with Figma's image
generator, in the same clay style as the Figure Worlds icon, so the two apps look like one family.
1024 px, sRGB, no transparency. It lives in `FigureShelf.swiftpm/Assets.xcassets/AppIcon.appiconset`;
the Xcode project (`FigureShelf-Xcode/`, used for App Store builds) points at the same asset catalog,
so there is only one file to change. Copies in `icon/`: `AppIcon-figma-1024.png` (this icon),
`AppIcon-figma-kitten-1024.png` (an unused option: kitten on a turntable), `AppIcon-1024-old.png`
(the earlier Blender-rendered Kitty, `models/make_icon.py -- c`, with options A and B and a size
test sheet), and `home-screen.png` (both apps' icons on the home screen).

## Sounds

All sounds are original: `models/make_sounds.py` synthesises them (sine tones, soft mallet
notes, filtered noise; no samples) into `FigureShelf.swiftpm/Resources/Sounds/`, quiet
(peaks at -12 dBFS) with soft starts and ends. Each one is as long as its move.

| Sound | What it is like |
|---|---|
| Jump | a soft rising "boing" at each of the 3 hops, then a soft landing thump |
| Run | light pitter-patter of little paws that fades in and out |
| Dance | each kind of figure has its own 4 s tune: **animals** a cheerful marimba tune with a gentle bass; **animatronics** a calliope (vintage theme park); **dinosaurs** a prehistoric groove (deep frame drums, log drums, a bone shaker, a low wooden flute and two friendly rawrs); **robots** a friendly electro tune (soft square-wave arpeggio, gentle beat, beep-boops); **creatures** a magical tune (music-box bells on a dreamy whole-tone scale, a harp sweep, a soft shimmering pad) |
| Wave | a friendly two-note "hel-lo" chime with a tiny sparkle |
| Spin | a soft whoosh that rises and falls, with a small chime at the end |
| Choosing | a very quiet round "pop" when an animal, color or extra is picked |

Sounds only start from a tap (a move, "Again" repeating it, or a choice). They use the
ambient audio mode, so the silent switch mutes them and music keeps playing. The speaker
button next to undo turns them off and the app remembers it. Rebuild: `python3 models/make_sounds.py`;
the dinosaur, robot and creature dance tunes come from `python3 models/make_dance_music.py`.

## How to run it

Needs an iPhone or iPad on iOS 18 or newer (the room camera needs a real device; the
Simulator shows the shelf only).

**Option A: Xcode on the Mac**
1. Open `FigureShelf.swiftpm` in Xcode 16 or newer (double-click it, or File > Open).
2. Click the project, open **Signing & Capabilities**, and choose your Apple ID team.
3. Plug in the iPhone or iPad, pick it at the top, and press Run (▶).

**Option B: Swift Playgrounds on an iPad**
Copy `FigureShelf.swiftpm` to the iPad (AirDrop or iCloud Drive), open it in the
free Swift Playgrounds app and tap Run. The room camera works there too.

## Files

- `Model.swift`: animals, colors, extras, actions, and saved state with undo
- `FigureBuilder.swift`: builds each animal and extra from shapes
- `FigureRig.swift`: the dance, jump, run, spin and wave movements
- `PatternPainter.swift`: paints dots, stripes, checks, stars and hearts onto a color texture using the animal's position map
- `RealFigure.swift`: loads the six animated models, swaps their color textures, plays their clips and keeps extras on the head and neck bones
- `Resources/`: `<animal>.usdz`, `<animal>_clips.json` (clips + where extras sit) `<animal>_skin_<color>.jpg`, and `<animal>_pos.png` (position map for patterns, the 24 animals)
- `StageView.swift`: the 3D shelf view and the AR room view
- `ContentView.swift`: the screens and buttons

## App Store

- Bundle ID `app.figureshelf.FigureShelf`, version 1.1 (4), team B6LBNVRNQ4, iPhone and iPad.
- `Resources/PrivacyInfo.xcprivacy`: no tracking, no collected data, UserDefaults (CA92.1).
- `InfoExtra.plist` adds `ITSAppUsesNonExemptEncryption = NO` (`additionalInfoPlistContentFilePath` in Package.swift;
  Swift Playgrounds may drop it if it rewrites Package.swift, so check after editing there).
- Parents' sheet: hold the small "i" for 3 s. Links: `PRIVACY_URL` / `SUPPORT_URL` in `ParentsInfo.swift`
  (GitHub Pages, repo fplotnikov/figureshelf-web; page sources in `appstore/web/`).
- Screenshot launch options: `-figureShelf.menuLevel 0|1|2`, `-figureShelf.autoplay dance|jump|run|spin|wave`.
- Store screenshots: `appstore/screenshots/`. Archive + local App Store export: `appstore/build/`.

### App Store builds come from the Xcode project

`FigureShelf-Xcode/` (generated by XcodeGen from `project.yml`) builds the same Swift files and `Resources/` as a normal
iOS app. Upload from there: App Playground (.swiftpm) builds record the deployment target as the SDK version in the binary
(`vtool -show-build` shows "sdk 18.0"), and App Store Connect rejects them. After adding Swift files in the .swiftpm,
add them to `project.yml` (sources list) and run `xcodegen` in `FigureShelf-Xcode/`.
