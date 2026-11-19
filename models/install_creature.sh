#!/bin/zsh
# Copy built creatures into the app: install_creature.sh mosskip glassfin ...
# (USDZ, clips JSON, the 7 JPEG skins and the chooser thumbnail), then check the USDZ.
set -e
HERE=${0:A:h}; RES=$HERE/../FigureShelf.swiftpm/Resources
for n in "$@"; do
  cp $HERE/$n.usdz $HERE/${n}_clips.json $RES/
  for f in $HERE/${n}_skins/*.jpg; do sips -Z 768 -s formatOptions 74 "$f" --out $RES/${f:t} >/dev/null; done
  [ -f $HERE/${n}_vehicle.usdz ] && cp $HERE/${n}_vehicle.usdz $RES/
  sips -Z 192 $HERE/${n}_thumb.png --out $RES/${n}_thumb.png >/dev/null
  usdchecker --arkit $RES/$n.usdz | tail -1
done
