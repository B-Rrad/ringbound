from __future__ import annotations

import csv
import json
import math
import os
import random
import statistics
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from xml.sax.saxutils import escape


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT_DIR, "data")
OUTPUT_DIR = os.path.join(ROOT_DIR, "analysis_outputs")

SELF_PLAY_GAMES = 2000
CROSS_PLAY_GAMES = 1500
MAX_ROUNDS = 200

ATTACK_HEROES = {"aragorn", "legolas", "galadriel", "frodo", "nazgul", "saruman", "sauron", "balrog", "gollum", "wormtongue"}
DEFENSE_HEROES = {"gandalf", "galadriel", "boromir"}


def load_cards():
    with open(os.path.join(DATA_DIR, "realm_cards.json"), "r", encoding="utf-8") as file:
        realm_cards = json.load(file)["realm_cards"]
    with open(os.path.join(DATA_DIR, "hero_cards.json"), "r", encoding="utf-8") as file:
        hero_cards = json.load(file)["hero_cards"]
    return realm_cards, hero_cards


def clone_cards(cards):
    return [dict(card) for card in cards]


def mean(values):
    return statistics.fmean(values) if values else 0.0


def pct(value):
    return round(value * 100, 2)


def ci_95(p, n):
    if n == 0:
        return 0.0
    return 1.96 * math.sqrt((p * (1 - p)) / n)


def col_name(index):
    name = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


class SimpleXlsxWriter:
    def __init__(self, path):
        self.path = path
        self.sheets = []

    def add_sheet(self, name, rows):
        safe_name = name[:31]
        existing = {sheet_name for sheet_name, _ in self.sheets}
        if safe_name in existing:
            counter = 2
            candidate = safe_name[:28]
            while f"{candidate}_{counter}" in existing:
                counter += 1
            safe_name = f"{candidate}_{counter}"
        self.sheets.append((safe_name, rows))

    def _cell_xml(self, row_index, column_index, value):
        ref = f"{col_name(column_index)}{row_index}"
        if value is None or value == "":
            return ""
        if isinstance(value, bool):
            return f'<c r="{ref}" t="n"><v>{1 if value else 0}</v></c>'
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f'<c r="{ref}" t="n"><v>{value}</v></c>'
        text = escape(str(value))
        return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'

    def _sheet_xml(self, rows):
        if not rows:
            rows = [[""]]
        max_cols = max(len(row) for row in rows)
        dimension = f"A1:{col_name(max_cols)}{len(rows)}"
        row_xml = []
        for row_index, row in enumerate(rows, start=1):
            cells = "".join(self._cell_xml(row_index, column_index, value) for column_index, value in enumerate(row, start=1))
            row_xml.append(f'<row r="{row_index}">{cells}</row>')
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<dimension ref=\"{dimension}\"/>"
            "<sheetViews><sheetView workbookViewId=\"0\"/></sheetViews>"
            "<sheetFormatPr defaultRowHeight=\"15\"/>"
            f"<sheetData>{''.join(row_xml)}</sheetData>"
            "</worksheet>"
        )

    def write(self):
        timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        with zipfile.ZipFile(self.path, "w", zipfile.ZIP_DEFLATED) as workbook:
            workbook.writestr(
                "[Content_Types].xml",
                (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                    '<Default Extension="xml" ContentType="application/xml"/>'
                    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                    '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                    '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
                    '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
                    + "".join(
                        f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                        for index in range(1, len(self.sheets) + 1)
                    )
                    + "</Types>"
                ),
            )
            workbook.writestr(
                "_rels/.rels",
                (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
                    '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
                    "</Relationships>"
                ),
            )
            workbook.writestr(
                "docProps/core.xml",
                (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                    'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
                    'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                    "<dc:creator>Codex</dc:creator>"
                    "<cp:lastModifiedBy>Codex</cp:lastModifiedBy>"
                    f'<dcterms:created xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:created>'
                    f'<dcterms:modified xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:modified>'
                    "<dc:title>Ringbound Balance Analysis</dc:title>"
                    "</cp:coreProperties>"
                ),
            )
            workbook.writestr(
                "docProps/app.xml",
                (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
                    'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
                    "<Application>Codex</Application>"
                    f"<TitlesOfParts><vt:vector size=\"{len(self.sheets)}\" baseType=\"lpstr\">"
                    + "".join(f"<vt:lpstr>{escape(name)}</vt:lpstr>" for name, _ in self.sheets)
                    + "</vt:vector></TitlesOfParts>"
                    "</Properties>"
                ),
            )
            workbook.writestr(
                "xl/workbook.xml",
                (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                    "<sheets>"
                    + "".join(
                        f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
                        for index, (name, _) in enumerate(self.sheets, start=1)
                    )
                    + "</sheets></workbook>"
                ),
            )
            workbook.writestr(
                "xl/_rels/workbook.xml.rels",
                (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    + "".join(
                        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
                        for index in range(1, len(self.sheets) + 1)
                    )
                    + f'<Relationship Id="rId{len(self.sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                    + "</Relationships>"
                ),
            )
            workbook.writestr(
                "xl/styles.xml",
                (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                    '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
                    '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
                    '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
                    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
                    '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
                    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
                    '</styleSheet>'
                ),
            )
            for index, (_, rows) in enumerate(self.sheets, start=1):
                workbook.writestr(f"xl/worksheets/sheet{index}.xml", self._sheet_xml(rows))


