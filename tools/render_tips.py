#!/usr/bin/env python3
"""Render all 210 localized English TIPS cards (105 Big 621x370 + 105 Small 261x147)
into `work/pgd_overrides/TIPSxxxxB.PGD` and `TIPSxxxxS.PGD`.

Cleanly reconstructs zero-ghosting blank templates from original TIPS0000B/S preserving exact
header gradients, geometric borders, and 'Explanation' watermark, then renders crisp English
title + body text using Barlow Semi Condensed Medium.
"""
from __future__ import annotations

import pathlib
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from softpal_pac import read_pac2_member  # noqa: E402
from softpal_pgd import decode_pgd, encode_pgd  # noqa: E402

WORKSPACE = pathlib.Path(r"d:\Documents\yureaka_en")
GAME_DIR = pathlib.Path(r"d:\Video_Game\Visual Novel\CRYSTALiA\紅月ゆれる恋あかり")
FONT_MED = WORKSPACE / "assets" / "fonts" / "BarlowSemiCondensed-Medium.ttf"
FONT_FIRA = WORKSPACE / "assets" / "fonts" / "FiraSansCondensed-Regular.ttf"

# Complete 105 TIPS entries (matching tips.pac: 0000..0103 + 0106)
# Format: num -> (English Title, Full Big Card Description, Concise Small Popup Summary)
TIPS_DATA: dict[int, tuple[str, str, str]] = {
    0: (
        "Murakumo Academy",
        "The only academy in Japan--and the world--dedicated exclusively to teaching Jindou. Operating as a full boarding school, the academy oversees nearly every aspect of student life, though students may roam freely across the entire island campus. Badly injured students spend the weekend in medical recovery pods before returning Monday, inspiring the motto: 'Don't get hurt if you want to play.' Famous for its annual Murakumo Martial Festival.",
        "The world's sole academy dedicated to teaching Jindou. A full boarding school overseeing student life across the island campus.",
    ),
    1: (
        "HR (Holographic Reality)",
        "Technology that projects three-dimensional light holograms into real space, or the holograms themselves. Commonly fixed to coordinates as signage, HR can also track moving targets--even projecting clothing directly over a person's body. A staple tool among cosplayers.",
        "Technology projecting 3D holograms into real space. Can track moving targets and even project outfits over the body.",
    ),
    2: (
        'Tenju Special Forces Group "Musashi"',
        "A highly secretive unit within the JGSDF whose members and operations remain classified. It includes many part-time operatives and reservists, some of whom are active pro Jindou athletes. Its unusually freewheeling culture allows frequent external dispatches--known colloquially as 'errands'--like the protagonist's current assignment.",
        "A secretive JGSDF special unit whose roster and missions are classified, including reservists and active pro athletes.",
    ),
    3: (
        "Origami",
        "Official name: Spirit-Type Mechanical Blade Origami. Commonly called 'Origami.' A mechanized sword-and-scabbard set forged from Tamahagane so fighters can channel supernatural abilities with ease. Serves as the standard weapon in Jindou.",
        "Short for Spirit-Type Mechanical Blade Origami. A mechanized Tamahagane sword-and-scabbard set used in Jindou.",
    ),
    4: (
        "Tenju",
        "A general term for supernatural abilities that convert mental energy into physical phenomena, typically channeled through a resonance catalyst such as Tamahagane. Core effects include physical enhancement and invisible protective VF Fields. Power varies greatly by individual and catalyst compatibility; historically known as 'divine arts.'",
        "Supernatural abilities turning mental energy into physical force via Tamahagane catalysts, granting physical boosts and VF Fields.",
    ),
    5: (
        "Company-Scale",
        "An army organizational unit of roughly 100 to 200 soldiers. A single Tenju Special Forces operative is rumored to match an entire regular infantry company--slicing through lines faster than the eye can follow while their Barrier Jacket shrugs off rifle fire and direct mortar hits. Since no direct battle has occurred as of 20XX, this remains unproven.",
        "An army unit of ~100-200 troops. One Tenju Special Forces operative is rumored to rival an entire regular company.",
    ),
    6: (
        "Martial Arts Division",
        "The division training Jindou swordsmen. Admission requires aptitude for wielding an Origami and a minimum Mental Resonance Coefficient just to sit the entrance exam. Teaches combat techniques, weapon handling, and Tenju activation needed for Origami duels.",
        "The division training Jindou fighters. Requires Origami aptitude and a high Mental Resonance Coefficient to enroll.",
    ),
    7: (
        "Technical Division",
        "The division training Jindou bladesmiths, including students capable of forging true spirit blades. Like Martial Arts, admission demands a high resonance score and comparable aptitude. Offers a rich research-focused curriculum in science, engineering, armament design, tactics, and ability studies.",
        "The division training Jindou bladesmiths and engineers. Focuses on science, armament design, tactics, and ability research.",
    ),
    8: (
        "Quartermaster Division",
        "The division training management and operations specialists for the Jindou world. Built for students without Martial Arts or Technical aptitude who still pursue Jindou-related careers--handling Tamahagane procurement, operator work, sales, and PR to back up fighters and smiths. Many Sword-Bearing Self-Defense Association members hail from here.",
        "The division training Jindou operations, procurement, operator, and PR staff who support fighters and bladesmiths.",
    ),
    9: (
        "Murakumo Martial Festival",
        "Murakumo Academy's biggest annual summer event, broadcast nationwide--so famous that people call Koshien and the Festival the twin icons of summer. Also a sacred rite honoring the gods, attended by the Defense Minister and head priests from Kashima and Atsuta Shrines for sword dedications. Its climax pits the academy's top qualifiers against each other for the championship.",
        "Murakumo Academy's famous summer tournament, broadcast nationwide and held alongside sacred Shinto sword-dedication rites.",
    ),
    10: (
        "Suzakuin Family",
        "A martial clan dating back to the Warring States period. After WWII, Suzakuin Ryouan founded the Sword-Bearing Self-Defense Association, laying the cornerstone of modern warrior culture. Still produces major Jindou figures today, with high expectations placed on the four main-branch sisters: Momiji, Nadeshiko, Miyako, and Tsubaki.",
        "A historic martial clan since the Warring States era that founded the Sword-Bearing Self-Defense Association.",
    ),
    11: (
        "Sword-Bearing Self-Defense Association",
        "Founded after WWII by Suzakuin Ryouan, former commander of the wartime warrior unit 'Akegarasu,' in response to the GHQ's sword-ban order aimed at weakening Japan. Continues to operate with the survival of Japan's Ikusabito warriors as its foremost mission.",
        "Founded postwar by Suzakuin Ryouan to preserve Japan's Ikusabito warriors in defiance of the GHQ's sword ban.",
    ),
    12: (
        "Toujinegi",
        "A sacred title awarded to the champion of the Murakumo Martial Festival. 'Negi' is a Shinto priestly rank, making Toujinegi recognized as the pinnacle of all Jindou swordsmen--also styled 'Iwainushi no Miko.' Bestowed only upon one possessing both supreme skill and dignity.",
        "Sacred champion title awarded to the winner of the Murakumo Martial Festival--the pinnacle of all Jindou swordsmen.",
    ),
    13: (
        "Fan Service Is Important!",
        "Devoted service offered to society or loved ones, or fulfilling one's expected role for others. Super important, right?!",
        "Devoted service offered to others--or giving the audience what they came to see. Super important, right?!",
    ),
    14: (
        "Second",
        "A support partner who assists a fighter using live data transmitted from their Origami, maintaining voice comms even mid-match. Like boxing seconds, they treat and cool down fighters during intervals, tune Origami, and hold authority to throw in the towel. Pro fighters use a three-person team (coach, medic, mechanic); at the academy, Technical Division students act as mechanic/coach while the school nurse serves as shared medic.",
        "A support partner assisting a fighter via live Origami telemetry during matches, handling tuning, advice, and stoppages.",
    ),
    15: (
        "Minamoto",
        "A bloodline of demon slayers descended from Minamoto no Yorimitsu, showing its true worth when fighting Keyou. A purebred Ikusabito clan whose prestige and local influence rival even the Suzakuin family.",
        "A demon-slaying Ikusabito bloodline descended from Minamoto no Yorimitsu, rivaling the Suzakuin clan in influence.",
    ),
    16: (
        "Go-Go Okita-kun",
        "A Japanese anime that also aired in America. Okita-kun is a master swordsman who cuts down evildoers left and right--only to tragically die of illness before achieving his dream.",
        "A Japanese sword-fighting anime aired in America too, starring master swordsman Okita-kun.",
    ),
    17: (
        "Revere the Emperor, Expel the Barbarians",
        "Sonnou Joui: a historical ideology calling to revere the Emperor ('Sonnou') and drive out foreign invaders ('Joui').",
        "Sonnou Joui: the historical Bakumatsu ideology of revering the Emperor and expelling foreign powers.",
    ),
    18: (
        "Barbarians",
        "Originally an ancient Chinese pejorative for foreign tribes, later adopted by Bakumatsu patriots advocating 'Expel the Barbarians' to reject foreign influence. Coming from Momiji--heir to the prestigious Suzakuin clan--against Victoria, who stormed into Jindou and claimed the Toujinegi title, the word carries striking symbolic weight.",
        "Historical term for outsiders, used by Bakumatsu patriots--and pointedly aimed by Momiji at Victoria.",
    ),
    19: (
        "Spirit-Type Armament",
        "Protective combat gear that doubles as an amplifier for an Origami. When deployed together with an Origami, it efficiently projects the invisible protective Barrier Jacket, granting formidable defense.",
        "Protective gear amplifying an Origami to project a powerful invisible defensive Barrier Jacket.",
    ),
    20: (
        "Shingan no Kiwamete",
        "Suzakuin Momiji's secret art. By instantaneously switching her brain into overdrive, she computes ultra-precise predictions of an opponent's moves from accumulated data, reading them like an open book. Because it is prediction rather than precognition, unknown variables can disrupt it--yet Momiji's vast knowledge makes escaping it nearly impossible without utterly erratic tactics.",
        "Momiji's secret art. Hyper-activates her brain to predict an opponent's moves with uncanny precision from battle data.",
    ),
    21: (
        "Momijigari",
        "The name of Kazamine Setsugekka's Origami. Originally named 'Fuugetsu Tsukinuke' (crafted by a renowned master smith at Keisetsu's commission), Setsugekka unilaterally renamed it 'Momijigari' ('Maple-Leaf Hunting').",
        "Setsugekka's masterwork Origami, originally named 'Fuugetsu Tsukinuke' before she renamed it herself.",
    ),
    22: (
        "Rival",
        "That classic trope where 'friend' is pronounced 'rival.' Wildly popular among hot-blooded types.",
        "That classic trope where 'friend' is read as 'rival.' Wildly popular with hot-blooded types.",
    ),
    23: (
        "Tretter",
        "A 140-character social networking service that remains stubbornly popular even in 20XX. Infamous for its cutthroat, hostile atmosphere.",
        "A 140-character social media service still popular in 20XX, infamous for its hostile atmosphere.",
    ),
    24: (
        "Mishima-ryuu Martial Arts",
        "A traditional unarmed martial art passed down in the Mishima family, specifically designed for fighting armed swordsmen barehanded.",
        "A traditional martial art of the Mishima clan built for fighting sword-wielding opponents empty-handed.",
    ),
    25: (
        "Shukuchi",
        "A martial footwork technique that closes the distance without letting the opponent perceive your movement, making it look as though you instantaneously teleported in front of them.",
        "A footwork art closing distance imperceptibly, appearing like sudden teleportation to the opponent.",
    ),
    26: (
        "Nakamura Sakura",
        "An active pro Jindou fighter and consummate heel known for her outrageous remarks. Currently ranked #3 in the Kansai-based Central League (alongside Kanto's East League). In a pro scene dominated by famous martial clans, Sakura rose purely on her own skill, earning fierce support from fans who resent traditional samurai families.",
        "Active pro Jindou heel fighter ranked #3 in the Central League. Self-made, wildly popular with anti-establishment fans.",
    ),
    27: (
        "Gnashing Teeth in Rage",
        "Sesshi Yakuwan: grinding one's teeth while clenching one's own arm--an idiom expressing unbearable fury, indignation, or bitter regret.",
        "Sesshi Yakuwan: grinding one's teeth and clenching one's arm in unbearable fury or bitter frustration.",
    ),
    28: (
        "Kuki Takahisa",
        "Muragaki Iori's best friend from their academy days and Kuki Asahi's older brother. Like Asahi, a master of Iai quick-draw swordsmanship. Won the Martial Festival as a first-year to claim the Toujinegi title, drawing numerous offers from pro Jindou teams as a top prospect.",
        "Iori's academy best friend and Asahi's older brother. An Iai master who won Toujinegi as a first-year.",
    ),
    29: (
        "World is Mine",
        "Tobe Ririmu's unique Tenju. Manifests Ririmu's inner worldview as an illusion visible exclusively to herself and her opponent.",
        "Ririmu's unique Tenju, projecting her personal worldview as an illusion seen only by herself and her foe.",
    ),
    30: (
        "Kazamine Family",
        "One of the martial clans that partnered with the Suzakuin family to found the Sword-Bearing Self-Defense Association. Built its faction by rallying lesser-standing members, specializing in support industries: spirit-weapon R&D, manufacturing, dojo operations, PR, and life insurance.",
        "A martial clan co-founding the Association alongside the Suzakuins, leading in spirit-gear R&D, dojos, and PR.",
    ),
    31: (
        "Convenience Stores Today!",
        "Sneaky convenience-store shrinkflation--like raising bento tray bottoms while claiming 'Now even tastier!' Soon inari sushi portions will shrink so far that by the 2200s customers will be handing inari sushi to the clerk... or maybe not.",
        "Sneaky convenience-store shrinkflation tricks like false bento bottoms while advertising 'Now even tastier!'",
    ),
    32: (
        "Changing Orders by Evening",
        "Chourei Bokai: issuing an order in the morning only to reverse it by evening. Unreliable and inconsistent--never lightly trust someone who does this without blinking.",
        "Chourei Bokai: reversing one's word from morning to night. A hallmark of someone not to be trusted lightly.",
    ),
    33: (
        "Masatane",
        "Father of Momiji and her three sisters, head of the Suzakuin family, and chairman of the Sword-Bearing Self-Defense Association. Austere, stubborn, and inflexible. Brilliant as an organizational leader, yet lacking as a parent--leaving Momiji and her sisters feeling stifled.",
        "Momiji's father, head of the Suzakuin clan and Association chairman. Capable leader, but a rigid, stifling parent.",
    ),
    34: (
        "Tengen Saimei-ryuu",
        "The secret sword style of the Muragaki family, feared as 'Swordsman Slayers.' Forged by generations of shogunate enforcers who eliminated enemies of the Tokugawa, it specializes strictly in killing swordsmen--using subtle feints in place ('Reader-Killer') to constantly break an enemy's reads until sheer mental exhaustion leaves them open to a fatal strike.",
        "The Muragaki family's 'Swordsman Slayer' style, breaking opponents' reads with micro-feints until delivering a fatal blow.",
    ),
    35: (
        "Ouitsu Issen",
        "A finishing art Asahi created on her own. Concentrating power while her blade remains sheathed, she unleashes stored Tenju in a single decisive flash--strong enough to slice steel like sponge and shear right through Kevlar, overwhelming any ordinary Barrier Jacket.",
        "Asahi's self-made finishing draw. Unleashes concentrated Tenju in one flash capable of cleaving steel and Barrier Jackets.",
    ),
    36: (
        "Arcadia",
        "A slightly self-indulgent fantasy where you dimly realize a dream will never come true, yet insist that chasing it anyway is what makes it cool.",
        "A romanticized delusion: knowing a dream can't come true, yet thinking it's cooler to chase it anyway.",
    ),
    37: (
        "Crowd-Puller",
        "Kyakuyose Panda: a star attraction that draws crowds. Because the Suzakuin clan is so prestigious, Momiji draws everyone's eyes at martial-heavy Murakumo Academy.",
        "A star attraction that draws crowds--much like the prestigious Suzakuin name at Murakumo Academy.",
    ),
    38: (
        "Kazamine Group Complex",
        "A mixed-use commercial and residential tower complex planned by the Kazamine Group in Sumiyoshi Special District, tentatively named 'Kazamine Tower.' Resolving numerous hurdles pushed its completion far down the road.",
        "A commercial and residential tower ('Kazamine Tower') planned by the Kazamine Group in Sumiyoshi District.",
    ),
    39: (
        "Bridgehead",
        "A foothold secured during a river crossing or amphibious landing for follow-up forces, or a strategic base of operations. The Kazamine clan apparently aims to make the academy a foothold for its influence.",
        "A strategic foothold for expanding operations--just as the Kazamine family hopes to use the academy.",
    ),
    40: (
        "Major Asagiri Midori",
        "Female company commander overseeing the Tenju Special Forces Group. A battle-hardened swordswoman who makes grown men tremble. Hailing from a long line of shrine maidens and Saniwa, her resonance score is extraordinarily high. Never attended Murakumo, learning Origami after joining the JGSDF. Wants to marry, but refuses to date anyone weaker than her--so she remains single.",
        "Company commander of the Tenju Special Forces. A fearsome veteran swordswoman still single because she won't date weaker men.",
    ),
    41: (
        "Personal Iron Frying Pan",
        "A cast-iron skillet Iori has carefully seasoned ever since enlisting, now gleaming black. The one time his squad leader nearly washed it with dish soap, Iori genuinely lost his temper.",
        "Iori's prized, well-seasoned cast-iron skillet from his enlistment days. Touch it with soap at your own peril.",
    ),
    42: (
        "Oni Extermination",
        "When an incident involving Origami or supernatural anomalies exceeds police capabilities, the Tenju Special Forces are called in. Within the unit, such missions are codenamed 'Oni Extermination.'",
        "Tenju Special Forces codename for dispatch missions handling Origami or supernatural incidents beyond police control.",
    ),
    43: (
        "Edo Period",
        "The era of peace when samurai clans ruled Japan as feudal lords. To people of martial households, it remains a symbol of bygone glory.",
        "The era of peace under samurai rule--still remembered as a golden age of glory by martial families.",
    ),
    44: (
        "Cool Beauty",
        "A stylish, composed woman who stays levelheaded and exudes an unapproachable elegance. The exact opposite of Setsugekka.",
        "A calm, composed, unapproachably elegant woman. The exact opposite of Setsugekka.",
    ),
    45: (
        "Bimiyan",
        "A half-baked delinquent ('bimyou na yankii'). Even in this era, delinquents still exist... they truly never die.",
        "A lukewarm, half-baked delinquent ('bimyou na yankii'). Even in the future, delinquents never go extinct.",
    ),
    46: (
        "Bamiyan",
        "A popular Chinese restaurant franchise. Famous for delicious gyoza and tantanmen noodles.",
        "A popular Chinese restaurant chain known for tasty gyoza and tantanmen.",
    ),
    47: (
        "James Mondo",
        "The protagonist of a famous spy series and a top-notch undercover agent. His signature sidearm is a Walther PPK.",
        "Ace undercover spy hero of a famous series, armed with his trusty Walther PPK.",
    ),
    48: (
        "Kijo (Demoness)",
        "Kuki Asahi's nickname, derived from her surname 'Kuki' ('Nine Oni') and fierce temperament. Also read 'kijo,' famously tied to legends like Momiji of Togakushi and Suzuka Gozen.",
        "Asahi's nickname, inspired by her 'Nine Oni' surname and ferocious personality.",
    ),
    49: (
        "Sworn Mortal Enemy",
        "Fugutaiten no Teki: an enemy with whom one cannot share the same sky--an adversary who must be struck down at all costs.",
        "An enemy with whom one cannot live under the same sky--a foe who must be defeated at any cost.",
    ),
    50: (
        "Muragaki Fried Rice",
        "Muragaki Iori's signature fried rice, iteratively perfected during his Tenju Special Forces days to reach culinary transcendence. Packed with select shrimp, scallops, and squid--one bite and you'll never forget it.",
        "Iori's transcendent seafood fried rice, perfected in the Special Forces with shrimp, scallops, and squid.",
    ),
    51: (
        "Low-Carb Menu",
        "A diet restricting carbohydrates among the three macronutrients (carbs, protein, fat). Effective for dieting, though improper balance can paradoxically spike blood sugar.",
        "A meal plan restricting carbohydrates for weight control, though balance is key.",
    ),
    52: (
        "Ascetic Monk",
        "Apparently meant to convey that forcing a growing teenage girl onto a low-carb menu is just like making a monk eat spartan temple food.",
        "How it feels for a growing girl forced onto a strict low-carb menu--like a monk on spartan temple fare.",
    ),
    53: (
        "Sakai Fresh Fish Market",
        "A historic seafood hub supplying fresh fish to the Kyoto-Osaka region. Momiji seems to have a friendly broker there who hooks her up with top-grade seafood.",
        "Historic seafood market supplying Kyoto and Osaka. Momiji gets fresh catch through a broker acquaintance there.",
    ),
    54: (
        "Suzaku Hyper Dry",
        "A non-alcoholic beer developed by a Kazamine Group subsidiary. In this era, non-alcoholic beer contains strictly 0% alcohol, so even students are allowed to drink it.",
        "A 0.0% non-alcoholic beer made by a Kazamine Group company, legal even for students.",
    ),
    55: (
        "Complete Six Codes",
        "Roppou Zensho: the compendium of Japan's six major legal codes. Even among lawyers, few have memorized every single article.",
        "Compendium of Japan's six major legal codes--rarely memorized in full even by lawyers.",
    ),
    56: (
        "Mental Resonance Coefficient",
        "Spiritual Induction Score (SIScore): a metric measuring how strongly one converts mental power into physical phenomena via a catalyst. Essential for wielding Tenju, and virtually unique to people of Japanese lineage. Because it depends heavily on innate physical traits, it cannot be raised through training--making a high score the mark of true talent.",
        "Spiritual Induction Score (SIScore): measures innate Tenju aptitude via a catalyst. Cannot be increased by training.",
    ),
    57: (
        "Tamukai",
        "Name of a secret art developed by a laboratory backed by the Kazamine family. Rumored to grant an immense Mental Resonance score if successful, though its details remain shrouded in mystery.",
        "A mysterious secret art created by a Kazamine-backed lab, rumored to grant enormous Mental Resonance.",
    ),
    58: (
        "Saniwa",
        "In ancient Shinto rites, one who receives and interprets divine oracles. Because Japan harbors countless spiritual beings beyond the myriad gods, those able to sense their wills have been prized since antiquity. Saniwa almost always possess extraordinarily high Mental Resonance.",
        "Shinto diviners who receive and interpret spiritual wills, typically blessed with exceptional Mental Resonance.",
    ),
    59: (
        "Satsuki",
        "Cabinet Public Security Bureau, Spiritual Disturbance Special Task Force 'Satsuki.' A covert unit handling domestic anomalies beyond regular military jurisdiction. Originally founded privately to combat the surge of Keyou after the Tokugawa abolished spirit blades, it was absorbed directly under the government after the Meiji Restoration.",
        "Covert Cabinet task force 'Satsuki,' tasked with secretly resolving major Keyou incidents beyond military reach.",
    ),
    60: (
        "Pochemon",
        "Official title: 'Pochette Monsters,' a holographic RPG where the protagonist becomes a trainer catching and battling monsters in pursuit of becoming a Pochemon Master.",
        "Short for 'Pochette Monsters,' a hit holographic RPG about catching and battling monsters to become a Master.",
    ),
    61: (
        "The Zone",
        "A state of extreme peak concentration where fatigue vanishes and unconscious, intuitive movements naturally produce the optimal answer.",
        "A transcendent state of peak focus where fatigue disappears and pure instinct guides every move.",
    ),
    62: (
        "Shohou Muga",
        "One of the Three/Four Seals of Dharma in Buddhism: all things arise through interdependence, and no permanent, unchanging self or essence exists.",
        "Buddhist Dharma seal teaching that all phenomena are interdependent and no fixed, eternal self exists.",
    ),
    63: (
        "Demon Zero-Calorie Theory",
        "Not 'donuts have zero calories because of the hole,' but the utterly sound theory that if you work out hard enough, anything you eat nets zero calories! Every girl's ultimate dream: effectively zero calories.",
        "The rock-solid theory that working out hard enough cancels out anything you eat--making it effectively zero calories!",
    ),
    64: (
        "Private Sauna",
        "Unlike large public saunas shared by crowds, a private sauna booth you can enjoy all to yourself.",
        "An individual sauna room you can enjoy privately instead of sharing with a crowd.",
    ),
    65: (
        "World Domination",
        "The classic vague ambition of evil organizations, about as fuzzy a concept as 'ally of justice.' Aliens with a power level of 530,000, frog-sergeant aliens, and squid girls all share this dream.",
        "The classic vague goal of villainous groups--cherished by alien emperors, frog sergeants, and squid girls alike.",
    ),
    66: (
        "Dojo Crashing",
        "The traditional Japanese custom of storming a dojo shouting 'Tanomou!' and claiming its signboard if you win. Most traditional kendo halls still welcome guests, though modern gym-like dojos mostly just give you weird looks.",
        "Traditional custom of challenging a dojo for its signboard--mostly earning strange looks at modern gym-style dojos.",
    ),
    67: (
        "Tennen Rishin-ryuu",
        "A sword style founded by Kondou Kuranosuke in the late Edo period, famed for 4th headmaster Kondou Isami of the Shinsengumi. Victoria is nominally a practitioner, though countless dojo challenges and tips picked up along the way mutated her style into mostly her own self-taught form.",
        "Classic sword style famed by Shinsengumi's Kondou Isami. Victoria's version has mutated into her own freestyle blend.",
    ),
    68: (
        "Ultimate Kikuichimonji Sword Kai",
        "The name of Victoria's Origami, styled 'Ultimate Kikuichimonji Sword Kai'--named after Okita-kun's 'Kikuichimonji' from Go-Go Okita-kun. The 'Kai' marks the wild custom modifications Shizuku added to Victoria's original blade.",
        "Victoria's Origami, named after Okita-kun's sword and heavily customized ('Kai') by Shizuku.",
    ),
    69: (
        "SUMITANI",
        "One of Japan's Big Three Origami parts makers alongside Getsuzan and Miyairi Bladeworks. Standard in raw specs, yet famous for affordable, reliable quality--used by 95% of Murakumo students. Offers Basic, Enterprise, and Premium tiers plus a huge lineup tailored to different fighters' traits.",
        "Major Origami parts maker used by 95% of Murakumo students, renowned for reliable quality and wide variety.",
    ),
    70: (
        "Flashy and Shallow",
        "Charai: flighty, superficial, party-boy vibes. For the record, Takahisa only talks like a playboy--inside he isn't actually that shallow.",
        "Flighty, flashy, playboy-ish. Takahisa only talks that way--deep down he's far more earnest.",
    ),
    71: (
        "Abuse of Authority",
        "Misusing power granted by one's profession, which can carry criminal penalties depending on severity. A teacher's authority over students is immense.",
        "Misusing the power of one's office or position--and a teacher's authority over students is no joke.",
    ),
    72: (
        "Monomolecular Coating",
        "An ultra-tough coating reinforced at the molecular scale. Technically, rather than a single giant molecule, it weaves monomolecular wires into the coating material.",
        "Ultra-durable protective coating reinforced with woven monomolecular wires.",
    ),
    73: (
        "Muscular Big Sister",
        "Judged purely by musculature she might look male, yet both her presentation and fashion are thoroughly feminine. Respect her identity and call her big sister!",
        "Built like a bodybuilder yet unmistakably feminine in fashion and style. Respect her and call her big sis!",
    ),
    74: (
        "Today's Goods",
        "You don't need white powder to send girls into euphoria--top-notch sweets work way better.",
        "Forget illicit powder--premium sweets are far more effective at sending girls into pure bliss.",
    ),
    75: (
        "Payback Visit",
        "An event around graduation where students express their 'payback'... er, heartfelt gratitude to teachers who looked after them, delivered passionately via fists.",
        "A graduation-time tradition of delivering passionate 'gratitude' to beloved teachers with one's fists.",
    ),
    76: (
        "Ookami Family",
        "A business-leaning martial clan running multiple major enterprises, renowned for Ookami Steel, Ookami Construction, and Ookami Insurance.",
        "A corporate-oriented martial family behind Ookami Steel, Ookami Construction, and Ookami Insurance.",
    ),
    77: (
        "Child Prodigy",
        "Kirinji: a brilliant youth expected to achieve greatness. Even the famed warlord Akechi Mitsuhide was supposedly once rumored to be one.",
        "Kirinji: an exceptional youth destined for greatness--even Akechi Mitsuhide was once rumored to be one.",
    ),
    78: (
        "Ikusabito",
        "General term for warriors who fight wielding genuine spirit blades forged from Tamahagane, gaining superhuman strength from their blades' spiritual blessings. Sometimes also used for Jindou swordsmen wielding Origami.",
        "Warriors wielding true Tamahagane spirit blades for superhuman strength; also loosely applied to Jindou fighters.",
    ),
    79: (
        "Keyou",
        "Otherworldly entities including youkai and phantoms--beings dwelling within the 'Darkness' beyond human comprehension.",
        "Supernatural entities such as youkai and spirits dwelling in the 'Darkness' beyond human understanding.",
    ),
    80: (
        "Demon Extermination",
        "Minamoto Shizuku's unique Tenju. Channels evil-banishing light that pierces pitch darkness, purging yin miasma and drastically weakening Keyou. Inherited from the demon-slaying power once held by Minamoto no Yorimitsu.",
        "Shizuku's unique Tenju, inherited from Minamoto no Yorimitsu, emitting purifying light that weakens Keyou.",
    ),
    81: (
        "Fox",
        "Shape-shifting foxes and tanuki are ancient Japanese Keyou famed for bewitching and deceiving humans, and sometimes possessing people to cause mischief.",
        "Ancient Japanese Keyou known for illusions, trickery, and occasionally possessing humans.",
    ),
    82: (
        "Moku (Smokes)",
        "Slang for cigarettes, named after the sound/image of billowing smoke ('mokumoku').",
        "Japanese slang for cigarettes, derived from 'mokumoku' (billowing smoke).",
    ),
    83: (
        "Magistrate",
        "Bugyou: civil officials assigned specific duties from the Heian to Edo periods. Nowadays also jokingly describes someone who bossily micromanages hotpot or yakiniku grilling.",
        "Historical civil official--or someone who bossily takes charge of grilling yakiniku or hotpot.",
    ),
    84: (
        "Hermit Sage",
        "Sennin: in ancient China, mortals who attained godlike enlightenment and lived peacefully in remote mountain paradises. An object of longing for Momiji, who yearns to escape worldly ties.",
        "Enlightened immortals living in secluded mountains--a lifestyle Momiji secretly envies.",
    ),
    85: (
        "Yorishiro-kun",
        "Murakumo Academy's battle simulator, officially 'Hiraga Electronic Spirit-Type Simulator YSR-04E.' Uses full HR to project telemetry, Origami, and opponents for simulated duels, uploading match logs to a shared server. Its default avatar looks adorable, though registered real fighters can be projected too.",
        "The academy's HR duel simulator (YSR-04E), projecting Origami, telemetry, and opponents with a cute default avatar.",
    ),
    86: (
        "Barrier Jacket",
        "A uniform full-body barrier generated by combining an Origami with Spirit-Type Armament, or the name of its durability rating--officially Vital Force Field Value (VF Value), monitored externally with other stats. While intact it never punctures unless hit beyond its limit; reserve VF automatically patches breaches at heavy energy cost. Dropping below threshold first loses a Jindou match.",
        "Full-body protective field from an Origami + Armament. Measured by VF Value; dropping below threshold loses the match.",
    ),
    87: (
        "Sanjou Family",
        "A lineage of master bladesmiths known since antiquity as 'Saishou,' producing countless great smiths. During the Meiji Restoration, they combined mechanical engineering with spirit blades to invent the versatile 'Spirit-Type Mechanical Blade.'",
        "Ancient lineage of master 'Saishou' bladesmiths who invented the Spirit-Type Mechanical Blade in the Meiji era.",
    ),
    88: (
        "Jindou",
        "Official name: Spirit-Type Mechanical Blade Way (Jindou). A modern one-on-one sport fought with live blades using mechanized Origami and protective gear, creating a futuristic kendo free of serious injury within the rules. Like sumo, it is regarded as a sacred Shinto rite offering sword dances to the gods.",
        "Futuristic 1-on-1 martial sport fought with mechanized live blades (Origami) and barriers, rooted in Shinto ritual.",
    ),
    89: (
        "Hanyou (Half-Apparition)",
        "A hybrid of Keyou and human. Though their supernatural strength is halved, wearing human form lets them remain stable in the material world without needing a medium. Refers both to direct hybrids and bloodlines descended from them.",
        "A Keyou-human hybrid whose human form sustains them without a medium, or clans descended from such blood.",
    ),
    90: (
        "Norito",
        "Because Jindou is classified as a sacred Shinto rite like sumo, every official match begins with the umpire reciting a solemn Norito prayer to the myriad gods.",
        "A Shinto ritual prayer chanted by the umpire before every official Jindou match.",
    ),
    91: (
        "Iai",
        "Swordsmanship focused on drawing from the scabbard to strike or deflect in one motion before finishing with a follow-up cut. Because Jindou bouts normally start with blades drawn, fighting from the sheath concedes initiative and requires immense skill--yet a few masters still win with Iai.",
        "Quick-draw swordsmanship striking straight from the scabbard--rare and demanding in Jindou, yet deadly in skilled hands.",
    ),
    92: (
        "JGSDF Special Forces",
        "The JGSDF maintains Ikusabito units wielding genuine spirit blades rather than Origami to defend Japan. 'Akegarasu' is well known, and rumors speak of unofficial non-JGSDF units too, though all details remain classified for national security.",
        "Classified JGSDF Ikusabito units like 'Akegarasu' wielding true spirit blades for national defense.",
    ),
    93: (
        "Pro League",
        "Because Jindou is a state-protected sport like sumo, a thriving Pro League exists under the Sword-Bearing Self-Defense Association, paying athletes a share of massive gate revenues. Winning fighters' home dojos receive Association funding and patron sponsorships, creating a pipeline of youth trained from childhood through Murakumo Academy to the pros.",
        "Jindou's lucrative Association-run Pro League, funding dojos and turning Murakumo graduates into star athletes.",
    ),
    94: (
        "Inari Sushi",
        "Vinegared sushi rice tucked inside sweet-savory simmered fried tofu pouches. Widely sold even at convenience stores with surprisingly good taste, affectionately called Oinari-san or Inari, with regional styles across Japan.",
        "Seasoned sushi rice stuffed into sweet-savory fried tofu pouches, beloved nationwide as Oinari-san.",
    ),
    95: (
        "Toyohara Konpeidou",
        "A traditional Japanese specialty shop selling everything from wagashi sweets to sushi and pickles across every price tier. Especially famous in certain circles for its exquisite inari sushi.",
        "A specialty Japanese shop stocking sweets, pickles, and sushi--famous in select circles for exquisite inari sushi.",
    ),
    96: (
        "Spot-On (Batsugyun)",
        "A cutesy slang twist on 'batsugun,' meaning extraordinarily outstanding among its kind~!",
        "Playful slang version of 'batsugun'--meaning totally top-notch and outstanding~!",
    ),
    97: (
        "Date",
        "A romantic rendezvous where two people agree on a time and place to meet--enjoyed by lovers regardless of gender.",
        "A planned romantic outing between two people in love, regardless of gender.",
    ),
    98: (
        "Big-Eater Champiooon",
        "A title bestowed upon someone who can devour astonishing amounts of food, contested in competitions around the globe.",
        "Champion title awarded to competitive eaters who can put away massive mountains of food.",
    ),
    99: (
        "Murmur (Zawa...)",
        "An onomatopoeia used when an uneasy, restless tension... hangs heavy in the air...",
        "An ominous, restless stirring in the air... when something feels deeply unsettling...",
    ),
    100: (
        "Zombie",
        "General term for a corpse brought back to life. Because they're already dead, half-hearted attacks can't put them down--hence the term is also used for people with freakish stamina.",
        "A reanimated corpse that shrugs off normal blows--also slang for someone with monstrous stamina.",
    ),
    101: (
        "Finishing Blow",
        "Todome: the decisive final strike that ends a fight for good. In practice, it's often withheld to keep someone dangling instead.",
        "Todome: the decisive final blow ending a matter completely.",
    ),
    102: (
        "Yakiniku",
        "Grilled beef, pork, chicken, and other meats. Red meat in particular is a great stamina booster. Popular at group banquets, though poor-quality meat can turn a lively party into a funeral wake.",
        "Japanese grilled meat--a classic stamina booster and banquet favorite (provided the meat is good!).",
    ),
    103: (
        "Harem",
        "A situation in which a single man is romantically adored by multiple women.",
        "A situation where multiple women hold romantic affection for one man.",
    ),
    106: (
        "Spirit Agency",
        "One of Japan's government ministries. A venerable institution descended from ancient Shinto traditions stretching back over 3,000 years--the spiritual headquarters overseeing Japan's shrine network from behind the scenes.",
        "Venerable Japanese ministry rooted in 3,000-year-old Shinto tradition, overseeing shrines from behind the scenes.",
    ),
}


