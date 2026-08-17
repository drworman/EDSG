"""Making commodity names match however they are written.

Elite writes the same commodity three different ways. A journal entry
for low temperature diamonds carries::

    "Type": "$lowtemperaturediamond_name;"
    "Type_Localised": "Low Temp. Diamonds"

and an organizer setting up a criterion types "Low Temperature Diamonds".
Folding case and stripping punctuation is not enough to reconcile those:
the internal name is singular and unabbreviated, the localised name is
plural and abbreviated, and the organizer's is plural and unabbreviated.
Three spellings, three different results, no matches at all — and a
criterion that silently scores zero.

:func:`canonical` reconciles them by working on words rather than on the
whole string: split on the separators that exist, expand Frontier's
abbreviations, fold plurals, then join. All three spellings above come
out as ``lowtemperaturediamond``.

This is deliberately mechanical rather than a lookup table. A table
covering every commodity would be out of date the next time Frontier
adds one, and would fail closed — silently scoring zero, which is the
thing being fixed. :data:`COMMODITIES` exists only to populate the
organizer's autocomplete, and nothing depends on it being complete.
"""

from __future__ import annotations

import re

#: Frontier's abbreviations, as they appear in localised names.
#: Expanded before comparison so "Low Temp. Diamonds" reconciles with
#: "$lowtemperaturediamond_name;".
ABBREVIATIONS = {
    "temp": "temperature",
    "equip": "equipment",
    "equipt": "equipment",
    "mat": "material",
    "mats": "materials",
    "min": "mineral",
    "sys": "system",
    "tech": "technology",
    "mfg": "manufacturing",
    "std": "standard",
    "adv": "advanced",
    "config": "configuration",
    "hyd": "hydrogen",
    "assy": "assembly",
}

#: Words that keep their trailing "s" — folding them would produce a
#: different commodity or plain nonsense.
NEVER_SINGULAR = {
    "gas",
    "biowaste",
    "goods",
    "arms",
    "narcotics",
    "textiles",
    "ceramics",
    "atmospherics",
    "hydrogen",
    "consumables",
    "electronics",
    "logistics",
    "plastics",
    "explosives",
    "diagnostics",
}

_SPLIT = re.compile(r"[^a-z0-9]+")


