"""Map-for-Goblins item category classifier, ported faithfully from the
authoritative open-source implementation.

Source: https://github.com/VirusAlex/ERR-MapForGoblins-DLL
  - tools/generate_loot_massedit.py  (LOOT_CATEGORIES, the ordered classifier)
  - tools/map_categories.py          (slug -> icon PNG)
  - data/goods_*.json                (itemId lists: incantations, sorceries,
                                       spirit ashes, crafting, key items,
                                       crystal tears, ammo, sort groups)

The classifier is first-match-wins over an ordered list, exactly as MFG's
LOOT_CATEGORIES. It maps every item to one of the MFG category slugs, with
"misc" as the final fallback (MFG has no misc; we add it so nothing is dropped).

This is the ERR profile: spirit ashes live in 300000-399999 and the Rune Arc
goods id is 150 (both differ from vanilla per MFG's config.PROFILE == 'err').
"""
import json
import os

# This file is tools/erlib/, so the repo root is two levels up - not one. The
# loaders below fail soft, so getting this wrong costs no error at all: every
# id-list category silently degrades to "misc" instead.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_MFG_DIR = os.path.join(_ROOT, "data", "mfg")


MISSING = []          # data files that could not be read, for data_status()


def _load_set(name):
    path = os.path.join(_MFG_DIR, name)
    try:
        with open(path, encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError):
        MISSING.append(name)
        return set()


def _load_sort_groups():
    name = "goods_sort_groups.json"
    path = os.path.join(_MFG_DIR, name)
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        return {int(k): int(v) for k, v in raw.items()}
    except (OSError, ValueError):
        MISSING.append(name)
        return {}


def data_status():
    """-> warning string when the id lists are missing, else None.

    Without them the classifier still runs, but every id-list and sort-group
    category (crystal tears, incantations, sorceries, crafting materials,
    consumables, greases, ...) quietly collapses into "misc". Callers print
    this so a bad checkout is visible rather than merely disappointing.
    """
    if not MISSING:
        return None
    return (f"warning: {len(MISSING)} Map-for-Goblins data files missing from "
            f"{_MFG_DIR}\n         items will be under-categorised: "
            + ", ".join(sorted(MISSING)))


CRYSTAL_TEAR_IDS = _load_set("goods_crystal_tear_ids.json")
INCANTATION_IDS = _load_set("goods_incantation_ids.json")
SORCERY_IDS = _load_set("goods_sorcery_ids.json")
CRAFTING_IDS = _load_set("goods_crafting_ids.json")
KEYITEM_IDS = _load_set("goods_keyitem_ids.json")
AMMO_IDS = _load_set("weapon_ammo_ids.json")
SPIRIT_ASH_IDS = _load_set("goods_spirit_ash_ids.json")
GOODS_SORT_GROUPS = _load_sort_groups()

# ERR profile constants (differ per profile in MFG).
RUNE_ARC_ID = 150
SPIRIT_ASH_MIN, SPIRIT_ASH_MAX = 300000, 399999

PATE_IDS = {2200, 2201, 2202, 2203, 2204, 2205, 2206, 2207, 2002150}
PROGRESSION_EXTRA = {2002120, 2002130, 2190, 8867, 2170, 1000000, 2920}

