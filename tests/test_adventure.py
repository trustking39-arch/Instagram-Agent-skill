import numpy as np
import pytest

from content_crew.animation.catalog import TYPES, make_text, pick_hashtags
from content_crew.animation.worlds import COMMON, WORLD_TEXT, pick, title_caption

skia = pytest.importorskip("skia")

KEYS = ["intro", "early", "challenge", "danger", "hide", "weather", "herd", "night"]


def test_worlds_have_texts_beats_and_scene_settings():
    from content_crew.animation.scenes.adventure import BEAT_HOURS, WORLDS

    assert set(WORLDS) == set(WORLD_TEXT) == set(TYPES["adventure"]["params"]["world"])
    for key, spec in WORLDS.items():
        assert len(spec["beats"]) == len(BEAT_HOURS), key
        for line_key in KEYS + list(COMMON):
            for variant in range(4):
                line = pick(key, line_key, variant)
                assert line and "{" not in line, (key, line_key)


def test_titles_captions_and_hashtags_are_english():
    title, caption = make_text("adventure", {"world": "medieval", "ending": "pet", "variant": 2}, "minor", 1)
    assert title == "24 Hours In The Middle Ages" and "baby dragon" in caption
    assert "Part 2" in title_caption("arctic", "eyes", 0)[1] or "PART 2" in title_caption("arctic", "eyes", 0)[1]
    tags = pick_hashtags(WORLD_TEXT["jungle"]["tags"], "adventure", "pentatonic", "en")
    assert tags == ["#whatif", "#animation", "#timetravel", "#jungle", "#jaguar"]


def test_every_creature_draws_normal_and_as_baby():
    from content_crew.animation.creatures import SPECIES, bird, quadruped, rider

    surf = skia.Surface(400, 300)
    c = surf.getCanvas()
    for kind in SPECIES:
        for cute in (False, True):
            hx, hy = quadruped(c, kind, 200, 280, 120, -1, 1.3, (30, 20, 30), gallop=not cute, cute=cute,
                               eye=((255, 200, 60), 1.0), jaw=0.5)
            assert 0 < hx < 400 and 0 < hy < 300, kind
    rider(c, 200, 150, 50, 1, (30, 20, 30), "knight", 1.0)
    rider(c, 200, 150, 50, -1, (30, 20, 30), "desert", 1.0)
    bird(c, 100, 50, 20, 0.5, (30, 20, 30))


@pytest.mark.parametrize("world", ["iceage", "arctic", "egypt", "jungle", "savanna", "medieval", "wildwest"])
@pytest.mark.parametrize("ending", ["pet", "eyes"])
def test_story_runs_through_all_beats_and_ends_at_home(world, ending):
    from content_crew.animation.engine import Ctx
    from content_crew.animation.palettes import PALETTES
    from content_crew.animation.scenes.adventure import Adventure

    W, H, fps = 90, 160, 10
    scene = Adventure(Ctx(W, H, fps, 40, 3, PALETTES["neon"], "minor"), {"world": world, "ending": ending, "variant": 2})
    lines = scene.voiceover()
    assert [t for t, _ in lines] == sorted(t for t, _ in lines) and len(lines) == 14
    frame = np.zeros((H, W, 4), np.uint8)
    surf = skia.Surface(frame, colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
    seen = set()
    while not scene.finished() and scene.t < 80:
        scene.update(1 / fps)
        hour = scene.hour()
        beat = "home" if scene.epi() >= 0 else min(int(hour // 3), 8)
        if beat not in seen or scene.epi() > 3.2 and "late" not in seen:  # jede Phase einmal zeichnen
            seen.add(beat if scene.epi() < 3.2 else "late")
            seen.add(beat)
            surf.getCanvas().clear(skia.ColorBLACK)
            scene.draw(surf.getCanvas())
    assert scene.finished() and scene.done_at is not None
    assert abs(scene.done_at - (scene.epi_start + scene.epi_len)) < 0.3
    assert "home" in seen and len(seen) >= 9
    assert frame[..., :3].mean() > 3  # das letzte Bild ist nicht schwarz