def build_clean_template_big(sample_img: Image.Image) -> Image.Image:
    """Reconstruct a 100% artifact-free 621x370 TIPS big card blank preserving exact gradient & borders."""
    arr = np.asarray(sample_img.convert("RGBA"), dtype=np.uint8).copy()
    # Header left region (x=10..410, y=6..52) has horizontal gradient matching row y=54 or x=380..410:
    # Actually row y=54..57 is completely text-free across x=0..621! Copy its horizontal gradient vertically for y=6..53!
    # Wait: sample y=2..5 (top margin above text) for x=0..360 so we keep the exact vertical+horizontal gradient!
    for x in range(10, 415):
        ref = arr[3, x]  # pristine header pixel at top margin (no text, no border!)
        arr[6:54, x] = ref
    # Body area (x=12..608, y=80..320) is completely uniform flat gray! Sample exact clean pixel at (300, 325):
    body_px = arr[325, 300]
    arr[80:320, 12:608] = body_px
    return Image.fromarray(arr, mode="RGBA")


def build_clean_template_small(sample_img: Image.Image) -> Image.Image:
    """Reconstruct a 100% artifact-free 261x147 TIPS small popup blank + clean '(Details)' tag."""
    arr = np.asarray(sample_img.convert("RGBA"), dtype=np.uint8).copy()
    # Header text region x=4..175, y=4..29 -> fill from clean top row y=2
    for x in range(4, 178):
        arr[4:30, x] = arr[2, x]
    # Body text region x=4..256, y=38..126 -> uniform flat gray sampled at (130, 130)
    body_px = arr[130, 130]
    arr[38:126, 4:256] = body_px
    # Clean bottom-right '(詳細有)' text inside the angled corner tab (x=216..258, y=130..145)
    arr[130:146, 217:259] = body_px
    return Image.fromarray(arr, mode="RGBA")