FORTUNE_IDS = {
    900218, 900238, 900258, 900268, 900278, 900288,
    900308, 900318, 900328, 900338, 900348, 900368,
}
SEALED_CURIO_IDS = {
    1301900, 1302900, 1303900, 1304900, 1305900,
    1306900, 1307900, 1308900, 1309900,
}
PRAYERBOOK_IDS = {
    8850, 8851, 8852, 8854, 8855, 8856, 8857, 8858,
    8859, 8862, 8864, 8865, 8866, 2008014,
}
SMITHING_LOW_IDS = {
    10100, 10101, 10102, 10103, 10104, 10105,   # Smithing Stone [1]-[6]
    10160, 10161, 10162, 10163, 10164, 10165,   # Somber [1]-[6]
}
SMITHING_IDS = {
    10106, 10107,           # Smithing Stone [7]-[8]
    10166, 10167, 10200,    # Somber [7]-[9]
    10150, 10151,           # Scadushards
    10110, 10111,           # Shadow stones
    10170, 10171, 10172, 10173,  # Somber Shadow stones
}
SMITHING_RARE_IDS = {
    10140, 10168, 10114, 10174,   # Ancient Dragon + Primordial
}
GOLDEN_RUNE_LOW_IDS = {
    2900, 2901, 2902, 2903, 2904, 2905, 2906, 2907,  # Golden Rune [200]-[3000]
    2002951,                                           # Broken Rune [500]
    2002952, 2002953,                                  # Shadow Realm [2500]-[5000]
}
GOLDEN_RUNE_IDS = {
    2908, 2909, 2910, 2911, 2912,  # Golden Rune [4000]-[10000]
    2913,                           # Numen's Rune
    2914, 2915, 2916, 2917, 2918,  # Hero's Rune
    2919,                           # Lord's Rune
    2002954, 2002955, 2002956, 2002957, 2002958,  # Shadow Realm [7500]-[30000]
    2002959,                                       # Unsung Hero
    2002960,                                       # Marika's Rune
}
MP_FINGER_IDS = {
    100, 101, 103, 104, 105, 106, 108, 110, 111, 112,
}


def _sg(iid):
    return GOODS_SORT_GROUPS.get(iid, -1)


def categorise(iid, name, category):
    """-> MFG category slug for one item.

    iid      : item id (goods/weapon/protector/accessory/gem id)
    name     : English item name (may be empty)
    category : lotItemCategory (1=Goods 2=Weapon 3=Protector 4=Accessory 5=Gem)
    """
    low = (name or "").lower()

    if category == 1:
        # Key items (specific ids first, most specific -> least specific)
        if iid == 2130:
            return "celestial_dew"
        if "cookbook" in low:
            return "cookbooks"
        if iid in CRYSTAL_TEAR_IDS or iid in (250, 251, 2011010):
            return "crystal_tears"
        if iid == 8186:
            return "imbued_sword_keys"
        if iid in (8185, 2008033):
            return "larval_tears"
        if iid == 10070:
            return "lost_ashes"
        if iid in (9500, 9501, 9510, 2009500) or _sg(iid) in (30, 40):
            return "pots_n_perfumes"
        if iid in (10010, 10020, 2010100):
            return "seeds_tears"
        if iid == 2010000:
            return "scadutree_fragments"
        if iid in (8970, 8971, 8972, 8973, 8974):
            return "whetblades"

        # Quest
        if iid == 2090:
            return "deathroot"
        if iid == 8193:
            return "seedbed_curses"

        # Reforged (ERR-specific)
        if iid in (900000, 900010, 22000):
            return "items_and_changes"
        if iid in FORTUNE_IDS:
            return "fortunes"
        if iid in SEALED_CURIO_IDS:
            return "sealed_curios"

        # Equipment via goods. Reforged moves spirit ashes to 300000-399999;
        # the id list also covers the vanilla ones, which that range misses -
        # without it every summon on an unmodded game lands in "misc".
        if SPIRIT_ASH_MIN <= iid <= SPIRIT_ASH_MAX or iid in SPIRIT_ASH_IDS:
            return "spirits"
        if iid in INCANTATION_IDS:
            return "incantations"
        if iid in SORCERY_IDS:
            return "sorceries"
        if iid == 10030:
            return "memory_stones"
        if iid in PRAYERBOOK_IDS:
            return "prayerbooks"

        # Loot
        if iid == 8000:
            return "stonesword_keys"
        if "bell bearing" in low:
            return "merchant_bell_bearings" if "merchant" in low else "bell_bearings"
        if iid in SMITHING_LOW_IDS:
            return "smithing_stones_low"
        if iid in SMITHING_IDS:
            return "smithing_stones"
        if iid in SMITHING_RARE_IDS:
            return "smithing_stones_rare"
        if iid in GOLDEN_RUNE_LOW_IDS:
            return "golden_runes_low"
        if iid in GOLDEN_RUNE_IDS:
            return "golden_runes"
        if iid == RUNE_ARC_ID:
            return "rune_arcs"
        if iid == 10060:
            return "dragon_hearts"
        if 10900 <= iid <= 10908 or 10910 <= iid <= 10918:
            return "gloveworts"
        if iid in (10909, 10919):
            return "great_gloveworts"
        if iid in PATE_IDS:
            return "prattling_pates"
        if (iid in MP_FINGER_IDS) or "furlcalling finger remedy" in low:
            return "mp_fingers"

        # Sort-group driven loot (uses MFG's goods sort groups)
        sg = _sg(iid)
        if sg in (20, 61):
            return "consumables"
        if sg == 70:
            return "greases"
        if sg == 80:
            return "utilities"
        if sg == 10:
            return "stat_boosts"
        if sg == 50:
            return "throwables"
        if iid in CRAFTING_IDS:
            return "crafting_materials"
        if sg in (60, 81) and iid < 4000000 and iid != 2008000:
            return "reusables"

        # Catch-all: quest progression key items. Must be last for category 1.
        if not low.startswith("map:") and (
            iid in KEYITEM_IDS or iid in PROGRESSION_EXTRA or sg == 90
        ):
            return "progression"

        return "misc"

    if category == 2:
        if iid in AMMO_IDS:
            return "ammo"
        return "armaments"
    if category == 3:
        return "armour"
    if category == 4:
        return "talismans"
    if category == 5:
        return "ashes_of_war"

    return "misc"