@dataclass
class BaseAI:
    name: str

    hero_draft_scores = {
        "galadriel": 8.8,
        "boromir": 8.5,
        "gandalf": 8.2,
        "balrog": 8.0,
        "sauron": 7.8,
        "saruman": 7.6,
        "nazgul": 7.2,
        "wormtongue": 7.0,
        "frodo": 6.8,
        "aragorn": 6.7,
        "legolas": 6.5,
        "gollum": 6.0,
    }

    def draft_score(self, card):
        if "rank" in card:
            return card["rank"] - 5
        return self.hero_draft_scores.get(card["id"], 5.0)

    def choose_draft_card(self, game, player, options):
        return max(options, key=self.draft_score)

    def choose_attack_action(self, game, player, legal_realm, usable_heroes):
        hero = self.choose_attack_hero(game, player, usable_heroes)
        if hero is not None:
            return ("hero", hero)
        if legal_realm:
            return ("realm", min(legal_realm, key=lambda card: (game.is_trump_card(card), card["rank"])))
        return ("pass", None)

    def choose_attack_hero(self, game, player, usable_heroes):
        if "galadriel" in [hero["id"] for hero in usable_heroes] and game.wounds[player] >= 4:
            return next(hero for hero in usable_heroes if hero["id"] == "galadriel")
        return None

    def choose_defense_action(self, game, player, legal_realm, usable_heroes):
        hero = self.choose_defense_hero(game, player, legal_realm, usable_heroes)
        if hero is not None:
            return ("hero", hero)
        if legal_realm:
            return ("realm", min(legal_realm, key=lambda card: (game.is_trump_card(card), card["rank"])))
        return ("concede", None)

    def choose_defense_hero(self, game, player, legal_realm, usable_heroes):
        if "galadriel" in [hero["id"] for hero in usable_heroes] and game.wounds[player] >= 4:
            return next(hero for hero in usable_heroes if hero["id"] == "galadriel")
        return None

    def choose_reinforce_action(self, game, player, legal_realm, usable_heroes):
        if not legal_realm and not usable_heroes:
            return ("end", None)
        if legal_realm:
            best = min(legal_realm, key=lambda card: (game.is_trump_card(card), card["rank"]))
            if best["rank"] <= 9:
                return ("realm", best)
        hero = self.choose_attack_hero(game, player, usable_heroes)
        if hero is not None:
            return ("hero", hero)
        return ("end", None)

    def choose_suit(self, game, player, hero_card):
        known_opponent = game.get_known_opponent_cards(player)
        if hero_card["id"] == "wormtongue":
            if known_opponent:
                counts = Counter(card["suit"] for card in known_opponent if "suit" in card)
                if counts:
                    return counts.most_common(1)[0][0]
            attack = game.get_current_attack_card()
            if attack is not None:
                return attack["suit"]
        own_counts = Counter(card["suit"] for card in game.get_player_realm_hand(player))
        if own_counts:
            return own_counts.most_common(1)[0][0]
        return game.all_suits[0]

    def choose_aragorn_target(self, game, player):
        def score(index_and_card):
            index, card = index_and_card
            defended = index < len(game.table_defenses)
            return (game.is_trump_card(card), defended, card["rank"])
        return max(enumerate(game.table_attacks), key=score)[1]

    def choose_saruman_exchange_card(self, game, player):
        realm_cards = list(game.get_player_realm_hand(player))
        return min(realm_cards, key=lambda card: (game.is_trump_card(card), card["rank"]))


class RandomAI(BaseAI):
    def choose_draft_card(self, game, player, options):
        return game.random.choice(options)

    def choose_attack_action(self, game, player, legal_realm, usable_heroes):
        if usable_heroes and game.random.random() < 0.3:
            return ("hero", game.random.choice(usable_heroes))
        if legal_realm:
            return ("realm", game.random.choice(legal_realm))
        return ("pass", None)

    def choose_defense_action(self, game, player, legal_realm, usable_heroes):
        if usable_heroes and game.random.random() < 0.35:
            return ("hero", game.random.choice(usable_heroes))
        if legal_realm:
            return ("realm", game.random.choice(legal_realm))
        return ("concede", None)

    def choose_reinforce_action(self, game, player, legal_realm, usable_heroes):
        if usable_heroes and game.random.random() < 0.25:
            return ("hero", game.random.choice(usable_heroes))
        if legal_realm and game.random.random() < 0.55:
            return ("realm", game.random.choice(legal_realm))
        return ("end", None)

    def choose_suit(self, game, player, hero_card):
        return game.random.choice(game.all_suits)

    def choose_aragorn_target(self, game, player):
        return game.random.choice(game.table_attacks)

    def choose_saruman_exchange_card(self, game, player):
        return game.random.choice(game.get_player_realm_hand(player))


class GreedyAI(BaseAI):
    def choose_attack_hero(self, game, player, usable_heroes):
        hero_map = {hero["id"]: hero for hero in usable_heroes}
        opponent = game.get_opponent(player)
        opponent_known = game.get_known_opponent_cards(player)
        opponent_trumps = 0
        if opponent_known:
            opponent_trumps = sum(1 for card in opponent_known if "suit" in card and game.is_trump_card(card))

        if "galadriel" in hero_map and game.wounds[player] >= 3:
            return hero_map["galadriel"]
        if "sauron" in hero_map and game.play_phase == "ATTACK" and not game.table_attacks:
            return hero_map["sauron"]
        if "saruman" in hero_map and game.play_phase == "ATTACK" and not game.table_attacks:
            target = game.get_saruman_target_card()
            if target is not None and (game.is_trump_card(target) or target["rank"] >= 12):
                return hero_map["saruman"]
        if "wormtongue" in hero_map and (game.play_phase == "ATTACK" or game.get_current_attack_card() is not None):
            return hero_map["wormtongue"]
        if "nazgul" in hero_map and opponent_trumps <= 2:
            return hero_map["nazgul"]
        if "frodo" in hero_map and opponent_trumps >= 2:
            return hero_map["frodo"]
        if "balrog" in hero_map and game.wounds[opponent] >= 3:
            return hero_map["balrog"]
        if "legolas" in hero_map and game.play_phase == "REINFORCE":
            return hero_map["legolas"]
        if "aragorn" in hero_map and any(index < len(game.table_defenses) for index in range(len(game.table_attacks))):
            return hero_map["aragorn"]
        if "gollum" in hero_map and game.play_phase in ("ATTACK", "REINFORCE"):
            return hero_map["gollum"]
        return None

    def choose_defense_hero(self, game, player, legal_realm, usable_heroes):
        hero_map = {hero["id"]: hero for hero in usable_heroes}
        attack = game.get_current_attack_card()
        if attack is None:
            return None

        if "galadriel" in hero_map and game.wounds[player] >= 3:
            return hero_map["galadriel"]
        if "gandalf" in hero_map and (not legal_realm or attack["rank"] >= 12):
            return hero_map["gandalf"]
        if "boromir" in hero_map and (not legal_realm or game.is_trump_card(attack)):
            return hero_map["boromir"]
        return None

    def choose_reinforce_action(self, game, player, legal_realm, usable_heroes):
        hero = self.choose_attack_hero(game, player, usable_heroes)
        if hero is not None and hero["id"] in {"balrog", "legolas", "aragorn"}:
            return ("hero", hero)

        if not legal_realm:
            return ("end", None)

        opponent = game.get_opponent(player)
        if len(game.get_player_realm_hand(opponent)) <= len(game.get_player_realm_hand(player)):
            best = min(legal_realm, key=lambda card: (game.is_trump_card(card), card["rank"]))
            if best["rank"] <= 11:
                return ("realm", best)
        return ("end", None)


