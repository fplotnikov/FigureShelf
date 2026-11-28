#!/bin/zsh
# Simulator screenshot of one figure: shot.sh <animal> <out.png> [skin] [worn-json-list] [autoplay] [wait-seconds] [menuLevel]
# The look goes in as a launch argument (an old-style plist <hex> data value).
# e.g. shot.sh megalodon out.png natural '["partyHat","sunglasses","bowTie"]' run 2.2 1
set -e
A=$1; OUT=$2; SKIN=${3:-natural}; WORN=${4:-[]}; PLAY=${5:-}; WAIT=${6:-6}; LEVEL=${7:-2}
BID=app.figureshelf.FigureShelf
J="{\"animal\":\"$A\",\"skin\":\"$SKIN\",\"pattern\":\"plain\",\"worn\":$WORN}"
xcrun simctl terminate booted $BID 2>/dev/null || true
HEX=$(printf '%s' "$J" | xxd -p | tr -d '\n')
ARGS=(-figureShelf.menuLevel $LEVEL -figureShelf.look "<$HEX>" -figureShelf.sound NO -figureShelf.tab animals)
[ -n "$PLAY" ] && ARGS+=(-figureShelf.autoplay $PLAY)
xcrun simctl launch booted $BID $ARGS >/dev/null
sleep $WAIT
xcrun simctl io booted screenshot "$OUT" >/dev/null 2>&1
echo "$OUT"
