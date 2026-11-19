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
| Animals | Bunny, Kitty, Bear, Penguin, Frog, Fox |
| Animatronics | Raccoon, Moth, Crocodile, Ram, Pelican, Armadillo, Lynx, Frog Singer, Vulture, Anteater (Fedir's vintage theme-park performers; they move in stiff servo steps) |
| Robots | Supercar, Jet, Motorcycle, Big Truck, Helicopter, Rally, Seaplane, Snowmobile, Excavator, Speedboat (Fedir's robot designs; each turns into its vehicle to run) |
| Creatures | Mosskip, Glassfin, Cindermole, Cloudlope, Thimblebat, Pebblenewt, Bloomusk, Velvetide, Lanternquill, Dunewisp (Fedir's own imaginary creatures) |
| Colors | Normal, Sunny, Ocean, Mint, Berry, Night, Snow |
| Accessories (one per group, all at once) | Hats: party hat, crown, top hat, cowboy, beanie, cap, wizard, pirate, chef, flower crown, viking, propeller, flower clip. Glasses: sunglasses, round, hearts, stars, goggles, 3D, monocle. Masks: hero, butterfly, red nose, moustache, ninja, snorkel. Neck: bow tie, scarf, cape, lei, medal |
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

## Things to wear

The **Accessories** tab has four groups: Hats, Glasses, Masks and Neck. One item from each group
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

The icon is the app's own Kitty, rendered in Blender close up on a sky-blue background
(`models/make_icon.py -- c`). Options A (shelf with three figures) and B (Kitty on the turntable)
and a size test sheet are in `icon/`. It lives in `FigureShelf.swiftpm/Assets.xcassets/AppIcon.appiconset`.

## Sounds

All sounds are original: `models/make_sounds.py` synthesises them (sine tones, soft mallet
notes, filtered noise; no samples) into `FigureShelf.swiftpm/Resources/Sounds/`, quiet
(peaks at -12 dBFS) with soft starts and ends. Each one is as long as its move.

| Sound | What it is like |
|---|---|
| Jump | a soft rising "boing" at each of the 3 hops, then a soft landing thump |
| Run | light pitter-patter of little paws that fades in and out |
| Dance | a short cheerful marimba tune with a gentle bass |
| Wave | a friendly two-note "hel-lo" chime with a tiny sparkle |
| Spin | a soft whoosh that rises and falls, with a small chime at the end |
| Choosing | a very quiet round "pop" when an animal, color or extra is picked |

Sounds only start from a tap (a move, "Again" repeating it, or a choice). They use the
ambient audio mode, so the silent switch mutes them and music keeps playing. The speaker
button next to undo turns them off and the app remembers it. Rebuild: `python3 models/make_sounds.py`.

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
- `RealFigure.swift`: loads the six animated models, swaps their color textures, plays their clips and keeps extras on the head and neck bones
- `Resources/`: `<animal>.usdz`, `<animal>_clips.json` (clips + where extras sit) and `<animal>_skin_<color>.jpg` for all six animals
- `StageView.swift`: the 3D shelf view and the AR room view
- `ContentView.swift`: the screens and buttons

## App Store

- Bundle ID `app.figureshelf.FigureShelf`, version 1.0 (1), team B6LBNVRNQ4, iPhone and iPad.
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