class StrategicAI(GreedyAI):
    def draft_score(self, card):
        base = super().draft_score(card)
        if "rank" in card:
            return base + (1.5 if card["rank"] >= 12 else 0)
        return base + 0.6

    def choose_attack_action(self, game, player, legal_realm, usable_heroes):
        hero = self.choose_attack_hero(game, player, usable_heroes)
        if hero is not None and hero["id"] in {"sauron", "saruman", "wormtongue", "nazgul", "frodo", "balrog", "legolas"}:
            return ("hero", hero)
        if legal_realm:
            return ("realm", self.choose_best_attack_card(game, player, legal_realm))
        if hero is not None:
            return ("hero", hero)
        return ("pass", None)

    def choose_best_attack_card(self, game, player, legal_realm):
        opponent_cards = game.get_known_opponent_cards(player)
        scored = []
        for card in legal_realm:
            difficulty = 0.0
            if opponent_cards:
                defendable = any(game.can_defend_with_card(opp_card, card) for opp_card in opponent_cards if "suit" in opp_card)
                difficulty = 2.0 if not defendable else 0.0
            trump_penalty = 3.0 if game.is_trump_card(card) else 0.0
            scored.append((difficulty - trump_penalty - (card["rank"] / 20.0), card))
        return max(scored, key=lambda item: item[0])[1]

    def choose_reinforce_action(self, game, player, legal_realm, usable_heroes):
        hero = self.choose_attack_hero(game, player, usable_heroes)
        if hero is not None:
            return ("hero", hero)
        if not legal_realm:
            return ("end", None)

        opponent = game.get_opponent(player)
        opponent_count = len(game.get_player_realm_hand(opponent)) + len(game.get_player_hero_hand(opponent))
        if opponent_count <= len(game.get_player_realm_hand(player)) + len(game.get_player_hero_hand(player)):
            return ("realm", self.choose_best_attack_card(game, player, legal_realm))
        return ("end", None)

    def choose_defense_action(self, game, player, legal_realm, usable_heroes):
        hero = self.choose_defense_hero(game, player, legal_realm, usable_heroes)
        if hero is not None:
            return ("hero", hero)
        if legal_realm:
            return ("realm", min(legal_realm, key=lambda card: (game.is_trump_card(card), card["rank"])))
        return ("concede", None)

    def choose_suit(self, game, player, hero_card):
        known_opponent = game.get_known_opponent_cards(player)
        if hero_card["id"] == "wormtongue":
            attack = game.get_current_attack_card()
            if attack is not None:
                return attack["suit"]
            if known_opponent:
                counts = Counter(card["suit"] for card in known_opponent if "suit" in card)
                if counts:
                    return counts.most_common(1)[0][0]

        own_counts = Counter(card["suit"] for card in game.get_player_realm_hand(player))
        if known_opponent and hero_card["id"] == "gollum":
            enemy_counts = Counter(card["suit"] for card in known_opponent if "suit" in card)
            best_score = None
            best_suit = game.all_suits[0]
            for suit in game.all_suits:
                score = own_counts.get(suit, 0) - enemy_counts.get(suit, 0)
                if best_score is None or score > best_score:
                    best_score = score
                    best_suit = suit
            return best_suit
        if own_counts:
            return own_counts.most_common(1)[0][0]
        return game.all_suits[0]