def wrap_text_pillow(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words = text.split(" ")
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = w if not cur else f"{cur} {w}"
        if draw.textlength(cand, font=font) <= max_w or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_big_card(blank: Image.Image, title: str, body: str) -> Image.Image:
    im = blank.copy()
    draw = ImageDraw.Draw(im)
    title = title.replace("--", "\u2014")
    body = body.replace("--", "\u2014")
    # Title (auto-fit width <= 395px so it never collides with 'Explanation' watermark at x=420)
    t_size = 30
    while t_size >= 18:
        t_font = ImageFont.truetype(str(FONT_MED), t_size)
        if draw.textlength(title, font=t_font) <= 395:
            break
        t_size -= 2
    t_y = 10 + (30 - t_size) // 2
    draw.text((18, t_y), title, font=t_font, fill=(255, 255, 255, 255))

    # Body (auto-shrink slightly if a very long entry needs > 8 lines)
    for b_size, line_h in [(21, 27), (19, 25), (17, 22)]:
        b_font = ImageFont.truetype(str(FONT_FIRA), b_size)
        lines = wrap_text_pillow(draw, body, b_font, max_w=578)
        if len(lines) * line_h <= 238:
            break
    y = 86
    for ln in lines:
        draw.text((22, y), ln, font=b_font, fill=(255, 255, 255, 255))
        y += line_h
    return im


def render_small_card(blank: Image.Image, title: str, summary: str) -> Image.Image:
    im = blank.copy()
    draw = ImageDraw.Draw(im)
    title = title.replace("--", "\u2014")
    summary = summary.replace("--", "\u2014")
    # Title (fit <= 172px so it clears 'Explanation' on the right)
    t_size = 18
    while t_size >= 12:
        t_font = ImageFont.truetype(str(FONT_MED), t_size)
        if draw.textlength(title, font=t_font) <= 172:
            break
        t_size -= 1
    draw.text((8, 6 + (18 - t_size) // 2), title, font=t_font, fill=(255, 255, 255, 255))

    # Summary body (fit comfortably inside y=40..124 = 84px height, max_w=244px)
    for b_size, line_h in [(14, 17), (13, 16), (12, 15)]:
        b_font = ImageFont.truetype(str(FONT_FIRA), b_size)
        lines = wrap_text_pillow(draw, summary, b_font, max_w=244)
        if len(lines) * line_h <= 84:
            break
    y = 40
    for ln in lines[:5]:
        draw.text((8, y), ln, font=b_font, fill=(255, 255, 255, 255))
        y += line_h

    # Render crisp '(Details)' in bottom-right corner tab
    d_font = ImageFont.truetype(str(FONT_MED), 11)
    draw.text((218, 132), "(Details)", font=d_font, fill=(255, 255, 255, 255))
    return im


def main() -> int:
    out_pgd_dir = WORKSPACE / "work" / "pgd_overrides"
    prev_dir = WORKSPACE / "work" / "ui_preview"
    out_pgd_dir.mkdir(parents=True, exist_ok=True)
    prev_dir.mkdir(parents=True, exist_ok=True)

    tips_pac = GAME_DIR / "tips.pac"
    orig_b0, meta_b0 = decode_pgd(read_pac2_member(tips_pac, "TIPS0000B.PGD"))
    orig_s0, meta_s0 = decode_pgd(read_pac2_member(tips_pac, "TIPS0000S.PGD"))
    blank_b = build_clean_template_big(orig_b0)
    blank_s = build_clean_template_small(orig_s0)
    blank_b.save(WORKSPACE / "work" / "ui_templates" / "tips_big_clean.png")
    blank_s.save(WORKSPACE / "work" / "ui_templates" / "tips_small_clean.png")

    count = 0
    for num, (title, body, summary) in sorted(TIPS_DATA.items()):
        im_b = render_big_card(blank_b, title, body)
        im_s = render_small_card(blank_s, title, summary)
        if num in (0, 2, 86):
            im_b.save(prev_dir / f"en_TIPS{num:04d}B.png")
            im_s.save(prev_dir / f"en_TIPS{num:04d}S.png")
        (out_pgd_dir / f"TIPS{num:04d}B.PGD").write_bytes(encode_pgd(im_b, meta_b0))
        (out_pgd_dir / f"TIPS{num:04d}S.PGD").write_bytes(encode_pgd(im_s, meta_s0))
        count += 2

    print(f"Rendered and encoded {count} English TIPS .PGD files into {out_pgd_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