# Category slug -> icon PNG basename (from MFG tools/map_categories.py).
CATEGORY_ICONS = {
    "graces": "grace.png",
    "rune_pieces": "rune_piece.png",
    "ember_pieces": "ember_piece.png",
    "world_maps": "map.png",
    "imp_statues": "imp_statue.png",
    "summoning_pools": "pool.png",
    "seedbed_curses": "curse.png",
    "progression": "quest.png",
    "deathroot": "death.png",
    "celestial_dew": "dew.png",
    "cookbooks": "cookbook.png",
    "crystal_tears": "crystal_tears.png",
    "imbued_sword_keys": "stone_key_2.png",
    "larval_tears": "larval.png",
    "lost_ashes": "lost_ash.png",
    "pots_n_perfumes": "pots_n_perfumes.png",
    "seeds_tears": "seed.png",
    "scadutree_fragments": "skadu.png",
    "whetblades": "whetblade.png",
    "great_runes": "great.png",
    "items_and_changes": "reforged.png",
    "fortunes": "fortune.png",
    "sealed_curios": "curio.png",
    "armaments": "weapon.png",
    "armour": "armor.png",
    "talismans": "talisman.png",
    "spirits": "spirit.png",
    "ashes_of_war": "ash.png",
    "incantations": "incantation.png",
    "sorceries": "sorceries.png",
    "memory_stones": "memory.png",
    "prayerbooks": "prayerbook.png",
    "gestures": "gesture.png",
    "stonesword_keys": "stone_key.png",
    "bell_bearings": "bell.png",
    "merchant_bell_bearings": "bell_m.png",
    "smithing_stones_rare": "smst_high.png",
    "golden_runes": "rune_high.png",
    "rune_arcs": "ark.png",
    "dragon_hearts": "dragon_heart.png",
    "stat_boosts": "shard.png",
    "prattling_pates": "pate.png",
    "reusables": "reusable.png",
    "paintings": "painting.png",
    "smithing_stones": "smst.png",
    "mp_fingers": "finger.png",
    "great_gloveworts": "glove_high.png",
    "interactables": "interactible.png",
    "ammo": "ammo.png",
    "smithing_stones_low": "smst_low.png",
    "golden_runes_low": "rune_low.png",
    "consumables": "consumables.png",
    "greases": "grease.png",
    "utilities": "utils.png",
    "throwables": "throw.png",
    "crafting_materials": "materials.png",
    "gloveworts": "glove.png",
    "material_nodes": "nodes.png",
    "stakes_of_marika": "marika.png",
    "spirit_springs": "jump.png",
    "spiritspring_hawks": "stormhawk.png",
    "bosses": "boss.png",
    "hostile_npc": "npc.png",
    "hero_tomb_statues": "statue.png",
    "misc": None,
}


def icon_for(category):
    """-> icon PNG basename for a category slug, or None."""
    return CATEGORY_ICONS.get(category)