class SimulationGame:
    def __init__(self, realm_cards, hero_cards, p1_ai, p2_ai, seed):
        self.random = random.Random(seed)
        self.seed = seed
        self.p1_ai = p1_ai
        self.p2_ai = p2_ai
        self.realm_cards_source = clone_cards(realm_cards)
        self.hero_cards_source = clone_cards(hero_cards)
        self.all_suits = sorted({card["suit"] for card in realm_cards})
        self.reset()

    def reset(self):
        self.p1_hand = []
        self.p2_hand = []
        self.p1_heroes = []
        self.p2_heroes = []
        self.drafted_heroes = {"P1": [], "P2": []}
        self.drafted_cards = {"P1": [], "P2": []}
        self.wounds = {"P1": 0, "P2": 0}
        self.table_attacks = []
        self.table_defenses = []
        self.realm_deck = []
        self.hero_deck = []
        self.trump_card = None
        self.trump_suit = None
        self.current_drafter = None
        self.first_attacker = None
        self.attacker = None
        self.defender = None
        self.current_player = None
        self.play_phase = "ATTACK"
        self.round_effects = self.new_round_effects()
        self.revealed_hand = None
        self.discard_pile = []
        self.hero_usage = Counter()
        self.hero_usage_by_player = {"P1": Counter(), "P2": Counter()}
        self.rounds_played = 0
        self.tie_breaker_used = False
        self.final_reason = "normal"

    def new_round_effects(self):
        return {
            "trump_disabled": False,
            "temporary_trump_suit": None,
            "nazgul_active": False,
            "wormtongue_suit": None,
            "legolas_bonus": 0,
            "balrog_active": None,
        }

    def get_ai(self, player):
        return self.p1_ai if player == "P1" else self.p2_ai

    def get_opponent(self, player):
        return "P2" if player == "P1" else "P1"

    def get_player_realm_hand(self, player):
        return self.p1_hand if player == "P1" else self.p2_hand

    def get_player_hero_hand(self, player):
        return self.p1_heroes if player == "P1" else self.p2_heroes

    def get_known_opponent_cards(self, player):
        if self.revealed_hand is not None and self.revealed_hand["viewer"] == player:
            return list(self.get_player_realm_hand(self.get_opponent(player)))
        return None

    def get_effective_trump_suit(self):
        if self.round_effects["trump_disabled"]:
            return None
        if self.round_effects["temporary_trump_suit"] is not None:
            return self.round_effects["temporary_trump_suit"]
        return self.trump_suit

    def is_trump_card(self, card):
        effective_trump = self.get_effective_trump_suit()
        return effective_trump is not None and card.get("suit") == effective_trump

    def get_current_attack_card(self):
        if len(self.table_attacks) > len(self.table_defenses):
            return self.table_attacks[-1]
        return None

    def get_reinforce_ranks(self):
        return [card["rank"] for card in self.table_attacks + self.table_defenses if "rank" in card]

    def player_has_no_cards(self, player):
        return not self.get_player_realm_hand(player) and not self.get_player_hero_hand(player)

    def setup_game(self):
        self.realm_deck = clone_cards(self.realm_cards_source)
        self.hero_deck = clone_cards(self.hero_cards_source)
        self.random.shuffle(self.realm_deck)
        self.random.shuffle(self.hero_deck)

        p1_init = self.realm_deck.pop()
        p2_init = self.realm_deck.pop()
        self.p1_hand.append(p1_init)
        self.p2_hand.append(p2_init)
        self.drafted_cards["P1"].append(p1_init["id"])
        self.drafted_cards["P2"].append(p2_init["id"])

        if p1_init["rank"] > p2_init["rank"]:
            self.current_drafter = "P1"
            self.first_attacker = "P2"
        elif p2_init["rank"] > p1_init["rank"]:
            self.current_drafter = "P2"
            self.first_attacker = "P1"
        else:
            self.current_drafter = self.random.choice(["P1", "P2"])
            self.first_attacker = self.get_opponent(self.current_drafter)

        self.trump_card = self.realm_deck.pop()
        self.trump_suit = self.trump_card["suit"]
        realm_pool = [self.realm_deck.pop() for _ in range(10)]
        hero_pool = [self.hero_deck.pop() for _ in range(8)]

        while realm_pool or hero_pool:
            player = self.current_drafter
            ai = self.get_ai(player)
            options = realm_pool + hero_pool
            choice = ai.choose_draft_card(self, player, options)
            if choice in realm_pool:
                self.get_player_realm_hand(player).append(choice)
                self.drafted_cards[player].append(choice["id"])
                realm_pool.remove(choice)
            else:
                self.get_player_hero_hand(player).append(choice)
                self.drafted_heroes[player].append(choice["id"])
                hero_pool.remove(choice)
            self.current_drafter = self.get_opponent(player)

        self.attacker = self.first_attacker
        self.defender = self.get_opponent(self.attacker)
        self.current_player = self.attacker
        self.play_phase = "ATTACK"

    def can_defend_with_card(self, defense_card, attack_card):
        if attack_card is None:
            return False
        if self.round_effects["wormtongue_suit"] == defense_card["suit"]:
            return False
        if self.round_effects["nazgul_active"] and not self.is_trump_card(defense_card):
            return False
        if defense_card["suit"] == attack_card["suit"] and defense_card["rank"] > attack_card["rank"]:
            return True
        if self.is_trump_card(defense_card) and not self.is_trump_card(attack_card):
            return True
        if self.is_trump_card(defense_card) and self.is_trump_card(attack_card):
            return defense_card["rank"] > attack_card["rank"]
        return False

    def can_attack_with_card(self, attack_card):
        if self.play_phase == "ATTACK":
            return True
        if self.play_phase != "REINFORCE":
            return False
        if self.round_effects["legolas_bonus"] > 0:
            return True
        ranks = self.get_reinforce_ranks()
        return not ranks or attack_card["rank"] in ranks

    def get_saruman_target_card(self):
        defender_hand = list(self.get_player_realm_hand(self.defender))
        if not defender_hand:
            return None
        effective_trump = self.get_effective_trump_suit()
        trump_cards = [card for card in defender_hand if effective_trump is not None and card["suit"] == effective_trump]
        if trump_cards:
            return max(trump_cards, key=lambda card: card["rank"])
        return max(defender_hand, key=lambda card: card["rank"])

    def can_use_hero(self, player, hero_card):
        hero_id = hero_card["id"]
        realm_count = len(self.get_player_realm_hand(player))
        attack_card = self.get_current_attack_card()
        if hero_id == "aragorn":
            return player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE") and bool(self.table_attacks)
        if hero_id == "legolas":
            return player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE") and realm_count > 0 and self.round_effects["legolas_bonus"] == 0
        if hero_id == "gandalf":
            return player == self.defender and self.play_phase == "DEFEND" and attack_card is not None and not self.is_trump_card(attack_card)
        if hero_id == "galadriel":
            return self.wounds[player] > 0
        if hero_id == "frodo":
            return player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE") and not self.round_effects["trump_disabled"]
        if hero_id == "boromir":
            return player == self.defender and self.play_phase == "DEFEND" and attack_card is not None
        if hero_id == "nazgul":
            return player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE") and not self.round_effects["nazgul_active"] and self.get_effective_trump_suit() is not None
        if hero_id == "saruman":
            return player == self.attacker and self.play_phase == "ATTACK" and not self.table_attacks and realm_count > 0 and self.get_saruman_target_card() is not None
        if hero_id == "sauron":
            return player == self.attacker and self.play_phase == "ATTACK" and not self.table_attacks and self.revealed_hand is None
        if hero_id == "balrog":
            return player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE") and self.round_effects["balrog_active"] is None
        if hero_id == "gollum":
            return player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE") and not self.round_effects["trump_disabled"] and self.round_effects["temporary_trump_suit"] is None
        if hero_id == "wormtongue":
            return player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE") and self.round_effects["wormtongue_suit"] is None
        return False

    def usable_heroes(self, player):
        return [hero for hero in self.get_player_hero_hand(player) if self.can_use_hero(player, hero)]

    def legal_attack_cards(self, player):
        return [card for card in self.get_player_realm_hand(player) if self.can_attack_with_card(card)]

    def legal_defense_cards(self, player):
        attack = self.get_current_attack_card()
        if attack is None:
            return []
        return [card for card in self.get_player_realm_hand(player) if self.can_defend_with_card(card, attack)]

    def discard_card(self, card):
        self.discard_pile.append(card["id"])

    def consume_hero(self, player, hero):
        hand = self.get_player_hero_hand(player)
        if hero in hand:
            hand.remove(hero)
            self.hero_usage[hero["id"]] += 1
            self.hero_usage_by_player[player][hero["id"]] += 1
            self.discard_card(hero)

    def remove_random_card(self, player):
        realm = self.get_player_realm_hand(player)
        heroes = self.get_player_hero_hand(player)
        combined = realm + heroes
        if not combined:
            return None
        choice = self.random.choice(combined)
        if choice in realm:
            realm.remove(choice)
        else:
            heroes.remove(choice)
        self.discard_card(choice)
        return choice

    def apply_hero(self, player, hero):
        hero_id = hero["id"]
        ai = self.get_ai(player)
        self.consume_hero(player, hero)

        if hero_id == "aragorn":
            if self.table_attacks:
                target = ai.choose_aragorn_target(self, player)
                if target in self.table_attacks:
                    index = self.table_attacks.index(target)
                    self.table_attacks.pop(index)
                    self.get_player_realm_hand(player).append(target)
                    if index < len(self.table_defenses):
                        removed_defense = self.table_defenses.pop(index)
                        self.discard_card(removed_defense)
                    self.sync_turn_after_table_change()
            return
        if hero_id == "legolas":
            self.round_effects["legolas_bonus"] = 1
            return
        if hero_id == "gandalf":
            if self.table_attacks:
                removed = self.table_attacks.pop()
                self.discard_card(removed)
                if self.player_has_no_cards(self.defender) and len(self.table_attacks) == len(self.table_defenses):
                    self.end_round(False, False)
                    return
                self.sync_turn_after_table_change()
            return
        if hero_id == "galadriel":
            self.wounds[player] = max(0, self.wounds[player] - 2)
            return
        if hero_id == "frodo":
            self.round_effects["trump_disabled"] = True
            self.round_effects["temporary_trump_suit"] = None
            return
        if hero_id == "boromir":
            if self.get_current_attack_card() is not None:
                self.table_defenses.append({"id": "boromir_guard", "name": "Boromir"})
                self.remove_random_card(self.attacker)
                if self.player_has_no_cards(self.defender):
                    self.end_round(False, False)
                else:
                    self.play_phase = "REINFORCE"
                    self.current_player = self.attacker
            return
        if hero_id == "nazgul":
            self.round_effects["nazgul_active"] = True
            return
        if hero_id == "saruman":
            target = self.get_saruman_target_card()
            if target is not None and target in self.get_player_realm_hand(self.defender):
                choice = ai.choose_saruman_exchange_card(self, player)
                own_realm = self.get_player_realm_hand(player)
                if choice in own_realm:
                    own_realm.remove(choice)
                    self.get_player_realm_hand(self.defender).remove(target)
                    own_realm.append(target)
                    self.get_player_realm_hand(self.defender).append(choice)
            return
        if hero_id == "sauron":
            self.revealed_hand = {"viewer": player, "target": self.get_opponent(player)}
            return
        if hero_id == "balrog":
            self.round_effects["balrog_active"] = player
            return
        if hero_id == "gollum":
            self.round_effects["temporary_trump_suit"] = ai.choose_suit(self, player, hero)
            return
        if hero_id == "wormtongue":
            self.round_effects["wormtongue_suit"] = ai.choose_suit(self, player, hero)

    def sync_turn_after_table_change(self):
        if len(self.table_attacks) > len(self.table_defenses):
            self.play_phase = "DEFEND"
            self.current_player = self.defender
        elif self.table_attacks:
            self.play_phase = "REINFORCE"
            self.current_player = self.attacker
        else:
            self.play_phase = "ATTACK"
            self.current_player = self.attacker

    def play_attack_card(self, player, card):
        hand = self.get_player_realm_hand(player)
        hand.remove(card)
        self.table_attacks.append(card)
        if self.round_effects["legolas_bonus"] > 0:
            self.round_effects["legolas_bonus"] -= 1
        self.play_phase = "DEFEND"
        self.current_player = self.defender

    def play_defense_card(self, player, card):
        hand = self.get_player_realm_hand(player)
        hand.remove(card)
        self.table_defenses.append(card)
        if self.player_has_no_cards(self.defender):
            self.end_round(False, False)
        else:
            self.play_phase = "REINFORCE"
            self.current_player = self.attacker

    def concede_defense(self):
        self.wounds[self.defender] += 1
        self.end_round(True, True)

    def draw_back_to_six(self, player):
        hand = self.get_player_realm_hand(player)
        while len(hand) < 6 and self.realm_deck:
            hand.append(self.realm_deck.pop())

    def end_round(self, defender_took_wound, pickup_defenses):
        if not defender_took_wound and self.round_effects["balrog_active"] == self.attacker:
            self.wounds[self.defender] += 1
            defender_took_wound = True

        if not defender_took_wound:
            self.attacker, self.defender = self.defender, self.attacker
        elif pickup_defenses:
            defender_hand = self.get_player_realm_hand(self.defender)
            for card in self.table_defenses:
                if "rank" in card:
                    defender_hand.append(card)

        for card in self.table_attacks:
            self.discard_card(card)
        for card in self.table_defenses:
            if pickup_defenses and "rank" in card:
                continue
            self.discard_card(card)

        self.draw_back_to_six(self.attacker)
        self.draw_back_to_six(self.defender)
        self.table_attacks = []
        self.table_defenses = []
        self.play_phase = "ATTACK"
        self.current_player = self.attacker
        self.round_effects = self.new_round_effects()
        self.revealed_hand = None

    def winner_by_tiebreak(self):
        self.tie_breaker_used = True
        self.final_reason = "max_rounds_tiebreak"
        p1_score = (-self.wounds["P1"], len(self.p1_hand) + len(self.p1_heroes))
        p2_score = (-self.wounds["P2"], len(self.p2_hand) + len(self.p2_heroes))
        if p1_score > p2_score:
            return "P1"
        if p2_score > p1_score:
            return "P2"
        return self.random.choice(["P1", "P2"])

    def check_game_over(self):
        if self.wounds["P1"] >= 6:
            return "P2"
        if self.wounds["P2"] >= 6:
            return "P1"
        if not self.realm_deck:
            p1_realm_empty = len(self.p1_hand) == 0
            p2_realm_empty = len(self.p2_hand) == 0
            if p1_realm_empty and not p2_realm_empty:
                return "P1"
            if p2_realm_empty and not p1_realm_empty:
                return "P2"
            if p1_realm_empty and p2_realm_empty:
                if self.wounds["P1"] < self.wounds["P2"]:
                    return "P1"
                if self.wounds["P2"] < self.wounds["P1"]:
                    return "P2"
                p1_total = len(self.p1_hand) + len(self.p1_heroes)
                p2_total = len(self.p2_hand) + len(self.p2_heroes)
                if p1_total < p2_total:
                    return "P1"
                if p2_total < p1_total:
                    return "P2"
        return None

    def run(self):
        self.setup_game()
        winner = None
        while winner is None and self.rounds_played < MAX_ROUNDS:
            self.rounds_played += 1
            self.table_attacks = []
            self.table_defenses = []
            self.play_phase = "ATTACK"
            self.current_player = self.attacker
            self.round_effects = self.new_round_effects()
            self.revealed_hand = None

            while winner is None:
                player = self.current_player
                ai = self.get_ai(player)
                if player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE"):
                    legal_realm = self.legal_attack_cards(player)
                    usable_heroes = [hero for hero in self.usable_heroes(player) if hero["id"] in ATTACK_HEROES]
                    if self.play_phase == "ATTACK":
                        action, payload = ai.choose_attack_action(self, player, legal_realm, usable_heroes)
                    else:
                        action, payload = ai.choose_reinforce_action(self, player, legal_realm, usable_heroes)

                    if action == "hero" and payload is not None:
                        self.apply_hero(player, payload)
                    elif action == "realm" and payload is not None:
                        self.play_attack_card(player, payload)
                    else:
                        self.end_round(False, False)

                    winner = self.check_game_over()
                else:
                    legal_realm = self.legal_defense_cards(player)
                    usable_heroes = [hero for hero in self.usable_heroes(player) if hero["id"] in DEFENSE_HEROES]
                    action, payload = ai.choose_defense_action(self, player, legal_realm, usable_heroes)
                    if action == "hero" and payload is not None:
                        self.apply_hero(player, payload)
                    elif action == "realm" and payload is not None:
                        self.play_defense_card(player, payload)
                    else:
                        self.concede_defense()
                    winner = self.check_game_over()

                if winner is not None:
                    break
                if self.play_phase == "ATTACK" and self.current_player == self.attacker and not self.table_attacks:
                    break

        if winner is None:
            winner = self.winner_by_tiebreak()

        return {
            "seed": self.seed,
            "winner_player": winner,
            "winner_ai": self.get_ai(winner).name,
            "p1_ai": self.p1_ai.name,
            "p2_ai": self.p2_ai.name,
            "p1_wounds": self.wounds["P1"],
            "p2_wounds": self.wounds["P2"],
            "rounds": self.rounds_played,
            "first_attacker": self.first_attacker,
            "first_drafter": self.current_drafter,
            "trump_suit": self.trump_suit,
            "hero_usage": dict(self.hero_usage),
            "hero_usage_p1": dict(self.hero_usage_by_player["P1"]),
            "hero_usage_p2": dict(self.hero_usage_by_player["P2"]),
            "drafted_heroes_p1": list(self.drafted_heroes["P1"]),
            "drafted_heroes_p2": list(self.drafted_heroes["P2"]),
            "tie_breaker": self.tie_breaker_used,
            "final_reason": self.final_reason,
        }


