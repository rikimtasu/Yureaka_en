#!/usr/bin/env python3
"""Generate curated canonical glossary files (`terms.json`, `glossary_galtransl.txt`, `style_guide.md`)
combining VNDB v28712 official character names, all 66 speaker-box names, all 107 TIPS terms,
and key Jindou/Tenju world-building & ruby-annotated terms.
"""
from __future__ import annotations

import json
import pathlib

WORKSPACE = pathlib.Path(r"d:\Documents\yureaka_en")
GLOSS_DIR = WORKSPACE / "work" / "glossary"

# 1. Official VNDB v28712 Characters + Minor Named Characters
CHARACTERS = [
    # Main / Heroines (VNDB v28712)
    {"jp": "村垣伊織", "en": "Muragaki Iori", "note": "Protagonist (VNDB c91892), male, homeroom sub-teacher"},
    {"jp": "村垣", "en": "Muragaki", "note": "Surname of Muragaki Iori"},
    {"jp": "伊織", "en": "Iori", "note": "Given name of Muragaki Iori (male)"},
    {"jp": "朱雀院紅葉", "en": "Suzakuin Momiji", "note": "Heroine (VNDB c91890), female"},
    {"jp": "朱雀院", "en": "Suzakuin", "note": "Surname of Suzakuin family (Momiji, Miyako, Tsubaki)"},
    {"jp": "紅葉", "en": "Momiji", "note": "Given name of Suzakuin Momiji (female)"},
    {"jp": "風嶺雪月花", "en": "Kazamine Setsugekka", "note": "Heroine (VNDB c91888), female"},
    {"jp": "風嶺", "en": "Kazamine", "note": "Surname of Kazamine family (Setsugekka, Keisetsu)"},
    {"jp": "雪月花", "en": "Setsugekka", "note": "Given name of Kazamine Setsugekka (female)"},
    {"jp": "九鬼旭", "en": "Kuki Asahi", "note": "Heroine (VNDB c91889), female"},
    {"jp": "九鬼", "en": "Kuki", "note": "Surname of Kuki family (Asahi, Takahisa)"},
    {"jp": "旭", "en": "Asahi", "note": "Given name of Kuki Asahi (female)"},
    {"jp": "十部梨々夢", "en": "Tobe Ririmu", "note": "Heroine (VNDB c91891), female"},
    {"jp": "十部", "en": "Tobe", "note": "Surname of Tobe Ririmu"},
    {"jp": "梨々夢", "en": "Ririmu", "note": "Given name of Tobe Ririmu (female)"},
    {"jp": "リリィ", "en": "Lily", "note": "Nickname for Tobe Ririmu"},
    # Side Characters (VNDB v28712)
    {"jp": "天王寺ヴィクトリア", "en": "Tennouji Victoria", "note": "Side character (VNDB c92307), female, reigning Toujinegi"},
    {"jp": "天王寺", "en": "Tennouji", "note": "Surname of Tennouji Victoria"},
    {"jp": "ヴィクトリア", "en": "Victoria", "note": "Given name of Tennouji Victoria (female)"},
    {"jp": "ヴィッキー", "en": "Vicky", "note": "Nickname for Tennouji Victoria"},
    {"jp": "源雫", "en": "Minamoto Shizuku", "note": "Side character (VNDB c92308), female, Victoria's second/attendant"},
    {"jp": "源", "en": "Minamoto", "note": "Surname of Minamoto Shizuku (also TIPS d0015 Minamoto clan)"},
    {"jp": "雫", "en": "Shizuku", "note": "Given name of Minamoto Shizuku (female)"},
    {"jp": "荒川園美", "en": "Arakawa Sonomi", "note": "Side character (VNDB c92309), female"},
    {"jp": "荒川", "en": "Arakawa", "note": "Surname of Arakawa Sonomi"},
    {"jp": "園美", "en": "Sonomi", "note": "Given name of Arakawa Sonomi (female)"},
    {"jp": "風嶺蛍雪", "en": "Kazamine Keisetsu", "note": "Side character (VNDB c92310), female, Setsugekka's relative/client"},
    {"jp": "蛍雪", "en": "Keisetsu", "note": "Given name of Kazamine Keisetsu (female)"},
    {"jp": "ケイちゃん", "en": "Kei-chan", "note": "Nickname for Kazamine Keisetsu"},
    {"jp": "佐々木巫琴", "en": "Sasaki Mikoto", "note": "Side character (VNDB c65005), female, academy doctor"},
    {"jp": "佐々木", "en": "Sasaki", "note": "Surname of Sasaki Mikoto"},
    {"jp": "巫琴", "en": "Mikoto", "note": "Given name of Sasaki Mikoto (female)"},
    {"jp": "朱雀院都子", "en": "Suzakuin Miyako", "note": "Side character (VNDB c92970), female"},
    {"jp": "都子", "en": "Miyako", "note": "Given name of Suzakuin Miyako (female)"},
    {"jp": "朱雀院椿", "en": "Suzakuin Tsubaki", "note": "Side character (VNDB c92971), female"},
    {"jp": "椿", "en": "Tsubaki", "note": "Given name of Suzakuin Tsubaki (female)"},
    {"jp": "九鬼隆久", "en": "Kuki Takahisa", "note": "Side character (VNDB c94719), male (also TIPS d0028)"},
    {"jp": "隆久", "en": "Takahisa", "note": "Given name of Kuki Takahisa (male)"},
    {"jp": "中邑さくら", "en": "Nakamura Sakura", "note": "Side character (VNDB c157028), female (also TIPS d0026)"},
    {"jp": "中邑", "en": "Nakamura", "note": "Surname of Nakamura Sakura"},
    {"jp": "さくら", "en": "Sakura", "note": "Given name of Nakamura Sakura (female)"},
    {"jp": "佐々鳴子", "en": "Sassa Naruko", "note": "Side character (VNDB c157029), female"},
    {"jp": "佐々", "en": "Sassa", "note": "Surname of Sassa Naruko"},
    {"jp": "鳴子", "en": "Naruko", "note": "Given name of Sassa Naruko (female)"},
    # Additional recurring named characters in script / TIPS
    {"jp": "朝霧ミドリ", "en": "Asagiri Midori", "note": "Recurring character, JGSDF Major (三等陸佐, TIPS d0040)"},
    {"jp": "柾胤", "en": "Masatane", "note": "Named character (also TIPS d0033)"},
    {"jp": "柾盛", "en": "Masamori", "note": "Named historical/family figure"},
    {"jp": "凛", "en": "Rin", "note": "Minor named character"},
    {"jp": "紗月", "en": "Satsuki", "note": "Referenced character (TIPS d0059)"},
    {"jp": "槇之丞", "en": "Makinojou", "note": "Named historical/martial figure"},
    {"jp": "嶺庵", "en": "Ryouan", "note": "Named figure"},
    {"jp": "ジェームズ・主水", "en": "James Mondo", "note": "Parody/referenced name (TIPS d0047)"},
    {"jp": "ヨリシロくん", "en": "Yorishiro-kun", "note": "Mascot/device character (TIPS d0085)"},
]

