"""
BaZi (Four Pillars of Destiny) computation engine.

Handles:
- Gregorian to BaZi pillar conversion (with LMT correction)
- Hidden stem extraction
- Ten Gods relationship mapping  
- Branch interaction detection (clashes, combinations, harms, etc.)
- Luck Pillar computation
- Element distribution analysis
- Annual/monthly pillar interaction with natal chart

Design principle: This module COMPUTES and FLAGS. It does not interpret.
Interpretation is the LLM's job, guided by the skill file.
"""

from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import swisseph as swe


# ============================================================
# FUNDAMENTAL DATA STRUCTURES
# ============================================================

class Polarity(Enum):
    YANG = "yang"
    YIN = "yin"


class Element(Enum):
    WOOD = "wood"
    FIRE = "fire"
    EARTH = "earth"
    METAL = "metal"
    WATER = "water"


@dataclass
class HeavenlyStem:
    chinese: str
    pinyin: str
    element: Element
    polarity: Polarity
    index: int  # 0-9 in the cycle

    def __str__(self):
        return f"{self.pinyin} ({self.polarity.value} {self.element.value})"


@dataclass
class EarthlyBranch:
    chinese: str
    pinyin: str
    animal: str
    element: Element  # primary/season element
    polarity: Polarity
    index: int  # 0-11 in the cycle
    hidden_stems: list[str]  # pinyin names of hidden stems [main_qi, middle_qi, residual_qi]

    def __str__(self):
        return f"{self.pinyin} ({self.animal})"


@dataclass
class Pillar:
    stem: HeavenlyStem
    branch: EarthlyBranch
    position: str  # "year", "month", "day", "hour"

    def __str__(self):
        return f"{self.stem.pinyin} {self.branch.pinyin} ({self.stem.polarity.value} {self.stem.element.value} {self.branch.animal})"
    
    def to_dict(self):
        return {
            "position": self.position,
            "stem": {
                "chinese": self.stem.chinese,
                "pinyin": self.stem.pinyin,
                "element": self.stem.element.value,
                "polarity": self.stem.polarity.value,
            },
            "branch": {
                "chinese": self.branch.chinese,
                "pinyin": self.branch.pinyin,
                "animal": self.branch.animal,
                "element": self.branch.element.value,
                "polarity": self.branch.polarity.value,
                "hidden_stems": self.branch.hidden_stems,
            },
            "combined": f"{self.stem.pinyin} {self.branch.pinyin}",
            "description": str(self),
        }


# ============================================================
# STEM AND BRANCH DEFINITIONS
# ============================================================

HEAVENLY_STEMS = [
    HeavenlyStem("甲", "Jia", Element.WOOD, Polarity.YANG, 0),
    HeavenlyStem("乙", "Yi", Element.WOOD, Polarity.YIN, 1),
    HeavenlyStem("丙", "Bing", Element.FIRE, Polarity.YANG, 2),
    HeavenlyStem("丁", "Ding", Element.FIRE, Polarity.YIN, 3),
    HeavenlyStem("戊", "Wu", Element.EARTH, Polarity.YANG, 4),
    HeavenlyStem("己", "Ji", Element.EARTH, Polarity.YIN, 5),
    HeavenlyStem("庚", "Geng", Element.METAL, Polarity.YANG, 6),
    HeavenlyStem("辛", "Xin", Element.METAL, Polarity.YIN, 7),
    HeavenlyStem("壬", "Ren", Element.WATER, Polarity.YANG, 8),
    HeavenlyStem("癸", "Gui", Element.WATER, Polarity.YIN, 9),
]