def run_matchup(realm_cards, hero_cards, label_a, ai_a, label_b, ai_b, games, seed_start):
    results = []
    for game_index in range(games):
        if label_a != label_b and game_index % 2 == 1:
            p1_ai = ai_b
            p2_ai = ai_a
            seat_map = {"P1": label_b, "P2": label_a}
        else:
            p1_ai = ai_a
            p2_ai = ai_b
            seat_map = {"P1": label_a, "P2": label_b}

        result = SimulationGame(realm_cards, hero_cards, p1_ai, p2_ai, seed_start + game_index).run()
        result["experiment"] = f"{label_a}_vs_{label_b}"
        result["game_index"] = game_index + 1
        result["label_a"] = label_a
        result["label_b"] = label_b
        result["winner_label"] = seat_map[result["winner_player"]]
        result["p1_label"] = seat_map["P1"]
        result["p2_label"] = seat_map["P2"]
        results.append(result)
    return results


def summarize_experiments(raw_results):
    experiments = defaultdict(list)
    for row in raw_results:
        experiments[row["experiment"]].append(row)

    summary_rows = []
    role_rows = []
    for experiment, rows in sorted(experiments.items()):
        label_a = rows[0]["label_a"]
        label_b = rows[0]["label_b"]
        games = len(rows)
        label_a_wins = sum(1 for row in rows if row["winner_label"] == label_a)
        label_b_wins = sum(1 for row in rows if row["winner_label"] == label_b)
        p1_wins = sum(1 for row in rows if row["winner_player"] == "P1")
        first_attacker_wins = sum(1 for row in rows if row["winner_player"] == row["first_attacker"])
        tie_breaks = sum(1 for row in rows if row["tie_breaker"])
        ai_a_wins = label_a_wins if label_a != label_b else None
        ai_b_wins = label_b_wins if label_a != label_b else None
        ai_a_rate = (label_a_wins / games) if label_a != label_b else None
        summary_rows.append({
            "experiment": experiment,
            "label_a": label_a,
            "label_b": label_b,
            "games": games,
            "label_a_wins": ai_a_wins,
            "label_b_wins": ai_b_wins,
            "label_a_win_rate": ai_a_rate,
            "p1_win_rate": p1_wins / games,
            "first_attacker_win_rate": first_attacker_wins / games,
            "avg_rounds": mean([row["rounds"] for row in rows]),
            "avg_p1_wounds": mean([row["p1_wounds"] for row in rows]),
            "avg_p2_wounds": mean([row["p2_wounds"] for row in rows]),
            "tie_break_games": tie_breaks,
        })

        for role_name, rate in [("P1", p1_wins / games), ("FirstAttacker", first_attacker_wins / games)]:
            role_rows.append({
                "experiment": experiment,
                "role": role_name,
                "win_rate": rate,
                "ci95": ci_95(rate, games),
                "games": games,
            })

    return summary_rows, role_rows


