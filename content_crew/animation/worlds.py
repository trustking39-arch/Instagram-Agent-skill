"""Story-Serie „24 Stunden in …“: Welten mit Titel, Caption, Hashtags und englischer Erzählung.

Das leuchtende Skelett erzählt selbst (Kokoro-Stimme, Englisch). Pro Abschnitt gibt es zwei Varianten,
damit Videos derselben Welt nicht gleich klingen.
"""

from __future__ import annotations

import random

WORLD_TEXT: dict[str, dict] = {
    "iceage": {
        "title": "24 Hours In The Ice Age", "where": "in the Ice Age", "emoji": "🦣", "label_de": "Eiszeit",
        "tags": ["#iceage", "#mammoth"], "pet": "a baby mammoth",
        "lines": {
            "intro": ["What if you spent twenty-four hours in the Ice Age? I tried it.",
                      "Twenty-four hours in the Ice Age. Let's see if I survive."],
            "early": ["Hour one. A woolly mammoth. It's as big as a bus!", "Hour one. That's a real woolly mammoth!"],
            "challenge": ["Hour four. Minus forty degrees. Good thing I have no skin.",
                          "Hour four. It's so cold my bones are rattling."],
            "danger": ["A saber-toothed cat! Those teeth are longer than my fingers!",
                       "Saber teeth! I have never run this fast in my life."],
            "hide": ["Hour ten. I hide behind a block of ice and don't move a bone.",
                     "Hour ten. Behind the ice. Don't move. Don't breathe. Oh wait, I can't."],
            "weather": ["Hour thirteen. A snowstorm. I can't see anything!",
                        "Hour thirteen. The snowstorm is so strong it almost blows me away."],
            "herd": ["Hour sixteen. A herd of mammoths walks into the sunset.",
                     "Hour sixteen. Mammoths, as far as I can see. Beautiful."],
            "night": ["Night. The northern lights are amazing... but something is watching me.",
                      "Night. I sleep by the fire under the northern lights. Something is out there."],
        },
    },
    "arctic": {
        "title": "24 Hours In The Arctic", "where": "in the Arctic", "emoji": "🐻‍❄️", "label_de": "Arktis",
        "tags": ["#arctic", "#polarbear"], "pet": "a baby polar bear",
        "lines": {
            "intro": ["What if you spent twenty-four hours in the Arctic? I tried it.",
                      "Twenty-four hours at the North Pole. How hard can it be?"],
            "early": ["Hour one. A reindeer walks right past me.", "Hour one. A wild reindeer. It doesn't even care about me."],
            "challenge": ["Hour four. The wind is freezing. Good thing I have no nose to freeze.",
                          "Hour four. Minus thirty. Even my bones are shivering."],
            "danger": ["A polar bear! The biggest land predator on Earth!",
                       "A polar bear! It can smell me from miles away!"],
            "hide": ["Hour ten. I hide behind the ice and don't move a bone.",
                     "Hour ten. I hide behind an ice block. Please don't sniff me."],
            "weather": ["Hour thirteen. A blizzard. Everything turns white!",
                        "Hour thirteen. A blizzard hits. I can't even see my own hand."],
            "herd": ["Hour sixteen. A herd of reindeer runs into the sunset.",
                     "Hour sixteen. Reindeer everywhere. Santa must be close."],
            "night": ["Night. The northern lights are dancing... and two eyes are watching me.",
                      "Night. The sky is glowing green. Something is breathing in the dark."],
        },
    },
    "egypt": {
        "title": "24 Hours In Ancient Egypt", "where": "in ancient Egypt", "emoji": "🐫", "label_de": "Altes Ägypten",
        "tags": ["#ancientegypt", "#pyramids"], "pet": "a little desert cat",
        "lines": {
            "intro": ["What if you spent twenty-four hours in ancient Egypt? I tried it.",
                      "Twenty-four hours in ancient Egypt. The pyramids are brand new!"],
            "early": ["Hour one. A camel. And it's staring at me.", "Hour one. The pyramids are shining. And a camel walks by."],
            "challenge": ["Hour four. It's so hot. Good thing I can't get a sunburn.",
                          "Hour four. Fifty degrees in the sun. Bones don't sweat, luckily."],
            "danger": ["A crocodile from the Nile! And it's fast!", "A Nile crocodile! Those jaws could crush my skull!"],
            "hide": ["Hour ten. I hide behind a stone block and don't move a bone.",
                     "Hour ten. Behind a pyramid stone. Stay still. Stay still."],
            "weather": ["Hour thirteen. A sandstorm! Sand in every bone.", "Hour thirteen. A wall of sand is coming!"],
            "herd": ["Hour sixteen. A camel caravan passes the pyramids.",
                     "Hour sixteen. A caravan crosses the desert at sunset."],
            "night": ["Night. A million stars over the desert... but something is watching me.",
                      "Night. The desert gets cold. And I hear jackals in the dark."],
        },
    },
    "jungle": {
        "title": "24 Hours In The Jungle", "where": "in the jungle", "emoji": "🐆", "label_de": "Dschungel",
        "tags": ["#jungle", "#jaguar"], "pet": "a baby jaguar",
        "lines": {
            "intro": ["What if you spent twenty-four hours in the jungle? I tried it.",
                      "Twenty-four hours in the deepest jungle. Wish me luck."],
            "early": ["Hour one. An elephant! It's pushing trees out of its way.",
                      "Hour one. An elephant walks through the jungle like a bulldozer."],
            "challenge": ["Hour four. It's so humid. Good thing I have no skin to sweat.",
                          "Hour four. Mosquitoes everywhere. Ha, nothing to bite!"],
            "danger": ["A jaguar! The strongest bite of all the big cats!", "A jaguar! It climbs, it swims, and it's fast!"],
            "hide": ["Hour ten. I hide in the bushes and don't move a bone.",
                     "Hour ten. In the bushes. I hope jaguars can't count bones."],
            "weather": ["Hour thirteen. Tropical rain. It comes down like a waterfall!",
                        "Hour thirteen. A jungle storm. Thunder shakes the trees!"],
            "herd": ["Hour sixteen. A family of elephants walks into the sunset.",
                     "Hour sixteen. The elephants are going home. So should I."],
            "night": ["Night. Fireflies everywhere... but something is watching me.",
                      "Night. The jungle is never quiet. Glowing eyes in the trees."],
        },
    },
    "savanna": {
        "title": "24 Hours In The Savanna", "where": "in the African savanna", "emoji": "🦁", "label_de": "Savanne",
        "tags": ["#africa", "#lion"], "pet": "a baby lion",
        "lines": {
            "intro": ["What if you spent twenty-four hours in the African savanna? I tried it.",
                      "Twenty-four hours in the savanna. Lions, elephants, and me."],
            "early": ["Hour one. A giraffe! Its neck is longer than my whole body.",
                      "Hour one. A giraffe. I have to look way up."],
            "challenge": ["Hour four. The sun is burning. Good thing I can't get a sunburn.",
                          "Hour four. No shade anywhere. Even the vultures are watching me."],
            "danger": ["A lion! And he looks hungry!", "A lion! Lions can run sixty kilometers per hour!"],
            "hide": ["Hour ten. I hide behind a rock and don't move a bone.",
                     "Hour ten. Behind the rock. Lions love bones. This is bad."],
            "weather": ["Hour thirteen. A thunderstorm rolls over the savanna!",
                        "Hour thirteen. The rainy season starts. Right now!"],
            "herd": ["Hour sixteen. A herd of elephants walks into the sunset.",
                     "Hour sixteen. Elephants at sunset. Just like in the movies."],
            "night": ["Night. I sleep by the fire... but hyenas are laughing in the dark.",
                      "Night. The stars are bright. Something is moving in the grass."],
        },
    },
    "medieval": {
        "title": "24 Hours In The Middle Ages", "where": "in the Middle Ages", "emoji": "🐉", "label_de": "Mittelalter",
        "tags": ["#medieval", "#dragon"], "pet": "a baby dragon",
        "lines": {
            "intro": ["What if you spent twenty-four hours in the Middle Ages? I tried it.",
                      "Twenty-four hours in the Middle Ages. No phone, no Wi-Fi, no problem."],
            "early": ["Hour one. A knight on his horse. Nice armor, buddy!", "Hour one. A real knight rides past the castle."],
            "challenge": ["Hour four. The castle is huge... and nobody has ever seen a walking skeleton.",
                          "Hour four. Everyone here thinks I'm a ghost."],
            "danger": ["A dragon! Dragons are real?!", "A dragon! And it breathes fire!"],
            "hide": ["Hour ten. I hide in the bushes and don't move a bone.",
                     "Hour ten. Hiding. Dragons can't smell bones. I hope."],
            "weather": ["Hour thirteen. A thunderstorm over the castle!", "Hour thirteen. Lightning hits the castle tower!"],
            "herd": ["Hour sixteen. The knights ride home into the sunset.",
                     "Hour sixteen. The knights are back. I think they're hunting the dragon."],
            "night": ["Night. I sleep by the fire... but something is watching me.",
                      "Night. Wolves are howling outside the castle."],
        },
    },
    "wildwest": {
        "title": "24 Hours In The Wild West", "where": "in the Wild West", "emoji": "🤠", "label_de": "Wilder Westen",
        "tags": ["#wildwest", "#cowboy"], "pet": "a little wolf pup",
        "lines": {
            "intro": ["What if you spent twenty-four hours in the Wild West? I tried it.",
                      "Twenty-four hours in the Wild West. Yee-haw!"],
            "early": ["Hour one. A wild mustang gallops past me.", "Hour one. A wild horse. Nobody owns this one."],
            "challenge": ["Hour four. No water anywhere. Good thing I'm never thirsty.",
                          "Hour four. It's so hot even the cactus is sweating."],
            "danger": ["A bison stampede! Tons of them, coming my way!", "Stampede! The ground is shaking!"],
            "hide": ["Hour ten. I hide behind a wagon and don't move a bone.",
                     "Hour ten. Behind the wagon. The dust is everywhere."],
            "weather": ["Hour thirteen. A dust storm! Tumbleweeds everywhere!",
                        "Hour thirteen. A dust storm rolls over the desert!"],
            "herd": ["Hour sixteen. Wild horses run into the sunset.", "Hour sixteen. The mustangs are free. Beautiful."],
            "night": ["Night. Coyotes are howling... and something is watching me.",
                      "Night. Campfire, stars, and something sneaking around."],
        },
    },
}

