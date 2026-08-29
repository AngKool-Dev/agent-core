#!/usr/bin/env python3
"""Generate 1000 progressively-ordered QuestBook quests (q0001..q1000).

Rules:
- Strict easiest-to-hardest ordering: target pools are tiered
  (early -> mid -> late -> mythic); selection interpolates inside the
  current tier with bounded jitter so neighbours differ but the curve
  only ever climbs.
- Amounts ramp per difficulty band and are capped for precious
  materials and boss mobs so nothing asks for 400 nether stars.
- Descriptions are composed from each quest's real objectives with
  rotating templates, correct plurals and articles.
"""
import os
import sys

# (first, last, difficulty, pool_key)
TIERS = [
    (1,    100,  "NORMAL",     "early"),
    (101,  400,  "HARD",       "mid"),
    (401,  949,  "SUPER_HARD", "late"),
    (950,  1000, "SUPER_HARD", "mythic"),
]

MOBS = {
    "early": ["ZOMBIE", "SKELETON", "SPIDER", "SLIME", "DROWNED", "HUSK",
              "STRAY", "PILLAGER", "ZOMBIFIED_PIGLIN", "WITCH"],
    "mid": ["ENDERMAN", "WITCH", "PHANTOM", "VINDICATOR", "EVOKER", "RAVAGER",
            "GUARDIAN", "BLAZE", "HOGLIN", "PIGLIN_BRUTE"],
    "late": ["GHAST", "WITHER_SKELETON", "PIGLIN_BRUTE", "RAVAGER", "EVOKER",
             "ELDER_GUARDIAN", "SHULKER", "BOGGED", "BREEZE", "WARDEN"],
    "mythic": ["WARDEN", "WITHER", "ENDER_DRAGON", "EVOKER", "RAVAGER",
               "ELDER_GUARDIAN"],
}

MOB_CAPS = {
    "ENDER_DRAGON": 4, "WITHER": 8, "WARDEN": 12, "ELDER_GUARDIAN": 30,
    "EVOKER": 40, "RAVAGER": 50, "PIGLIN_BRUTE": 60, "BREEZE": 60,
    "BOGGED": 90,
}

ITEMS = {
    "early": ["WHEAT", "WHEAT_SEEDS", "COAL", "RAW_COPPER", "RAW_IRON",
              "STRING", "BONE", "ROTTEN_FLESH", "GUNPOWDER", "COPPER_INGOT",
              "IRON_INGOT", "CALCITE", "TUFF"],
    "mid": ["IRON_INGOT", "GOLD_INGOT", "REDSTONE", "LAPIS_LAZULI",
            "AMETHYST_SHARD", "PRISMARINE_SHARD", "QUARTZ", "OBSIDIAN",
            "MAGMA_CREAM", "BLAZE_ROD", "DIAMOND", "RAW_GOLD"],
    "late": ["DIAMOND", "NETHERITE_SCRAP", "NETHERITE_INGOT", "ECHO_SHARD",
             "NAUTILUS_SHELL", "PHANTOM_MEMBRANE", "SHULKER_SHELL",
             "ENDER_PEARL", "ENDER_EYE", "GLOWSTONE_DUST"],
    "mythic": ["NETHERITE_INGOT", "NETHER_STAR", "SHULKER_SHELL",
               "ENDER_EYE"],
}

ITEM_CAPS = {
    "NETHER_STAR": 6, "ELYTRA": 2, "DRAGON_HEAD": 2, "TOTEM_OF_UNDYING": 8,
    "HEART_OF_THE_SEA": 8, "ENCHANTED_GOLDEN_APPLE": 4, "NETHERITE_INGOT": 32,
    "NETHERITE_SCRAP": 64, "ECHO_SHARD": 96, "SHULKER_SHELL": 48,
    "ENDER_EYE": 64, "ENDER_PEARL": 96, "NAUTILUS_SHELL": 96,
    "PHANTOM_MEMBRANE": 128,
}