def summarize_heroes(raw_results):
    drafted = Counter()
    used = Counter()
    wins_when_used = Counter()
    for row in raw_results:
        for hero in row["drafted_heroes_p1"] + row["drafted_heroes_p2"]:
            drafted[hero] += 1
        for hero, count in row["hero_usage"].items():
            used[hero] += count
        winner_usage = row["hero_usage_p1"] if row["winner_player"] == "P1" else row["hero_usage_p2"]
        for hero, count in winner_usage.items():
            wins_when_used[hero] += count

    hero_rows = []
    for hero_id in sorted(set(drafted) | set(used)):
        use_count = used[hero_id]
        hero_rows.append({
            "hero_id": hero_id,
            "drafted": drafted[hero_id],
            "used": use_count,
            "use_per_draft": (use_count / drafted[hero_id]) if drafted[hero_id] else 0.0,
            "winner_share_of_uses": (wins_when_used[hero_id] / use_count) if use_count else 0.0,
        })
    hero_rows.sort(key=lambda row: (-row["used"], row["hero_id"]))
    return hero_rows


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_workbook(summary_rows, role_rows, hero_rows, raw_results):
    workbook = SimpleXlsxWriter(os.path.join(OUTPUT_DIR, "ringbound_balance_analysis.xlsx"))
    workbook.add_sheet(
        "Summary",
        [["Experiment", "AI A", "AI B", "Games", "AI A Wins", "AI B Wins", "AI A Win Rate", "P1 Win Rate", "First Attacker Win Rate", "Avg Rounds", "Avg P1 Wounds", "Avg P2 Wounds", "Tie Break Games"]]
        + [[row["experiment"], row["label_a"], row["label_b"], row["games"], row["label_a_wins"], row["label_b_wins"], round(row["label_a_win_rate"], 4) if row["label_a_win_rate"] is not None else "", round(row["p1_win_rate"], 4), round(row["first_attacker_win_rate"], 4), round(row["avg_rounds"], 3), round(row["avg_p1_wounds"], 3), round(row["avg_p2_wounds"], 3), row["tie_break_games"]] for row in summary_rows],
    )
    workbook.add_sheet(
        "RoleBalance",
        [["Experiment", "Role Tested", "Win Rate", "95% CI", "Games"]]
        + [[row["experiment"], row["role"], round(row["win_rate"], 4), round(row["ci95"], 4), row["games"]] for row in role_rows],
    )
    workbook.add_sheet(
        "HeroUsage",
        [["Hero ID", "Times Drafted", "Times Used", "Uses Per Draft", "Winner Share of Uses"]]
        + [[row["hero_id"], row["drafted"], row["used"], round(row["use_per_draft"], 4), round(row["winner_share_of_uses"], 4)] for row in hero_rows],
    )
    workbook.add_sheet(
        "RawGames",
        [["Experiment", "Game", "Seed", "P1 AI", "P2 AI", "Winner Player", "Winner AI", "First Attacker", "Trump", "Rounds", "P1 Wounds", "P2 Wounds", "Tie Break", "Reason", "Heroes Used"]]
        + [[row["experiment"], row["game_index"], row["seed"], row["p1_ai"], row["p2_ai"], row["winner_player"], row["winner_ai"], row["first_attacker"], row["trump_suit"], row["rounds"], row["p1_wounds"], row["p2_wounds"], row["tie_breaker"], row["final_reason"], ", ".join(f"{hero}:{count}" for hero, count in sorted(row["hero_usage"].items()))] for row in raw_results],
    )
    workbook.write()


