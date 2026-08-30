"""
Build battle sprites for the Pokemon that don't have one.

The downloaded set came off projectpokemon.org as animations,
which by definition has nothing for this project's own creations -- hence the
old "Missing: Spectrier, All Custom Mons" note and the name-in-place-of-a-
sprite fallback in GUI_qt/sprites.py.

These are drawn rather than downloaded, and composed from what the game
already knows about each Pokemon so no two come out the same:

  body plan   one of a dozen genuinely different builds -- serpent, swarm,
              crustacean, plant, titan, wisp, avian, ... -- weighted by type
              and then picked by the species' own seed, so two Ice Pokemon
              can be built nothing like each other
  face        eyes are only one option: visors, hollow voids, compound
              clusters, mandibles, beaks, maws, eye stalks, sigils, or no
              face at all
  colour      the interface's own type palette, so a sprite always reads as
              its typing
  size/bulk   stat total and the Atk/Def/HP-vs-Speed balance
  aura        tier (Boss, Ultra High and Secret glow)
  seed        the name -- proportions, counts, horns, tails, patterns and
              markings are stable forever and identical on any machine

Output matches the downloaded set: small palette GIFs, transparent, gently
animated, `<key>-left.gif` / `<key>-right.gif` under Assets/pokemon/, keyed by
the same sprite_key() the interface looks them up with.

    python Test/sprite_forge.py            # only the missing ones
    python Test/sprite_forge.py --force    # redraw everything
    python Test/sprite_forge.py Douma Akaza
    python Test/sprite_forge.py --sheet    # contact sheet, no files written
"""

import csv
import hashlib
import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from GUI import theme as T                      # noqa: E402
from GUI.bridge import sprite_key               # noqa: E402

#: Working canvas. Bigger than the sprites end up being: everything is drawn
#: here with room to spare and then cropped to what was actually painted, so
#: the finished file is tight to the creature the way the downloaded sprites
#: are. Without that crop these shipped with wide transparent margins, which
#: made them render visibly smaller than the real Pokemon standing next to
#: them and sit too high off the arena floor.
CANVAS = (200, 180)
SS = 3                  # drawn large, then resolved down: smooth curves
#: The downloaded sprites share a look: a near-black outline (one of the most
#: common colours in every one of them) over three or four banded tones per
#: material. Drawing at 1:1 got the outline and the banding right but left
#: every curve stepped and every limb faceted, so the shapes are drawn big
#: and resolved down -- and the outline is inked *after* that, so it stays a
#: clean single pixel instead of being blurred away.
OUTLINE = (26, 24, 32)
CROP_PAD = 1            # px of breathing room kept around the artwork
#: After cropping, nothing ships larger than this. Draw freely on a roomy
#: canvas, crop to the art, then fit -- that way antlers, wings and orbiting
#: shards are never clipped, and every sprite still lands in the same size
#: band as the downloaded ones instead of towering over them.
MAX_SIZE = (132, 126)
FRAMES = 20
DURATION = 45
#: sprites are flattened onto the interface's own background colour and that
#: colour is then made transparent
CHROMA = (11, 18, 32)
#: GIF transparency is all-or-nothing: anything fainter than this becomes
#: fully see-through, otherwise a soft glow's wide tail ships as opaque navy
#: and shows up in game as a rectangle around the sprite
ALPHA_CUTOFF = 40
TYPELESS_COLOUR = "#C9CFDA"
STAT_KEYS = ("HP", "Atk", "Def", "SpA", "SpDef", "Spd")

# --------------------------------------------------------------------- choices
#: build -> whether it stands on the ground, and how much it bobs
BUILDS = ("biped", "quadruped", "serpent", "floater", "swarm", "avian",
          "armored", "wisp", "crustacean", "plant", "aquatic", "titan")
GROUNDED = {"biped", "quadruped", "armored", "crustacean", "plant", "titan"}
HOVERS = {"floater", "swarm", "wisp", "aquatic", "serpent"}

FACES = ("eyes2", "eyes1", "eyes3", "eyes4", "visor", "hollow", "mask",
         "mandibles", "beak", "maw", "compound", "sigil", "blank", "stalks")

#: Per type: which builds and faces suit it, as weights. Merged across a
#: Pokemon's types (primary counting most) and then rolled with the name
#: seed -- that combination is what stops same-type species converging.
TYPE_BUILD = {
    "Normal":   {"biped": 3, "quadruped": 3, "swarm": 1, "titan": 1},
    "Fire":     {"quadruped": 3, "biped": 2, "avian": 2, "titan": 2},
    "Water":    {"aquatic": 4, "crustacean": 2, "serpent": 2, "floater": 1},
    "Grass":    {"plant": 4, "quadruped": 2, "biped": 1, "swarm": 1},
    "Electric": {"floater": 2, "biped": 2, "quadruped": 2, "avian": 1},
    "Ice":      {"floater": 2, "armored": 2, "biped": 2, "crustacean": 1},
    "Fighting": {"biped": 3, "titan": 3, "quadruped": 1},
    "Poison":   {"floater": 2, "serpent": 2, "swarm": 2, "wisp": 1},
    "Ground":   {"quadruped": 3, "armored": 3, "titan": 2, "crustacean": 1},
    "Flying":   {"avian": 5, "serpent": 1, "floater": 1},
    "Psychic":  {"floater": 4, "wisp": 2, "swarm": 1, "biped": 1},
    "Bug":      {"crustacean": 3, "swarm": 3, "armored": 2, "avian": 1},
    "Rock":     {"armored": 4, "titan": 2, "quadruped": 2},
    "Ghost":    {"wisp": 5, "floater": 2, "swarm": 1},
    "Dragon":   {"serpent": 4, "titan": 2, "avian": 2, "quadruped": 1},
    "Dark":     {"wisp": 3, "biped": 2, "quadruped": 2, "titan": 1},
    "Steel":    {"armored": 4, "titan": 2, "biped": 2},
    "Fairy":    {"floater": 3, "swarm": 2, "plant": 1, "biped": 1},
    "Typeless": {"floater": 3, "wisp": 2, "swarm": 2},
}

TYPE_FACE = {
    "Normal":   {"eyes2": 4, "maw": 1, "beak": 1},
    "Fire":     {"eyes2": 2, "maw": 3, "visor": 1},
    "Water":    {"eyes2": 3, "eyes1": 1, "mandibles": 1, "stalks": 1},
    "Grass":    {"blank": 3, "eyes2": 2, "sigil": 1},
    "Electric": {"visor": 3, "eyes2": 2, "eyes1": 1},
    "Ice":      {"eyes1": 2, "visor": 2, "eyes2": 2, "blank": 1},
    "Fighting": {"mask": 3, "eyes2": 2, "maw": 1},
    "Poison":   {"eyes3": 2, "eyes4": 2, "maw": 2, "hollow": 1},
    "Ground":   {"eyes2": 2, "maw": 2, "blank": 2, "mask": 1},
    "Flying":   {"beak": 4, "eyes2": 2},
    "Psychic":  {"sigil": 3, "eyes1": 2, "eyes3": 1, "hollow": 1},
    "Bug":      {"compound": 4, "mandibles": 3, "eyes4": 1, "stalks": 1},
    "Rock":     {"blank": 3, "eyes2": 2, "mask": 1},
    "Ghost":    {"hollow": 5, "eyes1": 1, "maw": 1},
    "Dragon":   {"maw": 3, "eyes2": 2, "mask": 1},
    "Dark":     {"hollow": 3, "eyes3": 2, "maw": 2, "mask": 1},
    "Steel":    {"visor": 4, "mask": 2, "eyes2": 1},
    "Fairy":    {"eyes2": 3, "sigil": 2, "eyes1": 1},
    "Typeless": {"sigil": 3, "eyes3": 1, "blank": 1, "visor": 1},
}

#: expression parts -- combined with the eye scheme, these are what stop
#: two species with the same layout reading as the same creature
BROWS = ("none", "none", "angry", "raised", "heavy", "worried")
MOUTHS = ("none", "fangs", "grin", "frown", "line", "open")
PUPILS = ("round", "round", "slit", "square", "pinpoint")
CHEEKS = ("none", "none", "none", "blush", "scar", "whisker")

HORNS = ("none", "pair", "curved", "antlers", "crown", "single")
TAILS = ("none", "whip", "club", "fan", "forked", "flame")
WINGS = ("none", "bat", "feather", "insect", "energy")
PATTERNS = ("none", "stripes", "spots", "plates", "scales", "veins", "cracks")

TYPE_FEATURE = {
    "Fire": dict(flame=1.0, particles="ember"),
    "Grass": dict(leaves=1.0, particles="leaf"),
    "Ice": dict(crystal=1.0, particles="snow"),
    "Electric": dict(bolts=1.0, particles="spark"),
    "Water": dict(fins=1.0, particles="bubble"),
    "Rock": dict(rocks=1.0),
    "Ground": dict(rocks=0.7),
    "Steel": dict(plating=1.0),
    "Ghost": dict(glow=1.3, particles="shadow"),
    "Dark": dict(glow=0.8, particles="shadow"),
    "Psychic": dict(glow=1.2, particles="spark"),
    "Fairy": dict(glow=1.0, particles="spark"),
    "Poison": dict(drip=1.0, particles="bubble"),
    "Bug": dict(antennae=1.0),
    "Flying": dict(feathers=1.0),
    "Dragon": dict(spines=1.0),
    "Fighting": dict(bands=1.0),
    "Typeless": dict(glow=1.0, particles="spark"),
}