EARTHLY_BRANCHES = [
    EarthlyBranch("子", "Zi", "Rat", Element.WATER, Polarity.YANG, 0,
                  ["Gui"]),  # main: Gui Water
    EarthlyBranch("丑", "Chou", "Ox", Element.EARTH, Polarity.YIN, 1,
                  ["Ji", "Gui", "Xin"]),  # main: Ji Earth, mid: Gui Water, res: Xin Metal
    EarthlyBranch("寅", "Yin", "Tiger", Element.WOOD, Polarity.YANG, 2,
                  ["Jia", "Bing", "Wu"]),  # main: Jia Wood, mid: Bing Fire, res: Wu Earth
    EarthlyBranch("卯", "Mao", "Rabbit", Element.WOOD, Polarity.YIN, 3,
                  ["Yi"]),  # main: Yi Wood
    EarthlyBranch("辰", "Chen", "Dragon", Element.EARTH, Polarity.YANG, 4,
                  ["Wu", "Yi", "Gui"]),  # main: Wu Earth, mid: Yi Wood, res: Gui Water
    EarthlyBranch("巳", "Si", "Snake", Element.FIRE, Polarity.YIN, 5,
                  ["Bing", "Wu", "Geng"]),  # main: Bing Fire, mid: Wu Earth, res: Geng Metal
    EarthlyBranch("午", "Wu", "Horse", Element.FIRE, Polarity.YANG, 6,
                  ["Ding", "Ji"]),  # main: Ding Fire, mid: Ji Earth
    EarthlyBranch("未", "Wei", "Goat", Element.EARTH, Polarity.YIN, 7,
                  ["Ji", "Ding", "Yi"]),  # main: Ji Earth, mid: Ding Fire, res: Yi Wood
    EarthlyBranch("申", "Shen", "Monkey", Element.METAL, Polarity.YANG, 8,
                  ["Geng", "Ren", "Wu"]),  # main: Geng Metal, mid: Ren Water, res: Wu Earth
    EarthlyBranch("酉", "You", "Rooster", Element.METAL, Polarity.YIN, 9,
                  ["Xin"]),  # main: Xin Metal
    EarthlyBranch("戌", "Xu", "Dog", Element.EARTH, Polarity.YANG, 10,
                  ["Wu", "Xin", "Ding"]),  # main: Wu Earth, mid: Xin Metal, res: Ding Fire
    EarthlyBranch("亥", "Hai", "Pig", Element.WATER, Polarity.YIN, 11,
                  ["Ren", "Jia"]),  # main: Ren Water, mid: Jia Wood
]

# Lookup helpers
STEM_BY_PINYIN = {s.pinyin: s for s in HEAVENLY_STEMS}
BRANCH_BY_PINYIN = {b.pinyin: b for b in EARTHLY_BRANCHES}
BRANCH_BY_ANIMAL = {b.animal: b for b in EARTHLY_BRANCHES}


# ============================================================
# PILLAR COMPUTATION
# ============================================================

def year_pillar(year: int, month: int, day: int, li_chun_month: int = 2, li_chun_day: int = 4) -> Pillar:
    """
    Compute the Year Pillar.
    
    The BaZi year starts at Li Chun (Start of Spring), usually Feb 3-5.
    If born before Li Chun, use previous year's pillar.
    
    Args:
        year: Gregorian year
        month, day: birth month and day
        li_chun_month, li_chun_day: Li Chun date for that year
    """
    # Adjust year if before Li Chun
    effective_year = year
    if month < li_chun_month or (month == li_chun_month and day < li_chun_day):
        effective_year -= 1
    
    # Stem: (year - 4) % 10 gives index into heavenly stems
    # (Year 4 CE was Jia Zi, the start of the cycle)
    stem_index = (effective_year - 4) % 10
    branch_index = (effective_year - 4) % 12
    
    return Pillar(
        stem=HEAVENLY_STEMS[stem_index],
        branch=EARTHLY_BRANCHES[branch_index],
        position="year"
    )


def month_pillar(year_stem_index: int, month_branch_index: int) -> Pillar:
    """
    Compute the Month Pillar using the Five Tigers Escape (Wu Hu Dun) formula.
    
    The month branch is determined by solar terms.
    The month stem is derived from the year stem.
    
    Five Tigers Escape rule:
    - Year stem Jia/Ji → month 1 stem starts at Bing
    - Year stem Yi/Geng → month 1 stem starts at Wu  
    - Year stem Bing/Xin → month 1 stem starts at Geng
    - Year stem Ding/Ren → month 1 stem starts at Ren
    - Year stem Wu/Gui → month 1 stem starts at Jia
    
    Args:
        year_stem_index: index of the year's heavenly stem (0-9)
        month_branch_index: index of the month's earthly branch (0-11)
            Note: month 1 (Tiger/Yin) has branch_index 2
    """
    # Five Tigers Escape starting stems for month 1 (Tiger)
    tiger_start_stems = {
        0: 2, 5: 2,   # Jia/Ji year → Bing Tiger
        1: 4, 6: 4,   # Yi/Geng year → Wu Tiger
        2: 6, 7: 6,   # Bing/Xin year → Geng Tiger
        3: 8, 8: 8,   # Ding/Ren year → Ren Tiger
        4: 0, 9: 0,   # Wu/Gui year → Jia Tiger
    }
    
    start_stem = tiger_start_stems[year_stem_index]
    
    # Calculate how many months from Tiger (index 2) to the target month
    months_from_tiger = (month_branch_index - 2) % 12
    
    stem_index = (start_stem + months_from_tiger) % 10
    
    return Pillar(
        stem=HEAVENLY_STEMS[stem_index],
        branch=EARTHLY_BRANCHES[month_branch_index],
        position="month"
    )