# 2. All 66 exact speaker-box name mappings (for `name` field consistency)
SPEAKER_NAMES = {
    "伊織": "Iori",
    "雪月花": "Setsugekka",
    "紅葉": "Momiji",
    "旭": "Asahi",
    "梨々夢": "Ririmu",
    "蛍雪": "Keisetsu",
    "ヴィクトリア": "Victoria",
    "園美": "Sonomi",
    "雫": "Shizuku",
    "巫琴": "Mikoto",
    "都子": "Miyako",
    "佐々鳴子": "Sassa Naruko",
    "中邑さくら": "Nakamura Sakura",
    "隆久": "Takahisa",
    "立会人": "Umpire",
    "椿": "Tsubaki",
    "朝霧ミドリ": "Asagiri Midori",
    "？？？": "???",
    "店長": "Manager",
    "柾胤": "Masatane",
    "女の子": "Girl",
    "凛": "Rin",
    "女子生徒Ａ": "Female Student A",
    "女子生徒Ｂ": "Female Student B",
    "師匠": "Master",
    "ナレーター": "Narrator",
    "観客Ａ": "Spectator A",
    "ヨリシロくん": "Yorishiro-kun",
    "全員": "Everyone",
    "女子生徒": "Female Student",
    "観客Ｂ": "Spectator B",
    "技巧科の生徒": "Technical Division Student",
    "梨々夢の父": "Ririmu's Father",
    "道場の後輩Ａ": "Dojo Junior A",
    "店員": "Clerk",
    "メイド": "Maid",
    "教師": "Teacher",
    "アナウンサー": "Announcer",
    "秘書": "Secretary",
    "蛍雪の部下": "Keisetsu's Subordinate",
    "観客Ｃ": "Spectator C",
    "観客Ｄ": "Spectator D",
    "警察官": "Police Officer",
    "みんな": "Everyone",
    "刃道トレーナー": "Jindou Trainer",
    "場内アナウンス": "PA Announcement",
    "旭＆梨々夢": "Asahi & Ririmu",
    "梨々夢の母": "Ririmu's Mother",
    "琴の先生": "Koto Instructor",
    "男の子": "Boy",
    "観客たち": "Spectators",
    "観客Ｅ": "Spectator E",
    "観客Ｆ": "Spectator F",
    "道場の後輩Ｂ": "Dojo Junior B",
    "雪月花＆旭＆梨々夢": "Setsugekka, Asahi & Ririmu",
    "雪月花＆梨々夢": "Setsugekka & Ririmu",
    "雪月花＆紅葉": "Setsugekka & Momiji",
    "ヴィクトリア＆雪月花": "Victoria & Setsugekka",
    "学園システム": "Academy System",
    "旭＆紅葉": "Asahi & Momiji",
    "親戚Ａ": "Relative A",
    "親戚Ｂ": "Relative B",
    "運転手": "Driver",
    "雪月花＆園美": "Setsugekka & Sonomi",
    "雪月花＆都子": "Setsugekka & Miyako",
    "雫＆紅葉": "Shizuku & Momiji",
}