BLOCKS = {
    "early": ["OAK_PLANKS", "COBBLESTONE", "STONE", "SANDSTONE",
              "SMOOTH_STONE"],
    "mid": ["DEEPSLATE", "BRICKS", "CUT_COPPER", "WAXED_COPPER_BLOCK",
            "POLISHED_DEEPSLATE", "QUARTZ_BLOCK"],
    "late": ["BLACKSTONE", "POLISHED_BASALT", "CRYING_OBSIDIAN", "PURPUR_BLOCK",
             "END_STONE_BRICKS", "DEEPSLATE_BRICKS", "OBSIDIAN"],
}

BIOMES = {
    "early": ["PLAINS", "FOREST", "BIRCH_FOREST", "BEACH", "TAIGA", "SWAMP"],
    "mid": ["DESERT", "SAVANNA", "JUNGLE", "BADLANDS", "CHERRY_GROVE",
            "MEADOW", "MANGROVE_SWAMP", "STONY_SHORE", "WINDSWEPT_HILLS",
            "GROVE"],
    "late": ["SNOWY_TAIGA", "SNOWY_SLOPES", "FROZEN_PEAKS", "JAGGED_PEAKS",
             "ICE_SPIKES", "DRIPSTONE_CAVES", "LUSH_CAVES", "OLD_GROWTH_TAIGA",
             "BAMBOO_JUNGLE", "ERODED_BADLANDS", "MUSHROOM_FIELDS",
             "DEEP_DARK"],
}

STRUCTS = {
    # Early targets must be surface-visible or cave-reachable on foot.
    # No buried/ocean/rare-spawn structures in the early band.
    "early": ["village", "ruined_portal", "pillager_outpost", "mineshaft"],
    "mid": ["desert_pyramid", "jungle_pyramid", "monument", "mansion",
            "stronghold", "trial_chambers", "shipwreck", "ocean_ruin",
            "igloo", "swamp_hut"],
    "late": ["nether_fortress", "bastion_remnant", "ancient_city", "end_city"],
}

RARE = ["ELYTRA", "NETHER_STAR", "NETHERITE_INGOT", "TOTEM_OF_UNDYING",
        "HEART_OF_THE_SEA", "ECHO_SHARD", "DRAGON_HEAD", "ENCHANTED_GOLDEN_APPLE"]

TYPES = ["COLLECTION", "EXPLORATION", "COMBAT", "CONSTRUCTION"]

THEMES = ["Ember", "Frost", "Verdant", "Obsidian", "Gilded", "Storm",
          "Abyssal", "Crimson", "Hollow", "Radiant", "Shattered", "Eternal",
          "Ashen", "Torrent", "Mirage", "Iron", "Void", "Solar", "Lunar",
          "Thorn"]

ROLE = {
    "COMBAT": ["Vigil", "Hunt", "Reckoning", "Crusade"],
    "COLLECTION": ["Harvest", "Tribute", "Provision", "Ledger"],
    "EXPLORATION": ["Expedition", "Horizon", "Pilgrimage", "Compass"],
    "CONSTRUCTION": ["Foundation", "Masonry", "Edifice", "Cornerstone"],
}

DESC_COMBAT = [
    "{mob_pl} have been pushing past the borders after dark. Thin their ranks by {amt} before the trails go cold",
    "Scouts report {mob_pl} denning too close to the roads. Cull {amt} and the caravans will breathe easier",
    "There is a price on {mob_pl} this season. Collect on {amt} of them; nobody asks how",
    "Every {mob_s} taken is a traveller spared. Make it {amt}, and make it permanent",
    "The watchtower logs name {mob_pl} as this month's threat. Answer with {amt} confirmed kills",
]

DESC_COMBAT_MYTHIC = [
    "The {mob_s} waits where light forgets to reach. End {amt} of the breed and let the deep stay silent",
    "Prophecy names the {mob_s} as a wall between you and the last pages. Bring {amt} down",
    "Old maps mark its ground with a single word: run. Prove them wrong {amt} times over",
]