def day_pillar(date: datetime) -> Pillar:
    """
    Compute the Day Pillar using Julian Day Number.

    The sexagenary 60-day cycle maps to JDN with a fixed offset.
    Formula derived from Reingold & Dershowitz, *Calendrical Calculations*,
    and verified against published day pillars (e.g., 1990-03-15 = Ji You,
    1986-06-19 = Jia Zi).
    """
    # JDN offset: (int(jdn) + 20) % 60 gives the sexagenary index
    # where stem = index % 10, branch = index % 12
    _JDN_SEXAGENARY_OFFSET = 20

    jdn = int(swe.julday(date.year, date.month, date.day, 0))
    sexagenary = (jdn + _JDN_SEXAGENARY_OFFSET) % 60
    stem_index = sexagenary % 10
    branch_index = sexagenary % 12

    return Pillar(
        stem=HEAVENLY_STEMS[stem_index],
        branch=EARTHLY_BRANCHES[branch_index],
        position="day"
    )


def hour_pillar(day_stem_index: int, hour: int) -> Pillar:
    """
    Compute the Hour Pillar using Five Rats Escape (Wu Shu Dun) formula.
    
    Chinese hours (shi chen) are 2-hour blocks:
    23:00-00:59 = Zi (Rat)      = branch 0
    01:00-02:59 = Chou (Ox)     = branch 1
    03:00-04:59 = Yin (Tiger)   = branch 2
    05:00-06:59 = Mao (Rabbit)  = branch 3
    07:00-08:59 = Chen (Dragon) = branch 4
    09:00-10:59 = Si (Snake)    = branch 5
    11:00-12:59 = Wu (Horse)    = branch 6
    13:00-14:59 = Wei (Goat)    = branch 7
    15:00-16:59 = Shen (Monkey) = branch 8
    17:00-18:59 = You (Rooster) = branch 9
    19:00-20:59 = Xu (Dog)      = branch 10
    21:00-22:59 = Hai (Pig)     = branch 11
    
    IMPORTANT: Use LMT-corrected hour, not clock time.
    
    Args:
        day_stem_index: index of the day's heavenly stem (0-9)
        hour: hour in 24h format (LMT corrected)
    """
    # Map hour to branch index
    if hour == 23 or hour == 0:
        branch_index = 0  # Zi
    else:
        branch_index = ((hour + 1) // 2) % 12
    
    # Five Rats Escape: starting stem for Zi hour based on day stem
    zi_start_stems = {
        0: 0, 5: 0,   # Jia/Ji day → Jia Zi hour
        1: 2, 6: 2,   # Yi/Geng day → Bing Zi hour
        2: 4, 7: 4,   # Bing/Xin day → Wu Zi hour
        3: 6, 8: 6,   # Ding/Ren day → Geng Zi hour
        4: 8, 9: 8,   # Wu/Gui day → Ren Zi hour
    }
    
    start_stem = zi_start_stems[day_stem_index]
    stem_index = (start_stem + branch_index) % 10
    
    return Pillar(
        stem=HEAVENLY_STEMS[stem_index],
        branch=EARTHLY_BRANCHES[branch_index],
        position="hour"
    )


# ============================================================
# TEN GODS (十神) RELATIONSHIP MAPPING
# ============================================================

# The Ten Gods describe the relationship between any element and the Day Master.
# They are determined by element relationship + polarity match.

TEN_GODS = {
    # (relationship, same_polarity): god_name
    ("same", True): "Companion (比肩 Bi Jian)",          # Same element, same polarity
    ("same", False): "Rob Wealth (劫财 Jie Cai)",        # Same element, diff polarity
    ("produces_me", True): "Indirect Resource (偏印 Pian Yin)",  # Produces DM, same polarity
    ("produces_me", False): "Direct Resource (正印 Zheng Yin)",   # Produces DM, diff polarity
    ("i_produce", True): "Eating God (食神 Shi Shen)",    # DM produces it, same polarity
    ("i_produce", False): "Hurting Officer (伤官 Shang Guan)",  # DM produces it, diff polarity
    ("i_control", True): "Indirect Wealth (偏财 Pian Cai)",  # DM controls it, same polarity
    ("i_control", False): "Direct Wealth (正财 Zheng Cai)",   # DM controls it, diff polarity
    ("controls_me", True): "7 Killings (七杀 Qi Sha)",    # Controls DM, same polarity
    ("controls_me", False): "Direct Officer (正官 Zheng Guan)",  # Controls DM, diff polarity
}

# Production cycle: Wood → Fire → Earth → Metal → Water → Wood
PRODUCTION_CYCLE = {
    Element.WOOD: Element.FIRE,
    Element.FIRE: Element.EARTH,
    Element.EARTH: Element.METAL,
    Element.METAL: Element.WATER,
    Element.WATER: Element.WOOD,
}

# Control cycle: Wood → Earth → Water → Fire → Metal → Wood
CONTROL_CYCLE = {
    Element.WOOD: Element.EARTH,
    Element.EARTH: Element.WATER,
    Element.WATER: Element.FIRE,
    Element.FIRE: Element.METAL,
    Element.METAL: Element.WOOD,
}


def element_relationship(day_master_element: Element, other_element: Element) -> str:
    """Determine the elemental relationship from DM's perspective."""
    if day_master_element == other_element:
        return "same"
    elif PRODUCTION_CYCLE[other_element] == day_master_element:
        return "produces_me"  # other produces DM
    elif PRODUCTION_CYCLE[day_master_element] == other_element:
        return "i_produce"  # DM produces other
    elif CONTROL_CYCLE[day_master_element] == other_element:
        return "i_control"  # DM controls other
    elif CONTROL_CYCLE[other_element] == day_master_element:
        return "controls_me"  # other controls DM
    else:
        raise ValueError(f"No valid relationship between {day_master_element} and {other_element}")


def ten_god(day_master: HeavenlyStem, other: HeavenlyStem) -> str:
    """
    Determine the Ten God relationship between the Day Master and another stem.
    
    Args:
        day_master: the Day Master stem
        other: the stem being evaluated
    
    Returns:
        String name of the Ten God relationship
    """
    relationship = element_relationship(day_master.element, other.element)
    same_polarity = (day_master.polarity == other.polarity)
    return TEN_GODS[(relationship, same_polarity)]


def map_ten_gods(day_master: HeavenlyStem, pillars: list[Pillar]) -> list[dict]:
    """
    Map Ten Gods for all visible stems in the chart.
    Also maps hidden stems within each branch.
    
    Returns list of dicts with position, stem, ten_god, and hidden_stem_gods.
    """
    results = []
    for pillar in pillars:
        # Visible stem
        god = ten_god(day_master, pillar.stem) if pillar.stem != day_master else "Self (Day Master)"
        
        # Hidden stems
        hidden_gods = []
        for hidden_pinyin in pillar.branch.hidden_stems:
            hidden_stem = STEM_BY_PINYIN[hidden_pinyin]
            h_god = ten_god(day_master, hidden_stem)
            hidden_gods.append({
                "stem": hidden_pinyin,
                "element": hidden_stem.element.value,
                "polarity": hidden_stem.polarity.value,
                "ten_god": h_god,
            })
        
        results.append({
            "position": pillar.position,
            "stem": pillar.stem.pinyin,
            "ten_god": god,
            "branch": pillar.branch.pinyin,
            "branch_animal": pillar.branch.animal,
            "hidden_stem_gods": hidden_gods,
        })
    
    return results


# ============================================================
# BRANCH INTERACTIONS
# ============================================================

# Six Combinations (六合) - 1:1 pairings that can transform
SIX_COMBINATIONS = {
    # (branch1_index, branch2_index): resulting_element_if_transforms
    (0, 1): Element.EARTH,    # Zi-Chou → Earth
    (2, 11): Element.WOOD,    # Yin-Hai → Wood
    (3, 10): Element.FIRE,    # Mao-Xu → Fire
    (4, 9): Element.METAL,    # Chen-You → Metal
    (5, 8): Element.WATER,    # Si-Shen → Water
    (6, 7): Element.FIRE,     # Wu-Wei → Fire (or Earth, debated)
}

# Three Harmony Combinations (三合) - groups of three
THREE_HARMONY = {
    # (branch1, branch2, branch3): resulting_element
    (2, 6, 10): Element.FIRE,     # Yin-Wu-Xu → Fire frame
    (8, 0, 4): Element.WATER,     # Shen-Zi-Chen → Water frame
    (5, 9, 1): Element.METAL,     # Si-You-Chou → Metal frame
    (11, 3, 7): Element.WOOD,     # Hai-Mao-Wei → Wood frame
}

# Six Clashes (六冲)
SIX_CLASHES = [
    (0, 6),   # Zi-Wu (Rat-Horse)
    (1, 7),   # Chou-Wei (Ox-Goat)
    (2, 8),   # Yin-Shen (Tiger-Monkey)
    (3, 9),   # Mao-You (Rabbit-Rooster)
    (4, 10),  # Chen-Xu (Dragon-Dog)
    (5, 11),  # Si-Hai (Snake-Pig)
]

# Six Harms (六害)
SIX_HARMS = [
    (0, 7),   # Zi-Wei (Rat-Goat)
    (1, 6),   # Chou-Wu (Ox-Horse)
    (2, 5),   # Yin-Si (Tiger-Snake)
    (3, 4),   # Mao-Chen (Rabbit-Dragon)
    (8, 11),  # Shen-Hai (Monkey-Pig)
    (9, 10),  # You-Xu (Rooster-Dog)
]

# Destructions (相破)
DESTRUCTIONS = [
    (0, 9),   # Zi-You
    (1, 4),   # Chou-Chen
    (2, 11),  # Yin-Hai
    (3, 6),   # Mao-Wu
    (5, 8),   # Si-Shen
    (7, 10),  # Wei-Xu
]

# Self-Punishments and Triple Punishments (刑)
# Ungrateful punishment: Yin-Si-Shen
# Uncivilized punishment: Chou-Xu-Wei  
# Rude punishment: Zi-Mao
# Self-punishment: Chen-Chen, Wu-Wu, You-You, Hai-Hai
PUNISHMENTS = {
    "ungrateful": [2, 5, 8],      # Yin-Si-Shen
    "uncivilized": [1, 10, 7],     # Chou-Xu-Wei
    "rude": [0, 3],                # Zi-Mao
    "self": [4, 6, 9, 11],        # Chen, Wu, You, Hai (self with self)
}


def find_branch_interactions(branches: list[EarthlyBranch], 
                             labels: list[str] = None) -> list[dict]:
    """
    Find all branch interactions between a set of branches.
    
    This is the core pattern-recognition function. Given natal + transit/annual
    branches, it finds every active interaction.
    
    Args:
        branches: list of EarthlyBranch objects to check
        labels: optional labels for each branch (e.g., "year", "month", "annual")
    
    Returns:
        List of interaction dicts with type, branches involved, and result
    """
    if labels is None:
        labels = [f"branch_{i}" for i in range(len(branches))]
    
    interactions = []
    n = len(branches)
    
    for i in range(n):
        for j in range(i + 1, n):
            b1, b2 = branches[i], branches[j]
            idx1, idx2 = b1.index, b2.index
            pair = (min(idx1, idx2), max(idx1, idx2))
            pair_ordered = (idx1, idx2)
            
            # Check Six Combinations
            for combo_pair, result_element in SIX_COMBINATIONS.items():
                if set(pair) == set(combo_pair):
                    interactions.append({
                        "type": "Six Combination (六合)",
                        "branches": [f"{labels[i]}:{b1.pinyin}({b1.animal})", 
                                     f"{labels[j]}:{b2.pinyin}({b2.animal})"],
                        "result_element": result_element.value,
                        "note": f"Can transform into {result_element.value} if supported by stems/season",
                    })
            
            # Check Six Clashes
            for clash_pair in SIX_CLASHES:
                if set(pair) == set(clash_pair):
                    interactions.append({
                        "type": "Six Clash (六冲)",
                        "branches": [f"{labels[i]}:{b1.pinyin}({b1.animal})", 
                                     f"{labels[j]}:{b2.pinyin}({b2.animal})"],
                        "note": "Direct opposition. Disruption, conflict, forced movement.",
                    })
            
            # Check Six Harms
            for harm_pair in SIX_HARMS:
                if set(pair) == set(harm_pair):
                    interactions.append({
                        "type": "Six Harm (六害)",
                        "branches": [f"{labels[i]}:{b1.pinyin}({b1.animal})", 
                                     f"{labels[j]}:{b2.pinyin}({b2.animal})"],
                        "note": "Hidden damage, betrayal, subtle undermining.",
                    })
            
            # Check Destructions
            for dest_pair in DESTRUCTIONS:
                if set(pair) == set(dest_pair):
                    interactions.append({
                        "type": "Destruction (相破)",
                        "branches": [f"{labels[i]}:{b1.pinyin}({b1.animal})", 
                                     f"{labels[j]}:{b2.pinyin}({b2.animal})"],
                        "note": "Breaking apart, dissolution of existing structure.",
                    })
    
    # Check Three Harmony (need 3 branches)
    branch_indices = {b.index: (i, labels[i]) for i, b in enumerate(branches)}
    for harmony_triple, result_element in THREE_HARMONY.items():
        present = [idx for idx in harmony_triple if idx in branch_indices]
        if len(present) == 3:
            involved = [f"{branch_indices[idx][1]}:{branches[branch_indices[idx][0]].pinyin}" 
                       for idx in present]
            interactions.append({
                "type": "Three Harmony (三合) - COMPLETE",
                "branches": involved,
                "result_element": result_element.value,
                "note": f"Full {result_element.value} frame. Strong transformation.",
            })
        elif len(present) == 2:
            involved = [f"{branch_indices[idx][1]}:{branches[branch_indices[idx][0]].pinyin}" 
                       for idx in present]
            missing_idx = [idx for idx in harmony_triple if idx not in branch_indices][0]
            missing_branch = EARTHLY_BRANCHES[missing_idx]
            interactions.append({
                "type": "Three Harmony (三合) - PARTIAL",
                "branches": involved,
                "result_element": result_element.value,
                "missing": f"{missing_branch.pinyin}({missing_branch.animal})",
                "note": f"Partial {result_element.value} frame. Tendency without full lock-in.",
            })
    
    # Check Punishments
    for punishment_type, punishment_branches in PUNISHMENTS.items():
        if punishment_type == "self":
            # Self-punishment: same branch appearing twice
            for idx in punishment_branches:
                count = sum(1 for b in branches if b.index == idx)
                if count >= 2:
                    interactions.append({
                        "type": f"Self-Punishment (自刑)",
                        "branches": [f"{labels[i]}:{branches[i].pinyin}" 
                                    for i in range(n) if branches[i].index == idx],
                        "note": "Self-inflicted pressure, internal conflict.",
                    })
        else:
            present = [idx for idx in punishment_branches if idx in branch_indices]
            if len(present) >= 2:
                involved = [f"{branch_indices[idx][1]}:{branches[branch_indices[idx][0]].pinyin}" 
                           for idx in present]
                interactions.append({
                    "type": f"Punishment ({punishment_type}) (刑)",
                    "branches": involved,
                    "complete": len(present) == len(punishment_branches),
                    "note": f"{'Full' if len(present) == len(punishment_branches) else 'Partial'} {punishment_type} punishment.",
                })
    
    return interactions


# ============================================================
# ELEMENT DISTRIBUTION ANALYSIS
# ============================================================

def element_distribution(pillars: list[Pillar], include_hidden: bool = True) -> dict:
    """
    Count element presence across all pillars.
    
    Returns element counts weighted by position:
    - Visible stems: weight 1.0
    - Main qi (hidden stem 1): weight 0.7
    - Middle qi (hidden stem 2): weight 0.5
    - Residual qi (hidden stem 3): weight 0.3
    
    These weights are approximate and debated among practitioners.
    The skill file should instruct the LLM on how to use these.
    """
    HIDDEN_WEIGHTS = [0.7, 0.5, 0.3]
    
    distribution = {e.value: 0.0 for e in Element}
    
    for pillar in pillars:
        # Visible stem
        distribution[pillar.stem.element.value] += 1.0
        
        if include_hidden:
            # Hidden stems
            for idx, hidden_pinyin in enumerate(pillar.branch.hidden_stems):
                hidden_stem = STEM_BY_PINYIN[hidden_pinyin]
                weight = HIDDEN_WEIGHTS[idx] if idx < len(HIDDEN_WEIGHTS) else 0.3
                distribution[hidden_stem.element.value] += weight
    
    return distribution


# ============================================================
# LUCK PILLAR COMPUTATION
# ============================================================

def compute_luck_pillars(year_stem_index: int, month_stem_index: int,
                         month_branch_index: int, gender: str,
                         birth_date: datetime, num_pillars: int = 10) -> list[dict]:
    """
    Compute Luck Pillars (大运 Da Yun).

    Direction of count depends on gender + year stem polarity:
    - Yang stem year + Male OR Yin stem year + Female → count FORWARD
    - Yang stem year + Female OR Yin stem year + Male → count BACKWARD

    Starting age is calculated from birth date to the next/previous
    Jie (solar term boundary), divided by 3 (3 days ≈ 1 year).

    Args:
        year_stem_index: year stem index (0-9)
        month_stem_index: month pillar stem index
        month_branch_index: month pillar branch index
        gender: "male" or "female"
        birth_date: datetime of birth
        num_pillars: how many luck pillars to compute

    Returns:
        List of luck pillar dicts with stem, branch, start_age, end_age
    """
    from compute.astro_calendar import find_nearest_jie

    # Determine direction
    year_yang = (year_stem_index % 2 == 0)  # Even index = Yang
    forward = (year_yang and gender == "male") or (not year_yang and gender == "female")

    # Compute start age from distance to nearest Jie solar term
    birth_jd = swe.julday(birth_date.year, birth_date.month, birth_date.day, 0)
    nearest_jie_jd = find_nearest_jie(birth_jd, birth_date.year, forward=forward)
    days_to_jie = abs(nearest_jie_jd - birth_jd)
    # Traditional rule: 3 days = 1 year of luck pillar time
    start_age = round(days_to_jie / 3)

    pillars = []
    for i in range(num_pillars):
        if forward:
            s_idx = (month_stem_index + i + 1) % 10
            b_idx = (month_branch_index + i + 1) % 12
        else:
            s_idx = (month_stem_index - i - 1) % 10
            b_idx = (month_branch_index - i - 1) % 12

        age_start = start_age + (i * 10)
        age_end = age_start + 9

        pillars.append({
            "number": i + 1,
            "stem": HEAVENLY_STEMS[s_idx].pinyin,
            "stem_element": HEAVENLY_STEMS[s_idx].element.value,
            "stem_polarity": HEAVENLY_STEMS[s_idx].polarity.value,
            "branch": EARTHLY_BRANCHES[b_idx].pinyin,
            "branch_animal": EARTHLY_BRANCHES[b_idx].animal,
            "branch_element": EARTHLY_BRANCHES[b_idx].element.value,
            "age_start": age_start,
            "age_end": age_end,
            "description": f"LP{i+1}: {HEAVENLY_STEMS[s_idx].pinyin} {EARTHLY_BRANCHES[b_idx].pinyin} ({EARTHLY_BRANCHES[b_idx].animal}) ages {age_start}-{age_end}",
        })

    return pillars


# ============================================================
# ANNUAL PILLAR
# ============================================================

def annual_pillar(year: int) -> Pillar:
    """Compute the annual pillar for a given year."""
    stem_index = (year - 4) % 10
    branch_index = (year - 4) % 12
    return Pillar(
        stem=HEAVENLY_STEMS[stem_index],
        branch=EARTHLY_BRANCHES[branch_index],
        position="annual"
    )


# ============================================================
# FULL CHART COMPUTATION
# ============================================================

def compute_chart(birth_date: datetime, birth_hour_lmt: int, 
                  gender: str, month_branch_index: int,
                  li_chun_day: int = 4) -> dict:
    """
    Compute a full BaZi chart from birth data.
    
    Args:
        birth_date: datetime of birth (date portion used)
        birth_hour_lmt: hour in 24h format, LMT corrected
        gender: "male" or "female"
        month_branch_index: earthly branch index for the birth month 
                           (determined from solar terms)
        li_chun_day: day of Li Chun in the birth year's February
    
    Returns:
        Complete chart dict with pillars, ten gods, element distribution,
        and luck pillars.
    """
    # Year pillar
    yp = year_pillar(birth_date.year, birth_date.month, birth_date.day, 
                     li_chun_day=li_chun_day)
    
    # Month pillar
    mp = month_pillar(yp.stem.index, month_branch_index)
    
    # Day pillar
    dp = day_pillar(birth_date)
    
    # Hour pillar
    hp = hour_pillar(dp.stem.index, birth_hour_lmt)
    
    pillars = [yp, mp, dp, hp]
    day_master = dp.stem
    
    # Ten Gods
    gods = map_ten_gods(day_master, pillars)
    
    # Element distribution
    elements = element_distribution(pillars)
    
    # Branch interactions (natal only)
    natal_branches = [p.branch for p in pillars]
    natal_labels = ["year", "month", "day", "hour"]
    natal_interactions = find_branch_interactions(natal_branches, natal_labels)
    
    # Luck pillars
    luck_pillars = compute_luck_pillars(
        yp.stem.index, mp.stem.index, mp.branch.index,
        gender, birth_date
    )
    
    return {
        "day_master": {
            "stem": day_master.pinyin,
            "chinese": day_master.chinese,
            "element": day_master.element.value,
            "polarity": day_master.polarity.value,
            "description": str(day_master),
        },
        "pillars": {
            "year": yp.to_dict(),
            "month": mp.to_dict(),
            "day": dp.to_dict(),
            "hour": hp.to_dict(),
        },
        "ten_gods": gods,
        "element_distribution": elements,
        "natal_branch_interactions": natal_interactions,
        "luck_pillars": luck_pillars,
    }


def annual_interactions(natal_chart: dict, year: int) -> dict:
    """
    Compute interactions between the annual pillar and natal chart.
    
    This is what you run to get the BaZi context for a reading 
    in a specific year.
    """
    ap = annual_pillar(year)
    
    # Get Day Master for Ten God mapping
    dm_pinyin = natal_chart["day_master"]["stem"]
    day_master = STEM_BY_PINYIN[dm_pinyin]
    
    # Annual stem's Ten God relationship
    annual_ten_god = ten_god(day_master, ap.stem)
    
    # Gather all branches: natal + annual
    natal_branches = []
    natal_labels = []
    for pos in ["year", "month", "day", "hour"]:
        branch_pinyin = natal_chart["pillars"][pos]["branch"]["pinyin"]
        natal_branches.append(BRANCH_BY_PINYIN[branch_pinyin])
        natal_labels.append(pos)
    
    natal_branches.append(ap.branch)
    natal_labels.append("annual")
    
    all_interactions = find_branch_interactions(natal_branches, natal_labels)
    
    # Filter to only interactions involving the annual branch
    annual_specific = [i for i in all_interactions 
                      if any("annual:" in b for b in i["branches"])]
    
    return {
        "annual_pillar": ap.to_dict(),
        "annual_ten_god": annual_ten_god,
        "annual_interactions_with_natal": annual_specific,
        "all_active_interactions": all_interactions,
    }


# ============================================================
# TEST / VERIFICATION
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("BaZi Computation Test: Sample Chart (Alex Chen)")
    print("Birth: March 15, 1990, 10:30 AM LMT, San Francisco")
    print("=" * 60)

    # Sample chart (Alex Chen) — matches chart_data/sample.json
    # Expected: Geng Wu, Ji Mao, Ji You, Ji Si
    birth = datetime(1990, 3, 15)
    chart = compute_chart(
        birth_date=birth,
        birth_hour_lmt=10,  # 10:30 AM LMT → Si hour (9-11 AM)
        gender="male",
        month_branch_index=3,  # Mao (Rabbit) month
        li_chun_day=4,
    )

    print(f"\nDay Master: {chart['day_master']['description']}")
    print(f"\nFour Pillars:")
    for pos in ["year", "month", "day", "hour"]:
        p = chart["pillars"][pos]
        print(f"  {pos.capitalize():6s}: {p['description']}")

    print(f"\nExpected: Geng Wu, Ji Mao, Ji You, Ji Si")

    print(f"\nElement Distribution:")
    for element, weight in sorted(chart["element_distribution"].items(),
                                   key=lambda x: -x[1]):
        bar = "█" * int(weight * 5)
        print(f"  {element:6s}: {weight:.1f} {bar}")

    print(f"\nNatal Branch Interactions:")
    for interaction in chart["natal_branch_interactions"]:
        print(f"  {interaction['type']}: {', '.join(interaction['branches'])}")
        print(f"    → {interaction['note']}")

    print(f"\n2026 Annual Interactions:")
    annual = annual_interactions(chart, 2026)
    print(f"  Annual Pillar: {annual['annual_pillar']['description']}")
    print(f"  Annual Ten God: {annual['annual_ten_god']}")
    for interaction in annual["annual_interactions_with_natal"]:
        print(f"  {interaction['type']}: {', '.join(interaction['branches'])}")
        if "note" in interaction:
            print(f"    → {interaction['note']}")

    print(f"\nLuck Pillars (start age computed from solar terms):")
    for lp in chart["luck_pillars"][:6]:
        print(f"  {lp['description']}")

    print(f"\n{'=' * 60}")
    print("Verification:")

    dp = chart["pillars"]["day"]
    ok = dp["stem"]["pinyin"] == "Ji" and dp["branch"]["pinyin"] == "You"
    print(f"Day Pillar: {chart['pillars']['day']['combined']} (expected Ji You) {'✓' if ok else '✗'}")

    lp_age = chart["luck_pillars"][0]["age_start"]
    age_ok = lp_age == 7
    print(f"LP Start Age: {lp_age} (expected 7) {'✓' if age_ok else '✗'}")