AURA_TIERS = {"Boss": 1.0, "Ultra High": 0.7, "Secret": 1.0}


# ---------------------------------------------------------------- colour utils
def _rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, amount):
    return tuple(int(round(a[i] + (b[i] - a[i]) * amount)) for i in range(3))


def _shade(colour, amount):
    target = (255, 255, 255) if amount > 0 else (10, 12, 18)
    return _mix(colour, target, abs(amount))


def type_colour(name):
    if name == "Typeless":
        return _rgb(TYPELESS_COLOUR)
    return _rgb(T.TYPE_COLORS.get(name, T.TEXT_DIM))


def _pick(rng, weights):
    total = sum(weights.values())
    if total <= 0:
        return None
    roll = rng.uniform(0, total)
    for key, weight in sorted(weights.items()):
        roll -= weight
        if roll <= 0:
            return key
    return sorted(weights)[-1]


# -------------------------------------------------------------------- species
class Species:
    def __init__(self, row):
        self.name = row["Name"]
        self.key = sprite_key(self.name)
        self.types = [row[k] for k in ("Type1", "Type2", "Type3") if row[k]]
        self.tier = row["Tier"]
        self.custom = row["Custom"].strip().upper() == "Y"
        self.stats = {k: int(row[k] or 0) for k in STAT_KEYS}
        self.total = int(row["Total"] or sum(self.stats.values()))

        digest = hashlib.sha256(self.name.encode("utf-8")).digest()
        # A stable seed, not hash(): Python randomises string hashing per
        # process, so anything seeded from hash(key) laid itself out
        # differently on every run -- which broke the promise that a species
        # always draws the same.
        self.seed = int.from_bytes(digest[:8], "big")
        self.rng = random.Random(self.seed)
        rng = self.rng

        build_weights, face_weights = {}, {}
        self.features = {}
        for index, type_name in enumerate(self.types):
            weight = (1.0, 0.6, 0.4)[min(index, 2)]
            for key, value in TYPE_BUILD.get(type_name, {}).items():
                build_weights[key] = build_weights.get(key, 0) + value * weight
            for key, value in TYPE_FACE.get(type_name, {}).items():
                face_weights[key] = face_weights.get(key, 0) + value * weight
            for key, value in TYPE_FEATURE.get(type_name, {}).items():
                if isinstance(value, str):
                    self.features.setdefault(key, value)
                else:
                    self.features[key] = self.features.get(key, 0.0) + \
                        value * weight

        self.build = _pick(rng, build_weights) or "biped"
        self.face = _pick(rng, face_weights) or "eyes2"
        # a crustacean's eyes are on stalks whatever the type rolled, and a
        # swarm shows one face on its leader
        if self.build == "crustacean" and rng.random() < 0.6:
            self.face = "stalks"
        if self.face == "stalks" and self.build not in ("crustacean",
                                                        "aquatic", "swarm"):
            self.face = "eyes2"

        self.horns = rng.choice(HORNS) if rng.random() < 0.62 else "none"
        self.tail = rng.choice(TAILS) if rng.random() < 0.70 else "none"
        self.pattern = rng.choice(PATTERNS)
        # Expression, rolled independently of the eye scheme. Fourteen eye
        # layouts still left same-scheme species looking like siblings; a
        # brow and a mouth are what actually give a face a character, and
        # these multiply out so no two end up with the same look.
        self.brow = rng.choice(BROWS)
        self.mouth = rng.choice(MOUTHS)
        self.pupil = rng.choice(PUPILS)
        self.cheek = rng.choice(CHEEKS)
        self.iris = rng.choice((None, None, "glow", "accent"))
        wing_bias = self.features.get("feathers", 0) + \
            (0.6 if "Dragon" in self.types else 0) + \
            (0.5 if "Bug" in self.types else 0)
        if self.build == "avian":
            self.wings = "feather" if rng.random() < 0.6 else "energy"
        elif wing_bias > 0.4 or rng.random() < 0.22:
            self.wings = rng.choice([w for w in WINGS if w != "none"])
        else:
            self.wings = "none"

        base = type_colour(self.types[0])
        second = type_colour(self.types[1]) if len(self.types) > 1 else \
            _shade(base, 0.32)
        third = type_colour(self.types[2]) if len(self.types) > 2 else second
        luminance = (base[0] * 0.299 + base[1] * 0.587 + base[2] * 0.114) / 255
        self.body = _shade(base, -0.24) if luminance > 0.62 else base
        self.dark = _shade(self.body, -0.52)
        self.light = _shade(_mix(self.body, second, 0.22), 0.32)
        self.accent = second
        self.glow = third

        span = max(1, 740 - 380)
        # tuned so a cropped sprite lands in the same 70-130px range as the
        # downloaded set, rather than reading as a miniature beside them
        self.scale = 0.96 + 0.28 * min(1.0, max(0.0,
                                               (self.total - 380) / span))
        bulk = (self.stats["HP"] + self.stats["Def"] + self.stats["Atk"]) / 3.0
        self.stocky = max(0.0, min(1.0,
                                   (bulk - self.stats["Spd"] + 40) / 120.0))
        self.aura = AURA_TIERS.get(self.tier, 0.0)
        self.grounded = self.build in GROUNDED

    def summary(self):
        bits = [self.build, self.face]
        for label, value in (("horns", self.horns), ("tail", self.tail),
                             ("wings", self.wings), (None, self.pattern)):
            if value != "none":
                bits.append(value)
        return " ".join(bits)


# --------------------------------------------------------------------- painter
class Anatomy:
    """Where the head goes and what the features can hang off."""

    def __init__(self, head, head_r, shoulders=(), back=(), hips=None):
        self.head = head
        self.head_r = head_r
        self.shoulders = shoulders
        self.back = back
        self.hips = hips