DESC_COLLECTION = [
    "{item_l} never sits idle in capable hands. Deliver {amt} and the ledger stays balanced",
    "Stores run thin and patience thinner. {amt} {item_l}, weighed honest, closes this entry",
    "Someone upstream wants {item_l} by the crate. See that {amt} reach the counting table",
    "The smiths trade favours for {item_l}. {amt} units buys goodwill and coin alike",
    "Quartermasters have shortlisted {item_l}. Fulfil {amt} before the season turns",
]

DESC_EXPLORE_BIOME = [
    "Cartographers pay for certainty. Set eyes on the {place_t} and return to draw it true",
    "A survey team went missing heading for the {place_t}. Walk it, mark it, come back",
    "Trade routes bend around the {place_t} for want of a map. Be the one who fixes that",
    "They say the {place_t} hides more than wind and stone. Confirm it with your own feet",
]

DESC_EXPLORE_STRUCT = [
    "An expedition flag waits at the nearest {place_t}. Reach it and plant your claim",
    "Old records mention {art} {place_t} within reach. Find it; the guild handles the rest",
    "Treasure maps rot faster than rumours. Track down {art} {place_t} yourself",
    "The {place_t} has swallowed better adventurers than most. Locate it and prove the tales wrong",
]

DESC_CONSTRUCTION = [
    "Foundations outlive their founders. Set {amt} {block_l} where the old work has failed",
    "The frontier grows one wall at a time. Lay {amt} {block_l} and be part of it",
    "A mason is measured in placed stone. Contribute {amt} {block_l} to something lasting",
    "Blueprints call for {amt} {block_l}. The rest is sweat and stubbornness",
]

FLAVOR = {
    "NORMAL": [
        "Small steps still count on this road",
        "Every legend starts with errands like this one",
        "Do it well; someone is always watching the newcomers",
        "Steady hands today, steady name tomorrow",
    ],
    "HARD": [
        "The road steepens; so do the rewards",
        "By now, quitting would cost more than continuing",
        "Names that matter are earned at this depth of the book",
        "Careful - the world pushes back harder the further you go",
    ],
    "SUPER_HARD": [
        "Few pages turn past this point. Fewer still turn back",
        "The book keeps score, and it is watching closely now",
        "What waits ahead has ended better adventurers than most",
        "This is where the story stops being kind",
    ],
}

MILESTONE = [
    "A hundred-page marker in a very long book",
    "Half legend, half paperwork - such is progress",
    "The ranks whisper your name a little louder today",
]

_SEEN = set()


def tier_for(i):
    for first, last, diff, pool in TIERS:
        if first <= i <= last:
            return first, last, diff, pool
    raise ValueError(i)


def pl(name):
    irregular = {"DROWNED": "Drowned", "ENDERMAN": "Endermen"}
    if name.upper() in irregular:
        return irregular[name.upper()]
    words = name.split()
    w = words[-1]
    if w.endswith(("s", "x", "z", "ch", "sh")):
        w += "es"
    elif w.endswith("y") and len(w) > 1 and w[-2] not in "aeiou":
        w = w[:-1] + "ies"
    else:
        w += "s"
    return " ".join(words[:-1] + [w])


def art(phrase):
    if phrase.lower().endswith("ruins"):
        return ""
    return "an" if phrase[0].lower() in "aeiou" else "a"


def cap_first(s):
    return s[:1].upper() + s[1:]


def pick(table, i, n):
    _, _, _, tier = tier_for(i)
    pool = table.get(tier) or table["late"]
    first, last, _, _ = tier_for(i)
    span = max(1, last - first)
    u = min(1.0, (i - first) / span)
    base = int(u * len(pool) * 0.999)
    lo = max(0, base - 2)
    hi = min(len(pool) - 1, base + 2)
    idx = lo + (i * 7 + n * 13) % (hi - lo + 1)
    return pool[idx], tier


def ramp_amount(i, lo, hi):
    first, last, _, _ = tier_for(i)
    span_band = max(1, last - first)
    u_band = min(1.0, (i - first) / span_band)
    u_global = (i - 1) / 999.0
    u = max(u_band, u_global)
    return int(lo + (hi - lo) * u)