# 3. World-building, Organizations, Locations, Blade Arts & Key TIPS Terms
TERMS = [
    # Title & Setting
    {"jp": "紅月ゆれる恋あかり", "en": "Akatsuki Yureru Koi Akari", "cat": "title", "note": "Official VNDB romaji title"},
    {"jp": "叢雲学園", "en": "Murakumo Academy", "cat": "location", "note": "TIPS d0000; Jindou academy"},
    {"jp": "住吉学府", "en": "Sumiyoshi Academic Island", "cat": "location", "note": "Artificial island in Osaka Bay"},
    {"jp": "篁組", "en": "Takamura Class", "cat": "organization", "note": "Iori's homeroom class (篁=Takamura)"},
    {"jp": "武芸科", "en": "Martial Arts Division", "cat": "organization", "note": "TIPS d0006"},
    {"jp": "技巧科", "en": "Technical Division", "cat": "organization", "note": "TIPS d0007"},
    {"jp": "主計科", "en": "Quartermaster Division", "cat": "organization", "note": "TIPS d0008"},
    {"jp": "叢雲演武祭", "en": "Murakumo Martial Festival", "cat": "event", "note": "TIPS d0009; annual academy tournament"},
    {"jp": "天呪特科群『武蔵』", "en": 'Tenju Special Forces Group "Musashi"', "cat": "organization", "note": "TIPS d0002; JGSDF special unit"},
    {"jp": "武蔵", "en": "Musashi", "cat": "organization", "note": "Short for Tenju Special Forces Group Musashi"},
    {"jp": "朱鴉", "en": "Akegarasu", "cat": "organization", "note": "JGSDF special unit (reading: あけがらす)"},
    {"jp": "神所霊庁", "en": "Spirit Agency", "cat": "organization", "note": "TIPS d0106; government supernatural bureau"},
    {"jp": "佩刀護身会", "en": "Sword-Bearing Self-Defense Association", "cat": "organization", "note": "TIPS d0011"},
    {"jp": "朱雀院家", "en": "Suzakuin Family", "cat": "organization", "note": "TIPS d0010"},
    {"jp": "風嶺家", "en": "Kazamine Family", "cat": "organization", "note": "TIPS d0030"},
    {"jp": "風嶺グループ", "en": "Kazamine Group", "cat": "organization", "note": "TIPS d0038"},
    {"jp": "大上家", "en": "Ookami Family", "cat": "organization", "note": "TIPS d0076 (reading: おおかみけ)"},
    {"jp": "三城家", "en": "Sanjou Family", "cat": "organization", "note": "TIPS d0087"},
    {"jp": "豊原狐平堂", "en": "Toyohara Konpeidou", "cat": "location", "note": "TIPS d0095; shop name"},
    {"jp": "堺の鮮魚市場", "en": "Sakai Fresh Fish Market", "cat": "location", "note": "TIPS d0053"},
    # Core Power System & Lore
    {"jp": "刃道", "en": "Jindou", "cat": "lore", "note": "TIPS d0088; Way of the Blade competitive martial art"},
    {"jp": "刀仕禰宜", "en": "Toujinegi", "cat": "title", "note": "TIPS d0012; champion title at Murakumo Academy"},
    {"jp": "介添人", "en": "Second", "cat": "role", "note": "TIPS d0014; match attendant/second (like Victoria's Shizuku)"},
    {"jp": "天呪", "en": "Tenju", "cat": "lore", "note": "TIPS d0004; supernatural spirit arts/curses"},
    {"jp": "折紙", "en": "Origami", "cat": "lore", "note": "TIPS d0003; spiritual talisman/fold-paper"},
    {"jp": "霊式具装", "en": "Spirit-Type Armament", "cat": "lore", "note": "TIPS d0019"},
    {"jp": "霊式機巧デバイス", "en": "Spirit-Type Mechanical Device", "cat": "lore", "note": "TIPS d0105"},
    {"jp": "バリアジャケット", "en": "Barrier Jacket", "cat": "lore", "note": "TIPS d0086; protective Jindou outfit"},
    {"jp": "精神感応係数", "en": "Mental Resonance Coefficient", "cat": "lore", "note": "TIPS d0056"},
    {"jp": "魂来", "en": "Tamukai", "cat": "lore", "note": "TIPS d0057; spirit summoning/channeling (reading: たむかい)"},
    {"jp": "審神者", "en": "Saniwa", "cat": "lore", "note": "TIPS d0058; spirit medium/diviner"},
    {"jp": "戦人", "en": "Ikusabito", "cat": "lore", "note": "TIPS d0078; warrior spirit/fighter (reading: いくさびと)"},
    {"jp": "化妖", "en": "Keyou", "cat": "lore", "note": "TIPS d0079; apparition/demonized spirit (reading: けよう)"},
    {"jp": "半妖", "en": "Hanyou", "cat": "lore", "note": "TIPS d0089; half-apparition"},
    {"jp": "鬼女", "en": "Kijo", "cat": "lore", "note": "TIPS d0048; oni woman / demoness (reading: おにおんな)"},
    {"jp": "魂鋼", "en": "Tamahagane", "cat": "lore", "note": "Spirit steel / jewel steel"},
    {"jp": "祝詞", "en": "Norito", "cat": "lore", "note": "TIPS d0090; Shinto ritual prayer/incantation"},
    {"jp": "ＨＲ", "en": "HR", "cat": "tech", "note": "TIPS d0001; Holographic Reality"},
    {"jp": "ホログラフィックリアリティ", "en": "Holographic Reality", "cat": "tech", "note": "Full expansion of HR"},
    {"jp": "単分子コーティング", "en": "Monomolecular Coating", "cat": "tech", "note": "TIPS d0072"},
    # Sword Styles & Techniques
    {"jp": "天元齊命流", "en": "Tengen Saimei-ryuu", "cat": "martial_art", "note": "TIPS d0034; Iori's sword style"},
    {"jp": "天然理心流", "en": "Tennen Rishin-ryuu", "cat": "martial_art", "note": "TIPS d0067"},
    {"jp": "三島流格闘術", "en": "Mishima-ryuu Martial Arts", "cat": "martial_art", "note": "TIPS d0024"},
    {"jp": "三島流", "en": "Mishima-ryuu", "cat": "martial_art", "note": "Short for Mishima-ryuu Martial Arts"},
    {"jp": "神眼極手", "en": "Shingan no Kiwamete", "cat": "technique", "note": "TIPS d0020; Divine Eye Ultimate Hand"},
    {"jp": "紅葉狩", "en": "Momijigari", "cat": "technique", "note": "TIPS d0021; Momiji's technique"},
    {"jp": "八紘我観", "en": "World is Mine", "cat": "technique", "note": "TIPS d0029; Ririmu's technique (ruby: ワールド・イズ・マイン)"},
    {"jp": "胡蝶爛漫", "en": "Butterfly Effect", "cat": "technique", "note": "Ruby reading: バタフライ・エフェクト"},
    {"jp": "横溢一閃", "en": "Ouitsu Issen", "cat": "technique", "note": "TIPS d0035; Overflowing Flash"},
    {"jp": "雷霆一閃", "en": "Raitei Issen", "cat": "technique", "note": "Thunderbolt Flash"},
    {"jp": "炎虎猛巴斬", "en": "Enko Mouhazan", "cat": "technique", "note": "Blazing Tiger Slash"},
    {"jp": "朱雀演舞", "en": "Suzaku Enbu", "cat": "technique", "note": "Vermilion Bird Dance"},
    {"jp": "波濤乱舞", "en": "Hatou Ranbu", "cat": "technique", "note": "Surging Wave Dance"},
    {"jp": "峰打頂肘", "en": "Houda Chouchuu", "cat": "technique", "note": "Martial strike"},
    {"jp": "破城掌", "en": "Hajoushou", "cat": "technique", "note": "Castle-Breaker Palm"},
    {"jp": "金剛砲", "en": "Kongouhou", "cat": "technique", "note": "Vajra Cannon"},
    {"jp": "剛砲", "en": "Gouhou", "cat": "technique", "note": "Heavy Cannon"},
    {"jp": "天山靠", "en": "Tenzankou", "cat": "technique", "note": "Shoulder ram technique"},
    {"jp": "万絶", "en": "Banzetsu", "cat": "technique", "note": "Sword technique"},
    {"jp": "穿火", "en": "Ugachibi", "cat": "technique", "note": "Piercing Flame"},
    {"jp": "銀楯", "en": "Ginjun", "cat": "technique", "note": "Silver Shield"},
    {"jp": "炎牙", "en": "Enga", "cat": "technique", "note": "Flame Fang"},
    {"jp": "枝薙", "en": "Edanagi", "cat": "technique", "note": "Branch Sweep"},
    {"jp": "地走", "en": "Chibashiri", "cat": "technique", "note": "Ground Runner"},
    {"jp": "湧流", "en": "Wakinagashi", "cat": "technique", "note": "Spring Flow"},
    {"jp": "燕長光", "en": "Tsubakuro Nagamitsu", "cat": "weapon", "note": "Named sword"},
    {"jp": "縮地", "en": "Shukuchi", "cat": "technique", "note": "TIPS d0025; shrunk-earth footwork"},
    {"jp": "居合", "en": "Iai", "cat": "technique", "note": "TIPS d0091; quick-draw swordsmanship"},
    {"jp": "諸法無我", "en": "Shohou Muga", "cat": "lore", "note": "TIPS d0062; Buddhist principle / state of selflessness"},
    {"jp": "甲型", "en": "Type Kou", "cat": "form", "note": "Heavenly Stem form 1 (きのえがた)"},
    {"jp": "丙型", "en": "Type Hinoe", "cat": "form", "note": "Heavenly Stem form 3 (ひのえがた)"},
    {"jp": "丁型", "en": "Type Hinoto", "cat": "form", "note": "Heavenly Stem form 4 (ひのとがた)"},
    {"jp": "戊型", "en": "Type Tsuchinoe", "cat": "form", "note": "Heavenly Stem form 5 (つちのえがた)"},
    {"jp": "己型", "en": "Type Tsuchinoto", "cat": "form", "note": "Heavenly Stem form 6 (つちのとがた)"},
    {"jp": "庚型", "en": "Type Kanoe", "cat": "form", "note": "Heavenly Stem form 7 (かのえがた)"},
    {"jp": "辛型", "en": "Type Kanoto", "cat": "form", "note": "Heavenly Stem form 8 (かのとがた)"},
    {"jp": "壬型", "en": "Type Mizunoe", "cat": "form", "note": "Heavenly Stem form 9 (みずのえがた)"},
    {"jp": "癸型", "en": "Type Mizunoto", "cat": "form", "note": "Heavenly Stem form 10 (みずのとがた)"},
    # Cultural / Parody / Misc TIPS terms
    {"jp": "トレッター", "en": "Tretter", "cat": "misc", "note": "TIPS d0023; Twitter parody"},
    {"jp": "ポシェモン", "en": "Pochemon", "cat": "misc", "note": "TIPS d0060; Pokemon parody"},
    {"jp": "スザクハイパードラァイ", "en": "Suzaku Hyper Dry", "cat": "misc", "note": "TIPS d0054; beer parody"},
    {"jp": "Ｕ・キクイチモンジソード改", "en": "Ultimate Kikuichimonji Sword Kai", "cat": "weapon", "note": "TIPS d0068"},
    {"jp": "ＳＵＭＩＴＡＮＩ", "en": "SUMITANI", "cat": "misc", "note": "TIPS d0069; brand parody"},
    {"jp": "いけいけオキタくん", "en": "Go-Go Okita-kun", "cat": "misc", "note": "TIPS d0016"},
    {"jp": "ビミヤン", "en": "Bimiyan", "cat": "misc", "note": "TIPS d0045; Bamiyan restaurant parody"},
    {"jp": "村垣チャーハン", "en": "Muragaki Fried Rice", "cat": "misc", "note": "TIPS d0050"},
    {"jp": "理想郷", "en": "Arcadia", "cat": "lore", "note": "TIPS d0036 (ruby: アルカディア)"},
    {"jp": "悪鬼討滅", "en": "Demon Extermination", "cat": "lore", "note": "TIPS d0080"},
    {"jp": "道場破り", "en": "Dojo Crashing", "cat": "martial_art", "note": "TIPS d0066"},
    {"jp": "プロリーグ", "en": "Pro League", "cat": "organization", "note": "TIPS d0093"},
]