COMMON = {
    "seven": ["Hour seven..."],
    "run": ["Run!", "Run, run, run!"],
    "portal": ["Hour twenty-three. The portal is back. Time to go home!",
               "Hour twenty-three. There's my portal. I'm going home!"],
    "pet_home": ["Twenty twenty-six. Home sweet home. Wait... what was that?",
                 "Back in twenty twenty-six. Finally home. Hold on... something's moving."],
    "pet_found": ["{Pet} followed me through the portal!", "No way... {pet} came with me!"],
    "pet_end": ["I guess I have a new pet now. What should I call it?",
                "Looks like I have a new pet. Any name ideas?"],
    "eyes_home": ["Twenty twenty-six. Home at last. But why is the portal still open?",
                  "Back home. Twenty twenty-six. Why is the portal still glowing?"],
    "eyes_found": ["Uh-oh. Something came with me.", "Wait... something is coming through!"],
    "eyes_end": ["Should I make part two?", "Comment part two if you want to know what it is."],
}


def pick(world: str, key: str, variant: int) -> str:
    """Satz für einen Abschnitt – je nach Variante eine andere Formulierung."""
    options = WORLD_TEXT[world]["lines"].get(key) or COMMON[key]
    rng = random.Random(variant * 7919 + sum(map(ord, world + key)))
    line = rng.choice(options)
    pet = WORLD_TEXT[world]["pet"]
    return line.replace("{pet}", pet).replace("{Pet}", pet[0].upper() + pet[1:])


def title_caption(world: str, ending: str, variant: int) -> tuple[str, str]:
    t = WORLD_TEXT[world]
    rng = random.Random(variant * 31 + len(world))
    if ending == "pet":
        caption = rng.choice([
            f"I spent 24 hours {t['where']}… and {t['pet']} followed me home {t['emoji']}🦴 What should I name it?",
            f"24 hours {t['where']} – and I came back with {t['pet']} {t['emoji']}🦴 Name ideas?",
        ])
    else:
        caption = rng.choice([
            f"What if you spent 24 hours {t['where']}? {t['emoji']} Something came back with me… Part 2?",
            f"I survived 24 hours {t['where']} {t['emoji']} …or did I? Comment PART 2!",
        ])
    return t["title"], caption