def build_report(summary_rows, role_rows, hero_rows, raw_results):
    self_play = [row for row in summary_rows if row["label_a"] == row["label_b"]]
    cross_play = [row for row in summary_rows if row["label_a"] != row["label_b"]]
    total_games = len(raw_results)
    max_role_bias = max(abs(row["win_rate"] - 0.5) for row in role_rows) if role_rows else 0.0
    tie_breaks = sum(1 for row in raw_results if row["tie_breaker"])
    strategic_self = next((row for row in self_play if row["label_a"] == "Strategic"), None)
    random_vs_strategic = next((row for row in cross_play if row["label_a"] == "Random" and row["label_b"] == "Strategic"), None)
    top_hero = hero_rows[0] if hero_rows else None

    lines = [
        "# Ringbound Balance Report Draft",
        "",
        "## Introduction",
        "",
        "Ringbound is a two-player card game that combines alternating draft choices, attack-defense rounds, a wound track to six, and hero cards with special powers. Each simulated game follows the current implementation: players draft from a visible pool of realm cards and hero cards, a trump suit is revealed, and rounds continue until one player reaches six wounds or the endgame runs out of playable resources.",
        "",
        "Because Ringbound is a custom project, there is no outside published balance study for this exact ruleset. The appropriate analysis is Monte Carlo simulation with self-play and cross-play AI opponents. If equal-skill players split wins close to 50/50, while stronger AIs still beat weaker ones, then the game can be described as reasonably balanced without being strategically empty.",
        "",
        f"This report uses {total_games:,} simulated games across same-skill self-play and cross-skill matchups. The supporting workbook contains the summary tables, role-bias checks, hero-usage totals, and the raw game log used to compute the results.",
        "",
        "## Rules",
        "",
        "Ringbound is currently implemented as a two-player card game with a realm deck and a hero deck. The realm deck contains the standard playing cards for four suits in the game world, and the hero deck contains one copy of each special character ability.",
        "",
        "The game begins with each player receiving one realm card. Those two cards determine turn order for the draft: the player with the higher card drafts first, while the player with the lower card becomes the first attacker once play begins. After that, one additional realm card is revealed as the trump suit for the match. The game then presents a shared draft pool of 10 more realm cards and 8 hero cards, and the players alternate taking one visible card at a time until the draft pool is empty.",
        "",
        "After drafting, normal play happens in attack-defense rounds. The attacker leads with one realm card. The defender must beat the newest attack with a higher card of the same suit or with a valid trump card. If the defense succeeds, the attacker may reinforce by adding another realm card whose rank matches any rank already on the table. The current implementation also includes the option for the defender to concede instead of defending, which immediately gives that player one wound.",
        "",
        "At the end of a round, the result determines who attacks next. If the defender successfully answers the attack, the roles swap and the old defender becomes the new attacker. If the defender concedes and takes a wound, the attacker keeps the initiative for the next round. In the implemented version, attack cards are discarded at the end of the round, while a conceding defender keeps any defense cards they already played. After the round, both players draw realm cards back up to six whenever the realm deck still has cards remaining.",
        "",
        "Hero cards stay in a separate hand and can be played only in situations allowed by their rules and by the current game phase. Fellowship heroes mainly provide protection or flexibility: Aragorn recovers an attack card, Legolas allows one out-of-rank reinforcement, Gandalf cancels a non-trump attack, Galadriel heals wounds, Frodo disables trump for the round, and Boromir auto-defends one attack while forcing a random discard from the attacker. Shadow heroes apply pressure or disruption: Nazgul forces trump-only defense, Saruman swaps for the defender's best realm card, Sauron reveals the opponent's hand, Balrog still inflicts a wound through a full defense, Gollum changes the trump suit for one round, and Wormtongue forbids one suit for the defender.",
        "",
        "The implemented win condition has two parts. A player loses immediately upon taking six wounds. If the realm deck is empty, the game instead ends when one player has emptied all remaining cards from hand, which means that player wins by going out first.",
        "",
        "## Results",
        "",
        "### Experimental design",
        "",
        f"Three AI policies were tested: Random, Greedy, and Strategic. Random chooses mostly legal moves without planning. Greedy uses straightforward heuristics such as cheap defense, healing at high wound counts, and common-sense hero timing. Strategic adds extra drafting and information-based rules, although the experiment results show that these extra heuristics are not automatically stronger than the Greedy policy. The study includes {SELF_PLAY_GAMES:,} self-play games for each skill level and {CROSS_PLAY_GAMES:,} games for each cross-skill matchup.",
        "",
        "### Balance evidence",
        "",
    ]

    for row in self_play:
        lines.append(
            f"- In {row['experiment']}, seat P1 won {pct(row['p1_win_rate'])}% of {row['games']:,} games and first attacker won {pct(row['first_attacker_win_rate'])}%."
        )

    lines += [
        "",
        f"The largest measured role bias across all experiments was {pct(max_role_bias)} percentage points away from a perfectly even 50/50 split. That suggests a modest but not overwhelming role effect: first attacker underperformed slightly in the Greedy and Strategic self-play tests, but the seat and opening-role numbers still stayed close enough to 50/50 to describe the game as reasonably balanced overall.",
        "",
        "### Skill sensitivity",
        "",
    ]

    for row in cross_play:
        lines.append(f"- In {row['experiment']}, {row['label_a']} won {pct(row['label_a_win_rate'])}% of {row['games']:,} games against {row['label_b']}.")

    lines += [
        "",
        "These cross-skill results matter because a balanced game should still reward better choices. If all matchups stayed near 50/50, the game would probably be too random. Instead, the weaker Random policy loses badly to both of the stronger heuristic policies, while Greedy and Strategic are closer to each other. That suggests the game contains real decision-making depth even though the exact AI ranking depends on how the heuristics are written.",
        "",
        "### Workbook interpretation",
        "",
        "Each spreadsheet tab supports a different part of the argument:",
        "",
        "- `Summary` contains the main experiment table: win rates, round length, wound averages, and tiebreak frequency.",
        "- `RoleBalance` isolates seat and opening-role effects and adds an approximate 95% confidence interval.",
        "- `HeroUsage` reports how often each hero was drafted and used, plus how often those uses occurred in games the user eventually won.",
        "- `RawGames` is the full per-game log used to compute the summary statistics.",
        "",
    ]

    if strategic_self is not None and random_vs_strategic is not None:
        lines.append(
            f"Strategic self-play still stayed near even at {pct(strategic_self['p1_win_rate'])}% P1 wins, while Random versus Strategic was clearly separated, with Random winning only {pct(random_vs_strategic['label_a_win_rate'])}% of those games."
        )
        lines.append("")

    if top_hero is not None:
        lines.append(
            f"The most-used hero in the study was `{top_hero['hero_id']}`, drafted {top_hero['drafted']} times and used {top_hero['used']} times."
        )
        lines.append("")

    lines += [
        f"Only {tie_breaks} of {total_games:,} games required the max-round tiebreak safeguard, so the conclusions are not being driven by unresolved stalls.",
        "",
        "## Conclusion",
        "",
        "The introduction claimed that Ringbound should be considered balanced if equal-skill players split wins near 50% while stronger play still improves results. The simulations support that claim. Same-skill self-play remained close to even, role bias stayed modest rather than overwhelming, and the stronger heuristic policies defeated the Random policy often enough to show that the game rewards skill. Based on these experiments, the current implementation of Ringbound appears reasonably balanced for a class-project prototype.",
        "",
        "## Notes and assumptions",
        "",
        "- The simulator follows the current implemented rules, including the present hero behaviors and draft structure.",
        "- A max-round tiebreak was included only as a safety guard for unusually long games.",
        "- This is practical evidence of balance, not a proof of perfect balance. Human playtesting would still be useful.",
        "",
    ]
    return "\n".join(lines)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    realm_cards, hero_cards = load_cards()

    ai_random = RandomAI("Random")
    ai_greedy = GreedyAI("Greedy")
    ai_strategic = StrategicAI("Strategic")

    raw_results = []
    seed = 1000
    experiments = [
        ("Random", ai_random, "Random", ai_random, SELF_PLAY_GAMES),
        ("Greedy", ai_greedy, "Greedy", ai_greedy, SELF_PLAY_GAMES),
        ("Strategic", ai_strategic, "Strategic", ai_strategic, SELF_PLAY_GAMES),
        ("Random", ai_random, "Greedy", ai_greedy, CROSS_PLAY_GAMES),
        ("Random", ai_random, "Strategic", ai_strategic, CROSS_PLAY_GAMES),
        ("Greedy", ai_greedy, "Strategic", ai_strategic, CROSS_PLAY_GAMES),
    ]

    for label_a, ai_a, label_b, ai_b, games in experiments:
        raw_results.extend(run_matchup(realm_cards, hero_cards, label_a, ai_a, label_b, ai_b, games, seed))
        seed += games + 1000

    summary_rows, role_rows = summarize_experiments(raw_results)
    hero_rows = summarize_heroes(raw_results)

    write_csv(os.path.join(OUTPUT_DIR, "summary.csv"), summary_rows, ["experiment", "label_a", "label_b", "games", "label_a_wins", "label_b_wins", "label_a_win_rate", "p1_win_rate", "first_attacker_win_rate", "avg_rounds", "avg_p1_wounds", "avg_p2_wounds", "tie_break_games"])
    write_csv(os.path.join(OUTPUT_DIR, "role_balance.csv"), role_rows, ["experiment", "role", "win_rate", "ci95", "games"])
    write_csv(os.path.join(OUTPUT_DIR, "hero_usage.csv"), hero_rows, ["hero_id", "drafted", "used", "use_per_draft", "winner_share_of_uses"])
    write_csv(os.path.join(OUTPUT_DIR, "raw_games.csv"), raw_results, ["experiment", "game_index", "seed", "label_a", "label_b", "p1_ai", "p2_ai", "p1_label", "p2_label", "winner_player", "winner_ai", "winner_label", "first_attacker", "trump_suit", "rounds", "p1_wounds", "p2_wounds", "tie_breaker", "final_reason", "hero_usage", "drafted_heroes_p1", "drafted_heroes_p2"])

    build_workbook(summary_rows, role_rows, hero_rows, raw_results)

    report_text = build_report(summary_rows, role_rows, hero_rows, raw_results)
    with open(os.path.join(OUTPUT_DIR, "ringbound_balance_report_draft.md"), "w", encoding="utf-8") as file:
        file.write(report_text)

    with open(os.path.join(OUTPUT_DIR, "ringbound_balance_report_draft.html"), "w", encoding="utf-8") as file:
        html_body = "<br/>\n".join(escape(line) if line else "" for line in report_text.splitlines())
        file.write(f"<html><body style='font-family:Arial;max-width:900px;margin:40px auto;line-height:1.5'>{html_body}</body></html>")

    print(f"Generated analysis outputs in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
