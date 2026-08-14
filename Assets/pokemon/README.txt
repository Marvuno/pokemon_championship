Sprites are keyed by GUI/bridge.py's sprite_key(), as <key>-left.gif (your
side) and <key>-right.gif (the opponent's). left/ is the mirror of right/, so
the two sides face each other across the arena.

Two sources:

1. The real Pokemon -- downloaded from projectpokemon.org by
   Test/image_builder.py, then flipped into left/.

2. The custom Pokemon (plus Flygon and Spectrier) -- hand-drawn artwork in
   custom/, one 1024x1024 JPEG per Pokemon named as in Data/pokemon.csv, and
   installed by Test/build_custom_sprites.py. It keys out the white ground,
   crops to the artwork, fits 256x256, and writes the GIF to right/ with its
   mirror in left/.

     python Test/build_custom_sprites.py            # convert everything
     python Test/build_custom_sprites.py --sheet    # preview only
     python Test/build_custom_sprites.py --flip     # art faces left instead

Both sources are then pre-scaled by Test/sharpen_sprites.py so the game never
has to enlarge one at runtime -- smooth enlargement is what makes pixel art
look blurry. It is safe to re-run; sprites already big enough are skipped.

     python Test/sharpen_sprites.py --dry-run       # report only
     python Test/sharpen_sprites.py

Currently: all 239 Pokemon have both sides.