def pick_index(pool_len, i, n):
    _, last, _, _ = tier_for(i)
    return (i * 7 + n * 13) % pool_len


def pick_used(table, i, n, used):
    """Pick a tier-appropriate member, skipping already-used ones."""
    _, _, _, tier = tier_for(i)
    pool = table.get(tier) or table["late"]
    start = pick_index(len(pool), i, n)
    for offset in range(len(pool)):
        cand = pool[(start + offset) % len(pool)]
        if cand.lower() not in used:
            return cand, tier
    return pool[start], tier


def objective(type_name, i, n, used):
    """Return (yaml_lines, subject_id, display_amount, kind)."""
    if type_name == "COMBAT":
        mob, tier = pick_used(MOBS, i, n, used)
        amt = ramp_amount(i, 4, 140) + n * 2
        amt = min(amt, MOB_CAPS.get(mob, amt))
        if tier == "mythic":
            amt = max(1, min(amt, 4))
        text = f"Slay {amt} {pl(mob.title())}"
        return (f'  - description: "{text}"\n'
                f'    type: KILL_MOB\n    target: {mob}\n    amount: {amt}\n',
                mob, amt, "")
    if type_name == "COLLECTION":
        item, _ = pick_used(ITEMS, i, n, used)
        amt = ramp_amount(i, 6, 320) + n * 4
        amt = min(amt, ITEM_CAPS.get(item, amt))
        text = f"Collect {amt} {item.replace('_', ' ').lower()}"
        return (f'  - description: "{text}"\n'
                f'    type: COLLECT_ITEM\n    target: {item}\n    amount: {amt}\n',
                item, amt, "")
    if type_name == "EXPLORATION":
        if n % 2 == 0 or i <= 10:  # first ten quests never demand structures
            b, _ = pick_used(BIOMES, i, n // 2, used)
            text = f"Travel to the {b.replace('_', ' ').title()} biome"
            return (f'  - description: "{text}"\n'
                    f'    type: VISIT_BIOME\n    target: {b}\n    amount: 1\n',
                    b.title(), 1, "BIOME")
        st, _ = pick_used(STRUCTS, i, n // 2, used)
        disp = st.replace("_", " ")
        text = f"Locate {art(disp)} {disp}".replace("  ", " ")
        return (f'  - description: "{text}"\n'
                f'    type: FIND_STRUCTURE\n    target: {st}\n    amount: 1\n',
                disp, 1, "STRUCT")
    bl, _ = pick_used(BLOCKS, i, n, used)
    amt = ramp_amount(i, 8, 300) + n * 3
    text = f"Place {amt} {bl.replace('_', ' ').lower()}"
    return (f'  - description: "{text}"\n'
            f'    type: PLACE_BLOCK\n    target: {bl}\n    amount: {amt}\n',
            bl, amt, "")


def compose_description(type_name, i, diff, subjects, amounts, seen,
                        explore_kind=""):
    parts = []
    if i == 1000:
        parts.append("The last page. The Dragon knows your name now, and it is afraid")
    elif i >= 950:
        parts.append("The End stirs beneath the void. This is a summons, not a suggestion")
    elif i % 100 == 0:
        parts.append(MILESTONE[(i // 100 - 1) % len(MILESTONE)])
    elif i == 1:
        parts.append("Every long road opens with a single honest task")

    _, _, _, tier = tier_for(i)
    if type_name == "COMBAT":
        tmpl_set = DESC_COMBAT_MYTHIC if tier == "mythic" else DESC_COMBAT
        main = tmpl_set[(i // 2) % len(tmpl_set)].format(
            mob_pl=pl(subjects[0].title()), mob_s=subjects[0].title(),
            amt=amounts[0])
    elif type_name == "COLLECTION":
        main = DESC_COLLECTION[(i // 2) % len(DESC_COLLECTION)].format(
            item_l=cap_first(subjects[0].replace("_", " ").lower()),
            amt=amounts[0])
    elif type_name == "CONSTRUCTION":
        main = DESC_CONSTRUCTION[(i // 2) % len(DESC_CONSTRUCTION)].format(
            block_l=subjects[0].replace("_", " ").lower(), amt=amounts[0])
    else:
        is_struct = explore_kind == "STRUCT"
        table = DESC_EXPLORE_STRUCT if is_struct else DESC_EXPLORE_BIOME
        disp = subjects[0].replace("_", " ").title()
        main = table[(i // 2) % len(table)].format(place_t=disp,
                                                   art=art(disp))
    parts.append(main)

    if i < 950:
        parts.append(FLAVOR[diff][(i // 11) % len(FLAVOR[diff])])

    cleaned = [p.strip().rstrip(".") for p in parts if p and p.strip()]
    text = ". ".join(cleaned)
    while ".." in text:
        text = text.replace("..", ".")
    closers = [
        "The book files this one carefully",
        "Few have signed this page; fewer still twice",
        "The ink here is darker than usual",
        "A marginal note reads: bring help",
        "The paper smells faintly of ozone",
        "Someone crossed out a name at the bottom",
        "The spine creaks as if the book itself hesitates",
        "This entry is written in a hurried hand",
    ]
    suffix = (i * 13) % len(closers)
    while text in seen:
        text = f"{text}. {closers[suffix]}"
        suffix = (suffix + 1) % len(closers)
    seen.add(text)
    return text


def gen(i):
    tid = f"q{i:04d}"
    req = f"q{i - 1:04d}" if i > 1 else None
    first, last, diff, _ = tier_for(i)
    tname = TYPES[i % 4]
    global _SEEN

    n_obj = {"NORMAL": 2, "HARD": 3, "SUPER_HARD": 4}[diff]
    theme = THEMES[(i // 17) % len(THEMES)]
    role = ROLE[tname][(i // 5) % len(ROLE[tname])]
    title = f"{theme} {role} {i:03d}"
    obj_lines = []
    subjects = []
    amounts = []
    kinds = []
    used = set()
    for n in range(n_obj):
        line, subj, amt, kind = objective(tname, i, n, used)
        used.add(subj.lower())
        obj_lines.append(line.strip("\n"))
        subjects.append(subj)
        amounts.append(amt)
        kinds.append(kind)

    description = compose_description(tname, i, diff, subjects, amounts,
                                      _SEEN, kinds[0])

    exp = int(25 * i ** 1.18) + i
    money = int(15 * i ** 1.35)
    req_level = 1 + (i - 1) // 50

    lines = [f"id: {tid}",
             f'title: "{title}"',
             f'description: "{description}"',
             f"type: {tname}",
             f"required_level: {req_level}",
             f"repeatable: false",
             f"difficulty: {diff}"]
    if req:
        lines.append(f"required_quest: {req}")
    if i >= 951:
        lines.append("requires_dragon_killed: true")
    lines.append("objectives:")
    lines.extend(obj_lines)
    lines.append("rewards:")
    it1, _ = pick(ITEMS, i, 1)
    it2, _ = pick(ITEMS, i, 4)
    bonus = min(64, 2 + i // 60)
    lines.append("  items:")
    lines.append(f"    {it1}: {bonus}")
    lines.append(f"    {it2}: {max(1, bonus // 2)}")
    lines.append(f"  experience: {exp}")
    lines.append(f"  money: {money}")
    if diff == "SUPER_HARD" and i >= 600 and i % 3 == 0:
        r = RARE[(i // 3) % len(RARE)]
        lines.append("  rare_items:")
        lines.append(f"    - material: {r}")
        lines.append("      amount: 1")
        lines.append(f"      chance: {[2, 5, 10][(i // 3) % 3]}")
    return "\n".join(lines) + "\n"


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        if f.endswith(".yml") and (f.startswith("q") or f.startswith("demo_")):
            os.remove(os.path.join(out, f))
    for i in range(1, 1001):
        with open(os.path.join(out, f"q{i:04d}.yml"), "w") as fh:
            fh.write(gen(i))
    print(f"Generated 1000 quests in {out}")


if __name__ == "__main__":
    main()