def main() -> int:
    GLOSS_DIR.mkdir(parents=True, exist_ok=True)
    raw = json.loads((GLOSS_DIR / "glossary_raw_candidates.json").read_text(encoding="utf-8"))

    # Save structured terms.json
    terms_doc = {
        "schema": "yureaka-en-glossary/1",
        "reference": "https://vndb.org/v28712",
        "title_jp": "紅月ゆれる恋あかり",
        "title_en": "Akatsuki Yureru Koi Akari",
        "conventions": {
            "honorifics": "keep",
            "ruby": "drop",
            "name_order": "Family Given for full formal names (matching VNDB), Given name in casual speech/speaker box",
        },
        "characters": CHARACTERS,
        "speaker_names": SPEAKER_NAMES,
        "terms": TERMS,
        "tips_csv_reference": raw["tips_terms"],
    }
    (GLOSS_DIR / "terms.json").write_text(json.dumps(terms_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Save GalTransl / LLM tab-separated glossary (`JP\tEN\tNote`)
    lines: list[str] = [
        "# 紅月ゆれる恋あかり (Akatsuki Yureru Koi Akari) EN Glossary",
        "# Reference: https://vndb.org/v28712",
        "# Format: JP<TAB>EN<TAB>Note",
        "",
        "# --- Characters (VNDB v28712 + Script) ---",
    ]
    seen_jp: set[str] = set()
    for c in CHARACTERS:
        if c["jp"] not in seen_jp:
            lines.append(f"{c['jp']}\t{c['en']}\t{c['note']}")
            seen_jp.add(c["jp"])
    lines.append("")
    lines.append("# --- Speaker Box Labels ---")
    for jp, en in SPEAKER_NAMES.items():
        if jp not in seen_jp:
            lines.append(f"{jp}\t{en}\tSpeaker label")
            seen_jp.add(jp)
    lines.append("")
    lines.append("# --- World-Building, Factions, Martial Arts & TIPS ---")
    for t in TERMS:
        if t["jp"] not in seen_jp:
            lines.append(f"{t['jp']}\t{t['en']}\t[{t['cat']}] {t['note']}")
            seen_jp.add(t["jp"])
    (GLOSS_DIR / "glossary_galtransl.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Save style_guide.md for LLM prompt injection
    style_md = """# Translation Style Guide — 紅月ゆれる恋あかり (*Akatsuki Yureru Koi Akari*)

## 1. Core Rules
- **Natural, idiomatic English** preserving character voice, comedic timing, and combat intensity.
- **Honorifics — KEEP**: Retain Japanese honorifics (`-san`, `-kun`, `-chan`, `-sama`, `-senpai`, `-sensei`, `Sensei`, `Onii-chan`, `Onee-san`, etc.) naturally in English (e.g., `Muragaki-sensei`, `Victoria-san`, `Asahi-chan`, `Suzakuin-san`).
- **Ruby / Furigana — DROP**: All `<r...>...</r>` tags are already stripped in `gt_input/`. Do **not** add parenthetical Japanese readings unless required for clarity.
- **Name Order & Reference**: Follow [VNDB v28712](https://vndb.org/v28712) spellings in `terms.json` / `glossary_galtransl.txt` (`Muragaki Iori`, `Suzakuin Momiji`, `Kazamine Setsugekka`, `Kuki Asahi`, `Tobe Ririmu`, `Tennouji Victoria`, `Minamoto Shizuku`, `Arakawa Sonomi`, `Kazamine Keisetsu`, `Sasaki Mikoto`, `Suzakuin Miyako`, `Suzakuin Tsubaki`, `Kuki Takahisa`, `Nakamura Sakura`, `Sassa Naruko`).

## 2. Mandatory Tag & Format Preservation
- Keep the **exact JSON array length**, **record order**, and `"name"` keys of every file in `gt_input/`.
- **Preserve all inline engine tags verbatim** around the translated equivalent:
  - `<dNNNN>...</d>` — clickable TIPS glossary links (105 occurrences). Wrap the translated term inside the exact same `<dNNNN>...</d>` tag!
  - `<sN>...</sN>` — font size override (19 occurrences).
  - `<center>...</center>` — centered narration/headings (4 occurrences).
  - `<c#RRGGBB #RRGGBB>...</c>` — text color tags (if present).
- **Line Wrapping**: Do **not** manually insert `<br>` for normal dialogue wrapping — `tools/text_inject.py` automatically wraps English at pixel-accurate word boundaries using `Barlow Semi Condensed Medium` (24px, ~83 chars/line). Only use `<br>` or `\\n` when an intentional paragraph break is needed (keep UI tooltip `<br>` in `000_ui_system.json`).
- **Box Length Budget**: Target **<= 240 English characters** per dialogue box (~3 lines × ~80 chars). Avoid overly verbose expansions that exceed 3 lines.
- **Dialogue Quotes**: Replace Japanese quotes `「...」` with standard ASCII double quotes `"..."`, internal thoughts `（...）` with parentheses `(...)` or italics-free thoughts matching your style, and `『...』` with single quotes `'...'` or `"..."`.
- **ASCII Punctuation**: Standard ASCII (`"`, `'`, `--`, `...`) is preferred; `text_inject.py` automatically normalizes curly quotes, em-dashes, and ellipses to CP932/ASCII-safe characters.
"""
    (GLOSS_DIR / "style_guide.md").write_text(style_md, encoding="utf-8")
    print(f"Wrote terms.json ({len(CHARACTERS)} chars, {len(SPEAKER_NAMES)} speakers, {len(TERMS)} terms), glossary_galtransl.txt ({len(seen_jp)} unique entries), and style_guide.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