class Painter:
    def __init__(self, species):
        self.s = species
        self.w, self.h = CANVAS[0] * SS, CANVAS[1] * SS
        self.gy = self.h * 0.90
        self.cx = self.w * 0.50
        self.outline = species.dark + (255,)
        rng = species.rng
        self.eye_wobble = rng.uniform(-0.05, 0.05)
        # Every random choice is made here, once. Rolling dice inside a
        # frame-drawing routine meant the pattern's spots landed somewhere
        # new on each of the 20 frames, so in game they crawled around the
        # body instead of staying put.
        self.spots = [(rng.uniform(-0.9, 0.9), rng.uniform(0.0, 1.6))
                      for _ in range(5)]
        self.limb_count = rng.choice((4, 6))
        self.swarm_n = rng.choice((3, 4, 5))
        self.sat_n = rng.choice((3, 4, 5))
        self.petals = rng.choice((5, 6, 7))
        # spines are an accent, not a default -- every creature wearing a
        # row of them was a big part of why the silhouettes read as spiky
        self.spike_n = rng.choice((0, 0, 0, 2, 3))

    # -- primitives ------------------------------------------------------
    def layer(self):
        return Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))

    def ell(self, d, cx, cy, rx, ry, fill, outline=None, width=SS):
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill,
                  outline=outline, width=width)

    def poly(self, d, points, fill, outline=None):
        d.polygon(points, fill=fill, outline=outline)

    def limb(self, d, x0, y0, x1, y1, thickness, fill):
        d.line([(x0, y0), (x1, y1)], fill=fill, width=int(thickness))
        self.ell(d, x1, y1, thickness * 0.5, thickness * 0.5, fill)

    # -- builds ----------------------------------------------------------
    # each returns an Anatomy; all draw facing right (mirrored for the
    # opponent's side, exactly as the downloaded set was built)
    def build_biped(self, d, bob):
        s, W, H = self.s, self.w, self.h
        tw = W * 0.30 * s.scale * (0.85 + 0.35 * s.stocky)
        th = H * 0.28 * s.scale
        cy = H * 0.58 + bob
        body = s.body + (255,)
        for sign in (-1, 1):                       # legs
            x = self.cx + sign * tw * 0.34
            self.limb(d, x, cy + th * 0.38, x + sign * tw * 0.10, self.gy,
                      tw * 0.26, _shade(s.body, -0.18) + (255,))
        d.rounded_rectangle([self.cx - tw * 0.5, cy - th * 0.5,
                             self.cx + tw * 0.5, cy + th * 0.5],
                            radius=tw * 0.42, fill=body, outline=self.outline,
                            width=SS)
        head_r = W * 0.145 * s.scale * (1.12 - 0.24 * s.stocky)
        head = (self.cx, cy - th * 0.5 - head_r * 0.55)
        d.rounded_rectangle([self.cx - head_r * 0.34, head[1],
                             self.cx + head_r * 0.34, cy - th * 0.2],
                            radius=head_r * 0.3,
                            fill=_shade(s.body, -0.12) + (255,))
        for sign in (-1, 1):                       # arms
            x = self.cx + sign * tw * 0.5
            self.limb(d, x, cy - th * 0.22, x + sign * tw * 0.22,
                      cy + th * 0.34, tw * 0.20,
                      _shade(s.body, -0.10) + (255,))
        return Anatomy(head, head_r,
                       shoulders=((self.cx - tw * 0.5, cy - th * 0.3),
                                  (self.cx + tw * 0.5, cy - th * 0.3)),
                       back=[(self.cx + i * tw * 0.3, cy - th * 0.5)
                             for i in (-1, 0, 1)],
                       hips=(self.cx - tw * 0.5, cy + th * 0.3))

    def build_quadruped(self, d, bob):
        s, W, H = self.s, self.w, self.h
        tw = W * 0.40 * s.scale
        # deep barrel chest and short thick legs in two clearly separated
        # pairs -- four thin evenly-spaced struts read as furniture, not
        # as a four-legged animal
        th = H * 0.24 * s.scale * (0.9 + 0.3 * s.stocky)
        cy = H * 0.58 + bob
        leg_colour = _shade(s.body, -0.26) + (255,)
        for base, splay in ((0.32, 0.05), (-0.30, -0.06)):   # fore and hind
            for near in (0.0, 0.11):
                x = self.cx + (base + near) * tw
                self.limb(d, x, cy + th * 0.24, x + splay * tw, self.gy,
                          tw * 0.17, leg_colour)
        haunch = _shade(s.body, -0.10) + (255,)
        self.ell(d, self.cx - tw * 0.30, cy + th * 0.06, tw * 0.20,
                 th * 0.40, haunch)                # rump
        self.ell(d, self.cx, cy, tw * 0.5, th * 0.5, s.body + (255,),
                 self.outline, SS)
        self.ell(d, self.cx + tw * 0.28, cy - th * 0.04, tw * 0.20,
                 th * 0.42, haunch)                # shoulder
        head_r = W * 0.135 * s.scale
        head = (self.cx + tw * 0.52, cy - th * 0.52 - head_r * 0.18)
        self.limb(d, self.cx + tw * 0.30, cy - th * 0.22, head[0],
                  head[1] + head_r * 0.3, th * 0.46,
                  _shade(s.body, -0.06) + (255,))
        self.ell(d, head[0], head[1], head_r * 1.02, head_r * 0.92,
                 s.body + (255,), self.outline, SS)
        return Anatomy(head, head_r,
                       shoulders=((self.cx + tw * 0.24, cy - th * 0.42),
                                  (self.cx - tw * 0.10, cy - th * 0.44)),
                       back=[(self.cx + (-0.26 + 0.18 * i) * tw,
                              cy - th * 0.48) for i in range(4)],
                       hips=(self.cx - tw * 0.48, cy))

    def build_serpent(self, d, bob):
        s, W, H = self.s, self.w, self.h
        pts, radii = [], []
        for i in range(7):
            t = i / 6.0
            x = self.cx + W * s.scale * (-0.26 + 0.50 * t)
            y = self.gy - H * 0.10 - H * 0.44 * t + \
                math.sin(t * math.pi * 1.8 + bob * 0.02) * H * 0.05
            pts.append((x, y))
            radii.append(W * (0.125 - 0.055 * t) * s.scale)
        upper = [(x, y - r) for (x, y), r in zip(pts, radii)]
        lower = [(x, y + r) for (x, y), r in zip(pts, radii)]
        self.poly(d, upper + list(reversed(lower)), s.body + (255,))
        for (x, y), r in zip(pts, radii):
            self.ell(d, x, y, r, r, s.body + (255,))
        head_r = W * 0.115 * s.scale
        head = (pts[-1][0] + head_r * 0.35, pts[-1][1] - head_r * 0.25)
        self.ell(d, head[0], head[1], head_r * 1.05, head_r * 0.9,
                 s.body + (255,), self.outline, SS)
        return Anatomy(head, head_r,
                       shoulders=(pts[3], pts[4]),
                       back=[p for p in pts[1:5]],
                       hips=pts[0])

    def build_floater(self, d, bob, spin=0.0):
        s, W, H = self.s, self.w, self.h
        core_r = W * 0.185 * s.scale * (1.0 + 0.2 * s.stocky)
        cy = H * 0.50 + bob
        for i in range(self.sat_n):                 # orbiting shards
            angle = math.tau * (i / self.sat_n) + spin
            ox = self.cx + math.cos(angle) * core_r * 1.70
            oy = cy + math.sin(angle) * core_r * 1.35
            r = core_r * (0.30 - 0.05 * (i % 2))
            self.poly(d, [(ox - r, oy), (ox, oy - r * 1.5), (ox + r, oy),
                          (ox, oy + r * 1.5)],
                      _shade(s.accent, 0.1) + (240,), self.outline)
        self.ell(d, self.cx, cy, core_r, core_r * 0.96, s.body + (255,),
                 self.outline, SS)
        return Anatomy((self.cx, cy), core_r * 0.92,
                       shoulders=((self.cx - core_r, cy),
                                  (self.cx + core_r, cy)),
                       back=[(self.cx, cy - core_r)], hips=(self.cx, cy))

    def build_swarm(self, d, bob, phase=0.0):
        s, W, H = self.s, self.w, self.h
        rng = random.Random(s.seed ^ 0x5157A8)
        unit_r = W * 0.105 * s.scale
        spots = []
        for i in range(self.swarm_n):
            ax = self.cx + rng.uniform(-0.26, 0.26) * W
            ay = H * rng.uniform(0.40, 0.72)
            wobble = math.sin(phase * math.tau + i * 1.7) * H * 0.02
            spots.append((ax, ay + wobble, unit_r * rng.uniform(0.7, 1.15)))
        spots.sort(key=lambda p: p[2])
        for ax, ay, r in spots[:-1]:
            self.ell(d, ax, ay, r, r, s.body + (250,), self.outline, SS)
            self.ell(d, ax - r * 0.25, ay - r * 0.1, r * 0.16, r * 0.16,
                     (245, 246, 250, 245))
        lead_x, lead_y, lead_r = spots[-1]
        self.ell(d, lead_x, lead_y, lead_r * 1.15, lead_r * 1.1,
                 _shade(s.body, 0.06) + (255,), self.outline, SS)
        return Anatomy((lead_x, lead_y), lead_r,
                       shoulders=((lead_x - lead_r, lead_y),
                                  (lead_x + lead_r, lead_y)),
                       back=[(lead_x, lead_y - lead_r)],
                       hips=(lead_x, lead_y + lead_r))

    def build_avian(self, d, bob):
        s, W, H = self.s, self.w, self.h
        bw = W * 0.22 * s.scale
        bh = H * 0.21 * s.scale
        cy = H * 0.56 + bob
        for sign in (-1, 1):                        # talons
            x = self.cx + sign * bw * 0.34
            self.limb(d, x, cy + bh * 0.42, x, self.gy - H * 0.01, bw * 0.16,
                      _shade(s.accent, -0.25) + (255,))
        fan = _mix(s.accent, s.light, 0.25) + (240,)
        self.poly(d, [(self.cx - bw * 0.4, cy),
                      (self.cx - bw * 1.55, cy + bh * 0.5),
                      (self.cx - bw * 1.48, cy - bh * 0.5)], fan, self.outline)
        self.ell(d, self.cx, cy, bw * 0.5, bh * 0.5, s.body + (255,),
                 self.outline, SS)
        head_r = W * 0.105 * s.scale
        head = (self.cx + bw * 0.42, cy - bh * 0.52)
        self.ell(d, head[0], head[1], head_r, head_r, s.body + (255,),
                 self.outline, SS)
        return Anatomy(head, head_r,
                       shoulders=((self.cx - bw * 0.2, cy - bh * 0.3),
                                  (self.cx + bw * 0.2, cy - bh * 0.3)),
                       back=[(self.cx, cy - bh * 0.5)],
                       hips=(self.cx - bw * 0.5, cy))

    def build_armored(self, d, bob):
        s, W, H = self.s, self.w, self.h
        sw = W * 0.46 * s.scale
        sh = H * 0.27 * s.scale
        cy = H * 0.60 + bob
        for i in range(4):                          # stubby legs
            x = self.cx + (-0.3 + 0.2 * i) * sw
            self.limb(d, x, cy + sh * 0.34, x, self.gy - H * 0.01, sw * 0.11,
                      _shade(s.body, -0.3) + (255,))
        head_r = W * 0.095 * s.scale
        head = (self.cx + sw * 0.40, cy + sh * 0.10)
        self.ell(d, head[0], head[1], head_r, head_r * 0.9,
                 _shade(s.body, -0.14) + (255,), self.outline, SS)
        shell = [(self.cx - sw * 0.5, cy + sh * 0.18),
                 (self.cx - sw * 0.36, cy - sh * 0.42),
                 (self.cx + sw * 0.30, cy - sh * 0.5),
                 (self.cx + sw * 0.48, cy - sh * 0.02),
                 (self.cx + sw * 0.34, cy + sh * 0.36),
                 (self.cx - sw * 0.30, cy + sh * 0.42)]
        self.poly(d, shell, s.body + (255,), self.outline)
        band = _shade(s.accent, -0.18) + (170,)
        for i in range(3):
            y = cy - sh * 0.26 + i * sh * 0.26
            d.line([(self.cx - sw * (0.34 - i * 0.03), y),
                    (self.cx + sw * (0.34 - i * 0.05), y)],
                   fill=band, width=int(SS * 1.5))
        return Anatomy(head, head_r,
                       shoulders=((self.cx - sw * 0.34, cy - sh * 0.36),
                                  (self.cx + sw * 0.26, cy - sh * 0.44)),
                       back=[(self.cx + (-0.3 + 0.22 * i) * sw, cy - sh * 0.46)
                             for i in range(4)],
                       hips=(self.cx - sw * 0.5, cy))

    def build_wisp(self, d, bob):
        s, W, H = self.s, self.w, self.h
        core_r = W * 0.165 * s.scale
        cy = H * 0.42 + bob
        tail = []
        for i in range(8):
            t = i / 7.0
            width = core_r * (1.0 - 0.85 * t)
            x = self.cx + math.sin(t * math.pi * 1.6 + bob * 0.03) * W * 0.06
            y = cy + core_r * 0.7 + (self.gy - cy - core_r * 0.7) * t
            tail.append((x - width, y, x + width, y))
        left = [(p[0], p[1]) for p in tail]
        right = [(p[2], p[3]) for p in tail]
        self.poly(d, left + list(reversed(right)),
                  _mix(s.body, CHROMA, 0.15) + (238,))
        for sign in (-1, 1):                        # smoke tendrils
            self.limb(d, self.cx + sign * core_r * 0.7, cy + core_r * 0.3,
                      self.cx + sign * core_r * 1.9,
                      cy + core_r * (1.5 + 0.4 * sign), core_r * 0.28,
                      _mix(s.body, CHROMA, 0.25) + (210,))
        self.ell(d, self.cx, cy, core_r, core_r, s.body + (255,),
                 self.outline, SS)
        return Anatomy((self.cx, cy), core_r * 0.94,
                       shoulders=((self.cx - core_r, cy),
                                  (self.cx + core_r, cy)),
                       back=[(self.cx, cy - core_r)], hips=(self.cx, cy))

    def build_crustacean(self, d, bob):
        s, W, H = self.s, self.w, self.h
        bw = W * 0.36 * s.scale
        bh = H * 0.16 * s.scale
        cy = H * 0.68 + bob
        for i in range(self.limb_count):            # many small legs
            t = i / (self.limb_count - 1.0)
            x = self.cx + (-0.34 + 0.68 * t) * bw
            self.limb(d, x, cy + bh * 0.2, x + bw * 0.06, self.gy - H * 0.01,
                      bw * 0.07, _shade(s.body, -0.3) + (255,))
        claw = _shade(s.accent, -0.05) + (250,)
        for sign in (-1, 1):                        # pincers
            x = self.cx + sign * bw * 0.66
            y = cy - bh * 0.55
            self.limb(d, self.cx + sign * bw * 0.32, cy - bh * 0.2, x, y,
                      bw * 0.13, _shade(s.body, -0.2) + (255,))
            # two opposed halves with a gap between: a single triangle just
            # read as a lump on a stick
            self.poly(d, [(x - sign * bw * 0.06, y + bh * 0.10),
                          (x + sign * bw * 0.34, y - bh * 0.30),
                          (x + sign * bw * 0.36, y + bh * 0.06),
                          (x + sign * bw * 0.04, y + bh * 0.22)], claw,
                      self.outline)
            self.poly(d, [(x - sign * bw * 0.04, y + bh * 0.22),
                          (x + sign * bw * 0.34, y + bh * 0.52),
                          (x + sign * bw * 0.36, y + bh * 0.22),
                          (x + sign * bw * 0.06, y + bh * 0.30)],
                      _shade(s.accent, -0.22) + (250,), self.outline)
        self.ell(d, self.cx, cy, bw * 0.5, bh * 0.55, s.body + (255,),
                 self.outline, SS)
        head_r = W * 0.085 * s.scale
        head = (self.cx, cy - bh * 0.5 - head_r * 0.2)
        return Anatomy(head, head_r,
                       shoulders=((self.cx - bw * 0.4, cy - bh * 0.3),
                                  (self.cx + bw * 0.4, cy - bh * 0.3)),
                       back=[(self.cx + (-0.2 + 0.2 * i) * bw, cy - bh * 0.5)
                             for i in range(3)],
                       hips=(self.cx - bw * 0.5, cy))

    def build_plant(self, d, bob):
        s, W, H = self.s, self.w, self.h
        base_w = W * 0.24 * s.scale
        stalk_top = H * 0.42 + bob * 0.6
        leaf = _mix(type_colour("Grass"), s.light, 0.18)
        self.ell(d, self.cx, self.gy - H * 0.03, base_w * 0.62, H * 0.05,
                 _shade(s.body, -0.32) + (255,), self.outline, SS)
        d.line([(self.cx, self.gy - H * 0.04), (self.cx, stalk_top)],
               fill=_shade(leaf, -0.3) + (255,), width=int(base_w * 0.26))
        for i, side in enumerate((-1, 1, -1)):      # leaves up the stalk
            ly = self.gy - H * (0.10 + 0.09 * i)
            self.ell(d, self.cx + side * base_w * 0.62, ly, base_w * 0.55,
                     base_w * 0.20, leaf + (245,), self.outline,
                     max(1, SS // 2))
        crown_r = W * 0.17 * s.scale
        petal = _mix(s.body, s.light, 0.25)
        for i in range(self.petals):
            angle = math.tau * i / self.petals - math.pi / 2
            px = self.cx + math.cos(angle) * crown_r * 1.15
            py = stalk_top + math.sin(angle) * crown_r * 1.05
            self.ell(d, px, py, crown_r * 0.52, crown_r * 0.40,
                     petal + (248,), self.outline, max(1, SS // 2))
        self.ell(d, self.cx, stalk_top, crown_r * 0.66, crown_r * 0.62,
                 _shade(s.body, -0.10) + (255,), self.outline, SS)
        return Anatomy((self.cx, stalk_top), crown_r * 0.62,
                       shoulders=((self.cx - crown_r, stalk_top),
                                  (self.cx + crown_r, stalk_top)),
                       back=[(self.cx, stalk_top - crown_r)],
                       hips=(self.cx, self.gy - H * 0.06))

    def build_aquatic(self, d, bob):
        s, W, H = self.s, self.w, self.h
        bw = W * 0.40 * s.scale
        bh = H * 0.20 * s.scale
        cy = H * 0.56 + bob
        fin = _mix(s.accent, s.light, 0.3) + (240,)
        self.poly(d, [(self.cx - bw * 0.42, cy),                # tail fin
                      (self.cx - bw * 0.95, cy - bh * 0.75),
                      (self.cx - bw * 0.80, cy),
                      (self.cx - bw * 0.95, cy + bh * 0.75)], fin,
                  self.outline)
        self.poly(d, [(self.cx - bw * 0.1, cy - bh * 0.42),     # dorsal
                      (self.cx + bw * 0.16, cy - bh * 1.15),
                      (self.cx + bw * 0.26, cy - bh * 0.38)], fin,
                  self.outline)
        self.ell(d, self.cx, cy, bw * 0.5, bh * 0.5, s.body + (255,),
                 self.outline, SS)
        self.poly(d, [(self.cx + bw * 0.05, cy + bh * 0.2),     # pectoral
                      (self.cx - bw * 0.1, cy + bh * 0.85),
                      (self.cx + bw * 0.3, cy + bh * 0.35)], fin)
        head_r = W * 0.115 * s.scale
        head = (self.cx + bw * 0.30, cy - bh * 0.06)
        return Anatomy(head, head_r,
                       shoulders=((self.cx, cy - bh * 0.3),
                                  (self.cx + bw * 0.2, cy - bh * 0.3)),
                       back=[(self.cx + (-0.1 + 0.15 * i) * bw, cy - bh * 0.45)
                             for i in range(3)],
                       hips=(self.cx - bw * 0.4, cy))

    def build_titan(self, d, bob):
        s, W, H = self.s, self.w, self.h
        sw = W * 0.50 * s.scale
        cy_top = H * 0.44 + bob
        cy_bot = H * 0.72 + bob
        for sign in (-1, 1):                        # thick legs
            x = self.cx + sign * sw * 0.20
            self.limb(d, x, cy_bot - H * 0.01, x, self.gy, sw * 0.24,
                      _shade(s.body, -0.26) + (255,))
        torso = [(self.cx - sw * 0.5, cy_top),
                 (self.cx + sw * 0.5, cy_top),
                 (self.cx + sw * 0.30, cy_bot),
                 (self.cx - sw * 0.30, cy_bot)]
        self.poly(d, torso, s.body + (255,), self.outline)
        for sign in (-1, 1):                        # heavy arms
            x = self.cx + sign * sw * 0.52
            self.limb(d, x, cy_top + H * 0.01, x + sign * sw * 0.06,
                      cy_bot + H * 0.04, sw * 0.22,
                      _shade(s.body, -0.12) + (255,))
        head_r = W * 0.095 * s.scale
        head = (self.cx, cy_top - head_r * 0.55)
        self.ell(d, head[0], head[1], head_r, head_r * 0.94,
                 _shade(s.body, -0.06) + (255,), self.outline, SS)
        # pauldrons framing the head -- without them a titan is a slab with a
        # small ball balanced on it rather than something heavy-shouldered
        pauldron = _shade(s.accent, -0.12) + (250,)
        for sign in (-1, 1):
            self.ell(d, self.cx + sign * sw * 0.44, cy_top - head_r * 0.10,
                     sw * 0.20, head_r * 0.78, pauldron, self.outline, SS)
        return Anatomy(head, head_r,
                       shoulders=((self.cx - sw * 0.5, cy_top),
                                  (self.cx + sw * 0.5, cy_top)),
                       back=[(self.cx + i * sw * 0.28, cy_top)
                             for i in (-1, 0, 1)],
                       hips=(self.cx - sw * 0.3, cy_bot))

    # -- faces -----------------------------------------------------------
    def draw_face(self, d, anatomy, blink, pulse):
        s = self.s
        cx, cy = anatomy.head
        r = anatomy.head_r
        scheme = s.face
        glow_colour = _mix(s.glow, (255, 255, 255), 0.35 + 0.25 * pulse)
        white = (246, 248, 252, 255)
        socket = (14, 15, 22, 245)
        open_amount = 0.22 if blink else 1.0

        iris = {"glow": _mix(s.glow, (255, 255, 255), 0.2),
                "accent": _shade(s.accent, 0.25)}.get(s.iris)

        def pupil(ex, ey, radius):
            """The eye's own shape -- round, slit, square or a pinpoint."""
            dark = (20, 22, 30, 255)
            if iris is not None:      # a coloured ring inside the white
                self.ell(d, ex, ey, radius * 0.72, radius * 0.74 * open_amount,
                         iris + (255,))
            if s.pupil == "slit":
                d.rectangle([ex - radius * 0.16, ey - radius * 0.62,
                             ex + radius * 0.16, ey + radius * 0.46],
                            fill=dark)
            elif s.pupil == "square":
                d.rectangle([ex - radius * 0.40, ey - radius * 0.36,
                             ex + radius * 0.40, ey + radius * 0.40],
                            fill=dark)
            elif s.pupil == "pinpoint":
                self.ell(d, ex, ey, radius * 0.22,
                         radius * 0.24 * open_amount, dark)
            else:
                self.ell(d, ex + radius * self.eye_wobble, ey + radius * 0.08,
                         radius * 0.44, radius * 0.5 * open_amount, dark)
            # catchlight, the thing that makes an eye look wet
            if open_amount > 0.5:
                self.ell(d, ex - radius * 0.30, ey - radius * 0.34,
                         max(1.0, radius * 0.16), max(1.0, radius * 0.16),
                         (255, 255, 255, 235))

        def eyes(count, radius, spread, glowing=False):
            for i in range(count):
                offset = (i - (count - 1) / 2.0) * spread
                ex = cx + offset
                ey = cy - r * 0.05 + (r * 0.16 if count == 4 and i % 2 else 0)
                if glowing:
                    self.ell(d, ex, ey, radius * 1.3,
                             radius * 1.3 * open_amount, socket)
                    self.ell(d, ex, ey, radius * 0.85,
                             radius * 0.85 * open_amount, glow_colour + (255,))
                else:
                    self.ell(d, ex, ey, radius, radius * open_amount, white)
                    pupil(ex, ey, radius)

        glowing = s.features.get("glow", 0.0) >= 0.9

        if scheme == "eyes2":
            eyes(2, r * 0.175, r * 0.50, glowing)
        elif scheme == "eyes1":
            self.ell(d, cx, cy - r * 0.02, r * 0.27, r * 0.27 * open_amount,
                     white if not glowing else socket)
            self.ell(d, cx, cy, r * 0.13, r * 0.15 * open_amount,
                     glow_colour + (255,) if glowing else (20, 22, 30, 255))
        elif scheme == "eyes3":
            eyes(3, r * 0.125, r * 0.40, glowing)
        elif scheme == "eyes4":
            eyes(4, r * 0.115, r * 0.33, glowing)
        elif scheme == "visor":
            d.rounded_rectangle([cx - r * 0.62, cy - r * 0.20,
                                 cx + r * 0.62, cy + r * 0.14],
                                radius=r * 0.16, fill=socket)
            inner = int(r * 0.10 + r * 0.04 * pulse)
            d.rounded_rectangle([cx - r * 0.50, cy - r * 0.10,
                                 cx + r * 0.50, cy - r * 0.10 + inner],
                                radius=r * 0.06, fill=glow_colour + (255,))
        elif scheme == "hollow":
            self.ell(d, cx, cy, r * 0.74, r * 0.66, (10, 11, 17, 250))
            for sign in (-1, 1):
                self.ell(d, cx + sign * r * 0.28, cy - r * 0.02,
                         r * 0.13 + r * 0.03 * pulse,
                         (r * 0.13 + r * 0.03 * pulse) * open_amount,
                         glow_colour + (255,))
        elif scheme == "mask":
            self.poly(d, [(cx - r * 0.72, cy - r * 0.42),
                          (cx + r * 0.72, cy - r * 0.42),
                          (cx + r * 0.52, cy + r * 0.56),
                          (cx - r * 0.52, cy + r * 0.56)],
                      _mix(s.accent, s.light, 0.35) + (250,), self.outline)
            for sign in (-1, 1):
                self.poly(d, [(cx + sign * r * 0.14, cy - r * 0.12),
                              (cx + sign * r * 0.50, cy - r * 0.20),
                              (cx + sign * r * 0.46, cy + r * 0.06)], socket)
        elif scheme == "mandibles":
            eyes(2, r * 0.135, r * 0.50, glowing)
            jaw = _shade(s.accent, -0.2) + (255,)
            for sign in (-1, 1):
                self.poly(d, [(cx + sign * r * 0.20, cy + r * 0.34),
                              (cx + sign * r * 0.60, cy + r * 0.60),
                              (cx + sign * r * 0.18, cy + r * 0.76)], jaw)
        elif scheme == "beak":
            self.poly(d, [(cx + r * 0.30, cy - r * 0.06),
                          (cx + r * 1.30, cy + r * 0.16),
                          (cx + r * 0.30, cy + r * 0.34)],
                      _shade(s.accent, 0.05) + (255,), self.outline)
            self.ell(d, cx - r * 0.06, cy - r * 0.14, r * 0.24,
                     r * 0.24 * open_amount, white)
            self.ell(d, cx - r * 0.04, cy - r * 0.12, r * 0.11,
                     r * 0.12 * open_amount, (20, 22, 30, 255))
        elif scheme == "maw":
            eyes(2, r * 0.145, r * 0.50, glowing)
            d.rounded_rectangle([cx - r * 0.56, cy + r * 0.28,
                                 cx + r * 0.56, cy + r * 0.78],
                                radius=r * 0.16, fill=(12, 13, 20, 250))
            for i in range(4):
                tx = cx - r * 0.42 + i * r * 0.28
                self.poly(d, [(tx - r * 0.09, cy + r * 0.30),
                              (tx + r * 0.09, cy + r * 0.30),
                              (tx, cy + r * 0.54)], white)
        elif scheme == "compound":
            for ring, count in ((0.0, 1), (0.34, 6)):
                for i in range(count):
                    angle = math.tau * i / max(1, count)
                    ex = cx + math.cos(angle) * r * ring
                    ey = cy + math.sin(angle) * r * ring * 0.9
                    self.ell(d, ex, ey, r * 0.16, r * 0.16,
                             _mix(s.glow, (255, 255, 255),
                                  0.2 + 0.2 * pulse) + (245,))
        elif scheme == "sigil":
            for i in range(6):
                angle = math.tau * i / 6 + pulse * 0.4
                d.line([(cx, cy),
                        (cx + math.cos(angle) * r * 0.66,
                         cy + math.sin(angle) * r * 0.6)],
                       fill=glow_colour + (235,), width=int(SS * 1.3))
            self.ell(d, cx, cy, r * 0.20 + r * 0.05 * pulse,
                     r * 0.20 + r * 0.05 * pulse, glow_colour + (255,))
        elif scheme == "stalks":
            for sign in (-1, 1):
                tip = (cx + sign * r * 0.66, cy - r * 1.25)
                d.line([(cx + sign * r * 0.24, cy), tip],
                       fill=_shade(s.body, -0.16) + (255,),
                       width=int(r * 0.22))
                self.ell(d, tip[0], tip[1], r * 0.30,
                         r * 0.30 * open_amount, white, self.outline,
                         max(1, SS // 2))
                self.ell(d, tip[0], tip[1], r * 0.13,
                         r * 0.14 * open_amount, (20, 22, 30, 255))
        # 'blank' draws no face at all -- a crest or gem carries it instead

        if scheme == "blank":
            self.ell(d, cx, cy, r * 0.30, r * 0.30,
                     _mix(s.glow, (255, 255, 255), 0.2 + 0.25 * pulse) + (240,),
                     self.outline, max(1, SS // 2))

        # expression, over whichever eye scheme was drawn
        if scheme not in ("blank", "compound", "sigil", "stalks"):
            self._draw_brow(d, cx, cy, r)
        if scheme not in ("maw", "mandibles", "beak", "blank", "sigil"):
            self._draw_mouth(d, cx, cy, r)
        self._draw_cheeks(d, cx, cy, r)

    def _draw_brow(self, d, cx, cy, r):
        style = self.s.brow
        if style == "none":
            return
        ink = _shade(self.s.body, -0.62) + (255,)
        width = max(2, int(r * 0.20))
        for sign in (-1, 1):
            inner = (cx + sign * r * 0.16, cy - r * 0.44)
            outer = (cx + sign * r * 0.62, cy - r * 0.44)
            if style == "angry":       # inner ends dip toward the nose
                d.line([(inner[0], inner[1] + r * 0.16), outer], fill=ink,
                       width=width)
            elif style == "raised":
                d.line([(inner[0], inner[1] - r * 0.06),
                        (outer[0], outer[1] - r * 0.22)], fill=ink,
                       width=width)
            elif style == "worried":   # outer ends drop
                d.line([inner, (outer[0], outer[1] + r * 0.20)], fill=ink,
                       width=width)
            else:                      # heavy: a flat, thick ridge
                d.line([inner, outer], fill=ink, width=int(width * 1.7))

    def _draw_mouth(self, d, cx, cy, r):
        style = self.s.mouth
        if style == "none":
            return
        ink = (18, 16, 24, 245)
        white = (246, 248, 252, 255)
        y = cy + r * 0.50
        if style == "line":
            d.line([(cx - r * 0.24, y), (cx + r * 0.24, y)], fill=ink,
                   width=max(2, int(r * 0.12)))
        elif style == "grin":
            d.arc([cx - r * 0.34, y - r * 0.30, cx + r * 0.34, y + r * 0.26],
                  10, 170, fill=ink, width=max(2, int(r * 0.13)))
        elif style == "frown":
            d.arc([cx - r * 0.32, y - r * 0.10, cx + r * 0.32, y + r * 0.46],
                  190, 350, fill=ink, width=max(2, int(r * 0.13)))
        elif style == "open":
            self.ell(d, cx, y + r * 0.06, r * 0.24, r * 0.20, ink)
        elif style == "fangs":
            d.line([(cx - r * 0.26, y), (cx + r * 0.26, y)], fill=ink,
                   width=max(2, int(r * 0.11)))
            for sign in (-1, 1):
                fx = cx + sign * r * 0.18
                self.poly(d, [(fx - r * 0.07, y), (fx + r * 0.07, y),
                              (fx, y + r * 0.26)], white)

    def _draw_cheeks(self, d, cx, cy, r):
        style = self.s.cheek
        if style == "none":
            return
        if style == "blush":
            for sign in (-1, 1):
                self.ell(d, cx + sign * r * 0.66, cy + r * 0.24,
                         r * 0.20, r * 0.14,
                         _mix(self.s.accent, (255, 120, 140), 0.5) + (190,))
        elif style == "scar":
            ink = _shade(self.s.body, -0.60) + (235,)
            d.line([(cx + r * 0.44, cy - r * 0.46),
                    (cx + r * 0.70, cy + r * 0.16)], fill=ink,
                   width=max(2, int(r * 0.10)))
        elif style == "whisker":
            ink = _shade(self.s.body, -0.50) + (215,)
            for sign in (-1, 1):
                for k in (-0.12, 0.10):
                    d.line([(cx + sign * r * 0.52, cy + r * (0.22 + k)),
                            (cx + sign * r * 0.98, cy + r * (0.16 + k * 1.6))],
                           fill=ink, width=max(1, int(r * 0.07)))

    # -- hangs-off-the-body features -------------------------------------
    def draw_horns(self, d, anatomy):
        style = self.s.horns
        if style == "none":
            return
        cx, cy = anatomy.head
        r = anatomy.head_r
        colour = _shade(self.s.accent, 0.02) + (255,)
        if style == "pair":
            for sign in (-1, 1):
                self.poly(d, [(cx + sign * r * 0.5, cy - r * 0.6),
                              (cx + sign * r * 0.78, cy - r * 0.5),
                              (cx + sign * r * 0.62, cy - r * 1.7)], colour,
                          self.outline)
        elif style == "curved":
            for sign in (-1, 1):
                pts = [(cx + sign * r * (0.5 + 0.5 * t),
                        cy - r * (0.5 + 1.1 * t) + r * 0.5 * t * t)
                       for t in (0.0, 0.35, 0.7, 1.0)]
                d.line(pts, fill=colour, width=int(r * 0.22), joint="curve")
        elif style == "antlers":
            for sign in (-1, 1):
                base = (cx + sign * r * 0.42, cy - r * 0.62)
                tip = (cx + sign * r * 0.95, cy - r * 1.85)
                d.line([base, tip], fill=colour, width=int(r * 0.16))
                for k in (0.35, 0.7):
                    mid = (base[0] + (tip[0] - base[0]) * k,
                           base[1] + (tip[1] - base[1]) * k)
                    d.line([mid, (mid[0] + sign * r * 0.45,
                                  mid[1] - r * 0.30)],
                           fill=colour, width=int(r * 0.11))
        elif style == "crown":
            for i in range(5):
                x = cx - r * 0.7 + i * r * 0.35
                self.poly(d, [(x - r * 0.11, cy - r * 0.72),
                              (x + r * 0.11, cy - r * 0.72),
                              (x, cy - r * (1.05 + 0.25 * (i % 2)))],
                          colour, self.outline)
        elif style == "single":
            self.poly(d, [(cx - r * 0.20, cy - r * 0.72),
                          (cx + r * 0.20, cy - r * 0.72),
                          (cx, cy - r * 1.95)], colour, self.outline)

    def draw_tail(self, d, anatomy, sway):
        style = self.s.tail
        if style == "none" or anatomy.hips is None:
            return
        hx, hy = anatomy.hips
        s = self.s
        reach = self.w * 0.13 * s.scale
        tip = (hx - reach * (1.0 + 0.15 * sway), hy - reach * 0.25 * sway)
        colour = _shade(s.body, -0.06) + (255,)
        if style == "whip":
            d.line([(hx, hy), (hx - reach * 0.6, hy + reach * 0.1), tip],
                   fill=colour, width=int(reach * 0.20), joint="curve")
        elif style == "club":
            d.line([(hx, hy), tip], fill=colour, width=int(reach * 0.22))
            self.ell(d, tip[0], tip[1], reach * 0.30, reach * 0.30,
                     _shade(s.accent, -0.1) + (255,), self.outline, SS)
        elif style == "fan":
            for k in (-0.5, 0.0, 0.5):
                self.poly(d, [(hx, hy),
                              (tip[0], tip[1] + k * reach * 0.7),
                              (tip[0] + reach * 0.2,
                               tip[1] + k * reach * 0.4)],
                          _mix(s.accent, s.light, 0.3) + (238,))
        elif style == "forked":
            for k in (-0.35, 0.35):
                d.line([(hx, hy), (tip[0], tip[1] + k * reach)], fill=colour,
                       width=int(reach * 0.16))
        elif style == "flame":
            for k, mix_amount in ((0.0, 0.55), (0.4, 0.3), (-0.4, 0.3)):
                self.poly(d, [(hx, hy - reach * 0.12),
                              (hx, hy + reach * 0.12),
                              (tip[0] + k * reach * 0.4,
                               tip[1] + k * reach * 0.5)],
                          _mix(s.body, (255, 226, 140), mix_amount) + (240,))

    def draw_wings(self, d, anatomy, flap):
        style = self.s.wings
        if style == "none" or not anatomy.shoulders:
            return
        s = self.s
        span = self.w * 0.20 * s.scale   # kept inside the canvas: see CANVAS
        rise = self.h * (0.12 + 0.06 * flap)
        membrane = _mix(s.accent, s.light, 0.28)
        for sign, (ax, ay) in zip((-1, 1), anatomy.shoulders[:2]):
            if style == "bat":
                pts = [(ax, ay)]
                for k in (0.45, 0.75, 1.0):
                    pts.append((ax + sign * span * k,
                                ay - rise * (1.0 - 0.5 * k)))
                pts.append((ax + sign * span * 0.85, ay + rise * 0.5))
                self.poly(d, pts, membrane + (232,), self.outline)
            elif style == "feather":
                for i in range(4):
                    t = i / 3.0
                    self.poly(d, [(ax, ay + t * rise * 0.3),
                                  (ax + sign * span * (0.6 + 0.4 * t),
                                   ay - rise * (0.9 - 0.55 * t)),
                                  (ax + sign * span * (0.5 + 0.35 * t),
                                   ay + rise * (0.15 + 0.25 * t))],
                              _shade(membrane, 0.12 - 0.06 * i) + (240,),
                              self.outline)
            elif style == "insect":
                for i, (scale_x, scale_y) in enumerate(((1.0, 0.55),
                                                        (0.72, 0.36))):
                    self.ell(d, ax + sign * span * 0.55 * scale_x,
                             ay - rise * 0.35 + i * rise * 0.45,
                             span * 0.5 * scale_x, rise * scale_y,
                             _mix(membrane, (255, 255, 255), 0.35) + (150,),
                             self.outline, max(1, SS // 2))
            elif style == "energy":
                for i in range(3):
                    alpha = 210 - i * 55
                    self.poly(d, [(ax, ay),
                                  (ax + sign * span * (0.7 + 0.15 * i),
                                   ay - rise * (1.1 - 0.25 * i)),
                                  (ax + sign * span * (0.5 + 0.15 * i),
                                   ay + rise * 0.35)],
                              _mix(s.glow, (255, 255, 255), 0.3) + (alpha,))

    def draw_back_features(self, d, anatomy, flicker):
        """Spines, crystal shards, plating, rocks -- along the spine."""
        s, feats = self.s, self.s.features
        if not anatomy.back:
            return
        r = anatomy.head_r
        if feats.get("spines", 0) >= 0.5 or self.spike_n:
            count = max(self.spike_n, 3 if feats.get("spines", 0) >= 0.5 else 0)
            for i in range(min(count, len(anatomy.back) * 2)):
                bx, by = anatomy.back[i % len(anatomy.back)]
                bx += (i // len(anatomy.back)) * r * 0.4
                self.poly(d, [(bx - r * 0.16, by + r * 0.10),
                              (bx + r * 0.16, by + r * 0.10),
                              (bx, by - r * 0.72)],
                          _shade(s.accent, -0.05) + (250,))
        if feats.get("crystal", 0) >= 0.5:
            shard = _mix(type_colour("Ice"), (255, 255, 255), 0.32)
            for i, (bx, by) in enumerate(anatomy.back[:3]):
                lean = (-1, 1, 0)[i % 3]
                self.poly(d, [(bx - r * 0.22, by + r * 0.12),
                              (bx + r * 0.22, by + r * 0.12),
                              (bx + lean * r * 0.5, by - r * 1.6)],
                          shard + (238,), _shade(shard, -0.45) + (255,))
        if feats.get("rocks", 0) >= 0.5:
            rock = _shade(s.body, -0.30)
            for bx, by in anatomy.back[:3]:
                self.poly(d, [(bx - r * 0.34, by + r * 0.22),
                              (bx - r * 0.05, by - r * 0.42),
                              (bx + r * 0.34, by + r * 0.22)],
                          rock + (252,), _shade(rock, -0.4) + (255,))
        if feats.get("plating", 0) >= 0.5:
            plate = _mix(type_colour("Steel"), s.light, 0.30)
            for i, (bx, by) in enumerate(anatomy.back[:3]):
                d.rounded_rectangle([bx - r * 0.42, by - r * 0.16,
                                     bx + r * 0.42, by + r * 0.14],
                                    radius=r * 0.12, fill=plate + (238,),
                                    outline=_shade(plate, -0.45) + (255,))
        if feats.get("flame", 0) >= 0.5:
            cx, cy = anatomy.head
            tip = cy - r * (1.4 + 0.4 * flicker)
            for dx, scale in ((-0.42, 0.7), (0.0, 1.0), (0.42, 0.7)):
                self.poly(d, [(cx + dx * r - r * 0.30, cy - r * 0.55),
                              (cx + dx * r + r * 0.30, cy - r * 0.55),
                              (cx + dx * r, cy + (tip - cy) * scale)],
                          _mix(s.body, (255, 232, 150),
                               0.35 + 0.2 * scale) + (238,))
        if feats.get("leaves", 0) >= 0.5 and s.build != "plant":
            cx, cy = anatomy.head
            leaf = _mix(type_colour("Grass"), s.light, 0.2)
            for i in range(3):
                angle = math.radians(-145 + i * 65)
                lx = cx + math.cos(angle) * r * 1.05
                ly = cy - r * 0.5 + math.sin(angle) * r * 0.5
                self.ell(d, lx, ly, r * 0.38, r * 0.18, leaf + (245,),
                         _shade(leaf, -0.45) + (255,), max(1, SS // 2))
        if feats.get("antennae", 0) >= 0.5:
            cx, cy = anatomy.head
            for sign in (-1, 1):
                d.line([(cx + sign * r * 0.3, cy - r * 0.7),
                        (cx + sign * r * 0.85, cy - r * 1.6)],
                       fill=_shade(s.accent, -0.2) + (255,),
                       width=int(max(2, r * 0.13)))
                self.ell(d, cx + sign * r * 0.85, cy - r * 1.6, r * 0.13,
                         r * 0.13, _shade(s.accent, 0.2) + (255,))
        if feats.get("bolts", 0) >= 0.5:
            bolt = _mix(type_colour("Electric"), (255, 255, 255), 0.28)
            for sign, (ax, ay) in zip((-1, 1), anatomy.shoulders[:2]):
                self.poly(d, [(ax, ay), (ax + sign * r * 0.6, ay + r * 0.5),
                              (ax + sign * r * 0.2, ay + r * 0.55),
                              (ax + sign * r * 0.75, ay + r * 1.3),
                              (ax - sign * r * 0.05, ay + r * 0.7)],
                          bolt + (240,))

    def draw_pattern(self, d, anatomy):
        style = self.s.pattern
        if style == "none":
            return
        s = self.s
        cx, cy = anatomy.head
        r = anatomy.head_r
        hips = anatomy.hips or (cx, cy)
        colour = _shade(s.accent, -0.25) + (105,)
        if style == "stripes":
            for i in range(3):
                y = cy + r * (1.2 + i * 0.55)
                d.line([(cx - r * 0.9, y), (cx + r * 0.9, y)], fill=colour,
                       width=int(max(2, r * 0.16)))
        elif style == "spots":
            for dx, dy in self.spots:
                self.ell(d, cx + dx * r, cy + r * (1.0 + dy),
                         r * 0.16, r * 0.16, colour)
        elif style == "plates":
            for i in range(3):
                y = cy + r * (1.15 + i * 0.5)
                d.arc([cx - r * 0.9, y - r * 0.4, cx + r * 0.9, y + r * 0.4],
                      200, 340, fill=colour, width=int(max(2, r * 0.14)))
        elif style == "scales":
            for row in range(3):
                for col in range(3):
                    ox = cx + (col - 1) * r * 0.55
                    oy = cy + r * (1.1 + row * 0.45)
                    d.arc([ox - r * 0.26, oy - r * 0.26,
                           ox + r * 0.26, oy + r * 0.26], 200, 340,
                          fill=colour, width=int(max(2, r * 0.10)))
        elif style == "veins":
            glow = _mix(s.glow, (255, 255, 255), 0.25) + (130,)
            for sign in (-1, 1):
                d.line([(cx, cy + r * 0.9),
                        (cx + sign * r * 0.5, cy + r * 1.6),
                        (cx + sign * r * 0.25, cy + r * 2.4)],
                       fill=glow, width=int(max(2, r * 0.13)), joint="curve")
        elif style == "cracks":
            dark = _shade(s.body, -0.55) + (150,)
            for sign in (-1, 1):
                d.line([(cx + sign * r * 0.2, cy + r * 0.9),
                        (cx + sign * r * 0.7, cy + r * 1.5),
                        (cx + sign * r * 0.35, cy + r * 2.1)],
                       fill=dark, width=int(max(2, r * 0.10)))

    def draw_particles(self, layer, phase):
        kind = self.s.features.get("particles")
        if not isinstance(kind, str):
            return
        d = ImageDraw.Draw(layer)
        rng = random.Random(self.s.seed ^ 0x9A17C3)
        colours = {
            "ember": _mix(type_colour("Fire"), (255, 230, 150), 0.4),
            "spark": _mix(self.s.glow, (255, 255, 255), 0.45),
            "leaf": type_colour("Grass"),
            "snow": _mix(type_colour("Ice"), (255, 255, 255), 0.5),
            "bubble": _mix(type_colour("Water"), (255, 255, 255), 0.45),
            "shadow": _shade(type_colour("Ghost"), -0.05),
        }
        colour = colours.get(kind, self.s.glow)
        for i in range(7):
            seed_x = rng.uniform(0.18, 0.82)
            speed = rng.uniform(0.6, 1.4)
            drift = rng.uniform(-0.05, 0.05)
            t = (phase * speed + i / 7.0) % 1.0
            px = self.w * (seed_x + drift * math.sin(t * math.tau))
            py = self.h * (0.88 - 0.66 * t)
            radius = self.w * 0.013 * (1.5 - t)
            self.ell(d, px, py, radius, radius,
                     colour + (int(215 * (1.0 - t)),))

    # -- one frame -------------------------------------------------------
    def _outline(self, frame):
        """Ink the silhouette.

        A near-black outline is one of the most common colours in every
        downloaded sprite -- it's what makes them read as drawn characters
        rather than flat shapes, and what stops them dissolving into the
        arena behind them.
        """
        alpha = frame.getchannel("A").point(
            lambda value: 255 if value >= ALPHA_CUTOFF else 0)
        if not alpha.getbbox():
            return frame
        inner = alpha.filter(ImageFilter.MinFilter(3))
        edge = ImageChops.subtract(alpha, inner).point(
            lambda value: 255 if value > 0 else 0)
        frame.paste(Image.new("RGBA", frame.size, OUTLINE + (255,)), (0, 0),
                    edge)
        return frame

    def shade(self, layer):
        """Band light and shade across whatever has been drawn.

        The downloaded sprites shade in discrete steps -- a lit tone toward
        the light, the base, then a shadow tone away from it -- so a flat
        fill with only an outline looks like a decal beside them. Masking by
        the layer's own alpha means this works for every body plan without
        any of them having to know about it.
        """
        mask = layer.getchannel("A").point(
            lambda v: 255 if v >= ALPHA_CUTOFF else 0)
        if not mask.getbbox():
            return
        bands = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(bands)
        # light falls from the upper left, as it does on every sprite in the
        # downloaded set
        draw.ellipse([-self.w * 0.25, -self.h * 0.30,
                      self.w * 0.62, self.h * 0.66],
                     fill=(255, 255, 255, 46))
        draw.ellipse([-self.w * 0.10, -self.h * 0.16,
                      self.w * 0.40, self.h * 0.40],
                     fill=(255, 255, 255, 42))
        draw.ellipse([self.w * 0.44, self.h * 0.34,
                      self.w * 1.28, self.h * 1.26],
                     fill=(12, 10, 26, 66))
        layer.alpha_composite(Image.composite(
            bands, Image.new("RGBA", layer.size, (0, 0, 0, 0)), mask))

    def frame(self, index):
        s = self.s
        t = index / float(FRAMES)
        wave = math.sin(t * math.tau)
        flap = 0.5 + 0.5 * math.sin(t * math.tau)
        pulse = 0.5 + 0.5 * math.sin(t * math.tau)
        flicker = 0.5 + 0.5 * math.sin(t * math.tau * 2 + 1.1)
        blink = 0.06 < ((t + 0.5) % 1.0) < 0.11
        bob = wave * self.h * (0.022 if s.build in HOVERS else 0.009)

        canvas = self.layer()

        if s.aura:
            # Sparks orbiting the creature, not a filled disc behind it. GIF
            # transparency is all-or-nothing, so a soft glow can only ship as
            # a hard-edged plate -- which looked like the Pokemon was
            # standing on a coloured dinner plate. Discrete motes read as
            # energy and suit the pixel style.
            aura = self.layer()
            adraw = ImageDraw.Draw(aura)
            count = 10
            radius = (0.30 + 0.02 * pulse) * self.w * s.scale
            for i in range(count):
                angle = math.tau * (i / count) + t * math.tau * 0.35
                px = self.cx + math.cos(angle) * radius
                py = self.h * 0.56 + math.sin(angle) * radius * 0.72
                size = 1.6 + 1.5 * (0.5 + 0.5 * math.sin(angle * 3 + pulse))
                self.ell(adraw, px, py, size, size,
                         _mix(s.glow, (255, 255, 255), 0.35) + (235,))
            canvas.alpha_composite(aura)

        if s.grounded:
            shadow = self.layer()
            sdraw = ImageDraw.Draw(shadow)
            self.ell(sdraw, self.cx, self.gy + self.h * 0.02,
                     self.w * 0.20 * s.scale, self.h * 0.018,
                     (0, 0, 0, 105))
            canvas.alpha_composite(
                shadow.filter(ImageFilter.GaussianBlur(radius=2)))

        back = self.layer()
        bdraw = ImageDraw.Draw(back)

        body = self.layer()
        bodyd = ImageDraw.Draw(body)
        builder = getattr(self, "build_" + s.build)
        if s.build == "floater":
            anatomy = builder(bodyd, bob, spin=t * math.tau * 0.5)
        elif s.build == "swarm":
            anatomy = builder(bodyd, bob, phase=t)
        else:
            anatomy = builder(bodyd, bob)

        self.draw_tail(bdraw, anatomy, wave)
        self.draw_wings(bdraw, anatomy, flap)
        self.shade(back)
        self.shade(body)
        canvas.alpha_composite(back)
        canvas.alpha_composite(body)

        detail = self.layer()
        ddraw = ImageDraw.Draw(detail)
        self.draw_pattern(ddraw, anatomy)
        self.draw_back_features(ddraw, anatomy, flicker)
        self.draw_horns(ddraw, anatomy)
        self.draw_face(ddraw, anatomy, blink, pulse)
        canvas.alpha_composite(detail)

        particles = self.layer()
        self.draw_particles(particles, t)
        canvas.alpha_composite(particles)

        # resolve down first, then ink: outlining the supersampled canvas
        # would leave a fat, soft edge once it was scaled
        return self._outline(canvas.resize(CANVAS, Image.LANCZOS))


# ---------------------------------------------------------------------- output
def _write_gif(frames, path):
    flats = []
    for frame in frames:
        alpha = frame.getchannel("A").point(
            lambda value: 0 if value < ALPHA_CUTOFF else value)
        frame = frame.copy()
        frame.putalpha(alpha)
        base = Image.new("RGB", frame.size, CHROMA)
        base.paste(frame, (0, 0), frame)
        flats.append(base)

    montage = Image.new("RGB", (flats[0].width, flats[0].height * len(flats)),
                        CHROMA)
    for i, flat in enumerate(flats):
        montage.paste(flat, (0, i * flats[0].height))
    palette_source = montage.convert("P", palette=Image.ADAPTIVE, colors=255)

    palette = palette_source.getpalette() or []
    best, best_distance = 0, None
    for i in range(len(palette) // 3):
        r, g, b = palette[i * 3:i * 3 + 3]
        distance = (r - CHROMA[0]) ** 2 + (g - CHROMA[1]) ** 2 + \
            (b - CHROMA[2]) ** 2
        if best_distance is None or distance < best_distance:
            best, best_distance = i, distance

    converted = [flat.quantize(palette=palette_source, dither=Image.NONE)
                 for flat in flats]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    converted[0].save(path, save_all=True, append_images=converted[1:],
                      duration=DURATION, loop=0, transparency=best,
                      disposal=2, optimize=False)


def crop_to_content(frames, pad=CROP_PAD):
    """Trim the shared transparent margin off a whole animation.

    One box for every frame, not per frame -- cropping each to its own
    bounding box would make the creature jitter as its own bob and particles
    changed the extents.
    """
    box = None
    for frame in frames:
        alpha = frame.getchannel("A").point(
            lambda value: 0 if value < ALPHA_CUTOFF else 255)
        bounds = alpha.getbbox()
        if bounds is None:
            continue
        box = bounds if box is None else (
            min(box[0], bounds[0]), min(box[1], bounds[1]),
            max(box[2], bounds[2]), max(box[3], bounds[3]))
    if box is None:
        return frames, False
    width, height = frames[0].size
    touching = (box[0] <= 0 or box[1] <= 0 or box[2] >= width
                or box[3] >= height)
    box = (max(0, box[0] - pad), max(0, box[1] - pad),
           min(width, box[2] + pad), min(height, box[3] + pad))
    return [f.crop(box) for f in frames], touching


def fit_to_budget(frames, budget=MAX_SIZE):
    """Scale a whole animation down together if it exceeds the budget."""
    width, height = frames[0].size
    factor = min(1.0, budget[0] / width, budget[1] / height)
    if factor >= 1.0:
        return frames
    size = (max(1, int(round(width * factor))),
            max(1, int(round(height * factor))))
    # NEAREST, not LANCZOS: resampling smoothly would blur away the hard
    # pixel edges and the outline that make these read as sprites
    return [f.resize(size, Image.NEAREST) for f in frames]


def render(species, crop=True, verbose=True):
    """Draw the animation, shrinking if anything would be cut off.

    Coordinates are fractions of the canvas, so a bigger canvas just draws a
    bigger creature -- it cannot fix an overrun. Pulling the whole thing in
    and redrawing can. The crop and size budget then bring it back to a
    normal sprite size regardless, so nothing ships with a wing or an antler
    sliced off.
    """
    original_scale = species.scale
    try:
        for attempt in range(4):
            painter = Painter(species)
            frames = [painter.frame(i) for i in range(FRAMES)]
            if not crop:
                return frames
            cropped, clipped = crop_to_content(frames)
            if not clipped:
                return fit_to_budget(cropped)
            species.scale *= 0.86
        if verbose:
            print("     (note: %s still touches the edge after shrinking)"
                  % species.key)
        return fit_to_budget(cropped)
    finally:
        species.scale = original_scale


def build(species):
    frames = render(species)
    left = os.path.join(ROOT, "Assets", "pokemon", "left",
                        "%s-left.gif" % species.key)
    right = os.path.join(ROOT, "Assets", "pokemon", "right",
                         "%s-right.gif" % species.key)
    _write_gif(frames, left)
    _write_gif([f.transpose(Image.FLIP_LEFT_RIGHT) for f in frames], right)


def load_species():
    path = os.path.join(ROOT, "Data", "pokemon.csv")
    with open(path, encoding="ISO-8859-1") as handle:
        return [Species(row) for row in csv.DictReader(handle)
                if row.get("Name")]


def contact_sheet(targets, path, columns=10, zoom=2):
    width, height = CANVAS
    rows = (len(targets) + columns - 1) // columns
    sheet = Image.new("RGB", (width * zoom * columns, height * zoom * rows),
                      CHROMA)
    for i, species in enumerate(targets):
        frame = render(species)[4]
        cell = Image.new("RGBA", CANVAS, CHROMA + (255,))
        cell.alpha_composite(frame, (max(0, (CANVAS[0] - frame.width) // 2),
                                    max(0, CANVAS[1] - frame.height)))
        sheet.paste(cell.convert("RGB").resize(
            (width * zoom, height * zoom), Image.NEAREST),
            ((i % columns) * width * zoom, (i // columns) * height * zoom))
    sheet.save(path)


def main(argv):
    force = "--force" in argv
    sheet = "--sheet" in argv
    wanted = [a for a in argv if not a.startswith("-")]
    everyone = load_species()

    if wanted:
        lowered = {w.lower().strip() for w in wanted}
        targets = [s for s in everyone
                   if s.name.lower() in lowered or s.key in lowered]
    else:
        left_dir = os.path.join(ROOT, "Assets", "pokemon", "left")
        have = set(os.listdir(left_dir)) if os.path.isdir(left_dir) else set()
        targets = [s for s in everyone
                   if force or "%s-left.gif" % s.key not in have]

    if not targets:
        print("Nothing to draw.")
        return 0

    if sheet:
        out = os.path.join(ROOT, "Test", "sprite_sheet.png")
        contact_sheet(targets, out)
        print("Contact sheet -> %s (%d sprites, no game files touched)"
              % (out, len(targets)))
        for species in targets:
            print("  %-22s %-24s %s" % (species.key,
                                        "/".join(species.types),
                                        species.summary()))
        return 0

    print("Drawing %d sprite(s) into Assets/pokemon/..." % len(targets))
    for species in targets:
        build(species)
        print("  %-22s %-24s %s" % (species.key, "/".join(species.types),
                                    species.summary()))
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
