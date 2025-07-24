"""Canonical product and alias metadata for HigherDOSE analysis modules.

This file is GENERATED once from docs/product-list.md then maintained manually.
It must contain *data only* (no heavy imports or runtime code) so that any
other module can safely `import higherdose.product_data` without side-effects.
"""

from __future__ import annotations
from typing import Dict, List

# ---------------------------------------------------------------------------
# Product summaries – not currently used by analysis but kept for reference
# ---------------------------------------------------------------------------
SUMMARIES: Dict[str, str] = {
    "Microcurrent Body Sculptor Ritual Set": "Handheld microcurrent device with red & near-infrared LEDs plus activator gel and magnesium spray to sculpt fascia, boost lymph flow, relieve muscles, and firm skin.",
    "Red Light Hat": "650 nm red-light cap boosts scalp circulation to strengthen follicles, reduce shedding, and encourage thicker hair with 10-minute daily use.",
    "Infrared Sauna Blanket": "Portable far-infrared blanket (up to ~175 °F) with crystal & charcoal layers for deep detox, calorie burn, stress relief, and post-sweat glow.",
    "Red Light Face Mask": "FDA-cleared mask combining red & near-infrared LEDs to stimulate collagen, calm redness, fight acne, and brighten skin in hands-free sessions.",
    "Red Light Neck Enhancer": "Flexible neck/décolletage panel delivering red/NIR light that firms skin, fades lines, and extends facial light-therapy benefits.",
    "Infrared PEMF Pro Mat": "Full-size mat layering far-infrared heat, PEMF, negative ions, and crystals to ease pain, speed recovery, and promote deep relaxation.",
    "Infrared PEMF Go Mat": "Travel-ready version of the Pro Mat offering Infrared + PEMF therapy in a compact foldable pad for on-the-go relief.",
    "Full Spectrum Infrared Sauna": "Clearlight wooden cabin with low-EMF heaters providing near, mid & far infrared plus chromotherapy and audio for spa-level detox.",
    # … (trimmed for brevity – include the rest as needed)
}

# ---------------------------------------------------------------------------
# Category membership – product → category string
# ---------------------------------------------------------------------------
PRODUCT_TO_CATEGORY: Dict[str, str] = {
    # Wellness Tech
    "Microcurrent Body Sculptor Ritual Set": "Wellness Tech",
    "Red Light Hat": "Wellness Tech",
    "Infrared Sauna Blanket": "Wellness Tech",
    "Red Light Face Mask": "Wellness Tech",
    "Red Light Neck Enhancer": "Wellness Tech",
    "Infrared PEMF Pro Mat": "Wellness Tech",
    "Infrared PEMF Go Mat": "Wellness Tech",
    "Full Spectrum Infrared Sauna": "Wellness Tech",

    # Bundle & Save
    "Sauna Blanket Starter Kit": "Bundle & Save",
    "PEMF Pro Mat Starter Kit": "Bundle & Save",
    "Red Light Starter Kit": "Bundle & Save",
    "Summer Body Recover & Sculpt": "Bundle & Save",
    "Summer Travel Glow Kit": "Bundle & Save",
    "Best Seller Bundle": "Bundle & Save",
    "Turn Me On Kit": "Bundle & Save",
    "PEMF Go Mat Starter Kit": "Bundle & Save",
    "Endorphin Kit": "Bundle & Save",
    "Oxytocin Kit": "Bundle & Save",
    "The Supermom Bundle": "Bundle & Save",
    "The Sweat it Out Bundle": "Bundle & Save",
    "After Bedtime Bundle": "Bundle & Save",

    # Accessories
    "Supercharge Copper Body Brush": "Accessories",
    "SweatBand": "Accessories",
    "EMF Blocking Fanny Pack": "Accessories",
    "Infrared Sauna Blanket Insert": "Accessories",
    "High Maintenance Cleaner": "Accessories",
    "DailyDOSE Time-Marked Glass Water Bottle": "Accessories",
    "Sauna Blanket Bag": "Accessories",
    "PEMF Mat Cover": "Accessories",
    "100% Organic Cotton Bath Robe": "Accessories",

    # Supplements
    "Detox Drops": "Supplements",
    "High-Dration Powder": "Supplements",
    "HighDration Kit": "Supplements",

    # Body Care
    "Transdermal Magnesium Spray": "Body Care",
    "Endorphin Oil": "Body Care",
    "Serotonin Soak Salt": "Body Care",
    "Light-Activated Glow Serum": "Body Care",
    "Oxytocin Oil": "Body Care",
    "Daily Dose Ritual": "Body Care",
    "Sculpting Activator Gel": "Body Care",

    # Gifting
    "eGift Card": "Gifting",
}

# ---------------------------------------------------------------------------
# Aliases – any lower-cased keyword / phrase → canonical product name
# ---------------------------------------------------------------------------
ALIASES: Dict[str, str] = {
    "sauna blanket": "Infrared Sauna Blanket",
    "sauna blanket starter kit": "Sauna Blanket Starter Kit",
    "pemf mat": "Infrared PEMF Pro Mat",
    "pemf pro mat": "Infrared PEMF Pro Mat",
    "pemf go mat": "Infrared PEMF Go Mat",
    "red light mask": "Red Light Face Mask",
    "red light face mask": "Red Light Face Mask",
    "red light hat": "Red Light Hat",
    "neck enhancer": "Red Light Neck Enhancer",
    "microcurrent body sculptor": "Microcurrent Body Sculptor Ritual Set",
    "body sculptor": "Microcurrent Body Sculptor Ritual Set",
    "body sculptor ritual set": "Microcurrent Body Sculptor Ritual Set",
    "sculptor": "Microcurrent Body Sculptor Ritual Set",
    "body sculpt": "Microcurrent Body Sculptor Ritual Set",
    # … (include remaining aliases)
}

# Convenience: longest-first list for greedy matching
ALIAS_SORTED: List[tuple[str, str]] = sorted(ALIASES.items(), key=lambda kv: -len(kv[0]))

__all__ = [
    "SUMMARIES",
    "PRODUCT_TO_CATEGORY",
    "ALIASES",
    "ALIAS_SORTED",
]