def _strip_decoration(value: str) -> str:
    """Remove Frontier's ``$name;`` wrapper and case-fold."""
    text = value.strip().lower()
    if text.startswith("$"):
        text = text[1:]
    if text.endswith(";"):
        text = text[:-1]
    for suffix in ("_name", "_localised"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text


def singular(word: str) -> str:
    """Fold a simple English plural.

    Conservative on purpose: only a trailing "s" is removed, never from a
    word ending "ss", never from anything short, and never from the words
    that mean something different in the singular.
    """
    if word in NEVER_SINGULAR or len(word) <= 3 or word.endswith("ss"):
        return word
    if word.endswith("ies") and len(word) > 4:
        return f"{word[:-3]}y"
    if word.endswith("s"):
        return word[:-1]
    return word


def words(value: str) -> list[str]:
    """Split a name into normalised, expanded, singular words."""
    text = _strip_decoration(value)
    parts = [part for part in _SPLIT.split(text) if part]
    return [singular(ABBREVIATIONS.get(part, part)) for part in parts]


def canonical(value: str) -> str:
    """Return one comparable form for any spelling of a commodity.

    ``$lowtemperaturediamond_name;``, ``Low Temp. Diamonds`` and
    ``Low Temperature Diamonds`` all return ``lowtemperaturediamond``.
    """
    joined = "".join(words(value))
    # An internal name arrives as one long word, so the expansions above
    # never fire on it. Folding the plural once more on the joined form
    # reconciles "lowtemperaturediamonds" with the singular internal name.
    return singular(joined)


def matches(value: str, pattern: str) -> bool:
    """Return whether a journal value matches an organizer's pattern.

    Exact once both are canonical, falling back to a substring match so
    partial names such as "diamond" still behave as a filter.
    """
    target = canonical(value)
    needle = canonical(pattern)
    if not target or not needle:
        return False
    return needle == target or needle in target


#: Names offered in the organizer's autocomplete. **Not exhaustive and
#: not authoritative** — matching does not consult it, so a commodity
#: missing here still scores correctly when typed. It exists to save
#: typing and to show the spelling Frontier uses.
COMMODITIES: tuple[str, ...] = (
    # Minerals and metals most often used in mining events
    "Alexandrite",
    "Aluminium",
    "Bauxite",
    "Benitoite",
    "Bertrandite",
    "Beryllium",
    "Bismuth",
    "Bromellite",
    "Coltan",
    "Cobalt",
    "Copper",
    "Cryolite",
    "Gallite",
    "Gallium",
    "Gold",
    "Goslarite",
    "Grandidierite",
    "Hafnium 178",
    "Indite",
    "Indium",
    "Jadeite",
    "Lanthanum",
    "Lepidolite",
    "Lithium",
    "Lithium Hydroxide",
    "Low Temperature Diamonds",
    "Methane Clathrate",
    "Methanol Monohydrate Crystals",
    "Moissanite",
    "Monazite",
    "Musgravite",
    "Osmium",
    "Painite",
    "Palladium",
    "Platinum",
    "Praseodymium",
    "Pyrophyllite",
    "Rhodplumsite",
    "Rutile",
    "Samarium",
    "Serendibite",
    "Silver",
    "Taaffeite",
    "Tantalum",
    "Thallium",
    "Thorium",
    "Titanium",
    "Tritium",
    "Uraninite",
    "Uranium",
    "Void Opals",
    "Water",
    # Chemicals and fuels
    "Explosives",
    "Hydrogen Fuel",
    "Hydrogen Peroxide",
    "Liquid Oxygen",
    "Mineral Oil",
    "Nerve Agents",
    "Pesticides",
    "Surface Stabilisers",
    "Synthetic Reagents",
    # Consumer items
    "Clothing",
    "Consumer Technology",
    "Domestic Appliances",
    "Evacuation Shelter",
    "Survival Equipment",
    # Foods
    "Algae",
    "Animal Meat",
    "Coffee",
    "Fish",
    "Food Cartridges",
    "Fruit and Vegetables",
    "Grain",
    "Synthetic Meat",
    "Tea",
    # Industrial materials
    "Ceramic Composites",
    "CMM Composite",
    "Insulating Membrane",
    "Meta-Alloys",
    "Micro-Weave Cooling Hoses",
    "Neofabric Insulation",
    "Polymers",
    "Semiconductors",
    "Superconductors",
    # Machinery
    "Building Fabricators",
    "Crop Harvesters",
    "Emergency Power Cells",
    "Energy Grid Assembly",
    "Exhaust Manifold",
    "Geological Equipment",
    "Heatsink Interlink",
    "HN Shock Mount",
    "Ion Distributor",
    "Magnetic Emitter Coil",
    "Marine Equipment",
    "Microbial Furnaces",
    "Mineral Extractors",
    "Modular Terminals",
    "Power Converter",
    "Power Generators",
    "Power Transfer Bus",
    "Radiation Baffle",
    "Reinforced Mounting Plate",
    "Skimmer Components",
    "Thermal Cooling Units",
    "Water Purifiers",
    # Medicines
    "Advanced Medicines",
    "Agronomic Treatment",
    "Basic Medicines",
    "Combat Stabilisers",
    "Performance Enhancers",
    "Progenitor Cells",
    # Salvage
    "Ancient Artefact",
    "Antimatter Containment Unit",
    "Antique Jewellery",
    "Damaged Escape Pod",
    "Occupied Escape Pod",
    "Personal Effects",
    "Political Prisoners",
    "Precious Gems",
    "Wreckage Components",
    # Technology
    "Advanced Catalysers",
    "Animal Monitors",
    "Aquaponic Systems",
    "Auto-Fabricators",
    "Bioreducing Lichen",
    "Computer Components",
    "Diagnostic Sensor",
    "Land Enrichment Systems",
    "Medical Diagnostic Equipment",
    "Micro Controllers",
    "Muon Imager",
    "Nanobreakers",
    "Resonating Separators",
    "Robotics",
    "Structural Regulators",
    "Telemetry Suite",
    # Textiles
    "Conductive Fabrics",
    "Leather",
    "Military Grade Fabrics",
    "Natural Fabrics",
    "Synthetic Fabrics",
    # Waste
    "Biowaste",
    "Chemical Waste",
    "Scrap",
    "Toxic Waste",
    # Weapons
    "Battle Weapons",
    "Landmines",
    "Non-Lethal Weapons",
    "Personal Weapons",
    "Reactive Armour",
)


__all__ = [
    "ABBREVIATIONS",
    "COMMODITIES",
    "NEVER_SINGULAR",
    "canonical",
    "matches",
    "singular",
    "words",
]
