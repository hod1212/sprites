"""
Dicionario de palavras-chave PT-BR -> EN para classes/entidades de Ragnarok Online.

O Spriters Resource indexa os sprites pelos nomes em ingles (Knight, Priest...).
Este modulo traduz automaticamente os termos que o usuario brasileiro digita
(inclusive os nomes oficiais do bRO, como "Algoz" = Assassin Cross) para os
termos que realmente aparecem no site.

Cada chave e' um termo em portugues (minusculo, sem acento) e o valor e' uma
lista de termos em ingles que devem ser buscados no indice.
"""

# fmt: off
PT_TO_EN = {
    # ---- Classes basicas (1-1) ----
    "aprendiz":            ["novice"],
    "novico":              ["acolyte"],
    "espadachim":          ["swordsman", "swordman"],
    "gatuno":              ["thief"],
    "ladrao":              ["thief"],
    "arqueiro":            ["archer"],
    "arqueira":            ["archer"],
    "mago":                ["mage", "magician"],
    "maga":                ["mage", "magician"],
    "mercador":            ["merchant"],
    "comerciante":         ["merchant"],

    # ---- Classes 2-1 ----
    "cavaleiro":           ["knight"],
    "sacerdote":           ["priest"],
    "padre":               ["priest"],
    "bruxo":               ["wizard"],
    "bruxa":               ["wizard"],
    "feiticeiro":          ["wizard", "warlock"],
    "ferreiro":            ["blacksmith"],
    "cacador":             ["hunter"],
    "cacadora":            ["hunter"],
    "mercenario":          ["assassin", "mercenary"],
    "assassino":           ["assassin"],

    # ---- Classes 2-2 ----
    "templario":           ["crusader"],
    "cruzado":             ["crusader"],
    "monge":               ["monk"],
    "sabio":               ["sage"],
    "arruaceiro":          ["rogue"],
    "alquimista":          ["alchemist"],
    "bardo":               ["bard"],
    "odalisca":            ["dancer"],
    "dancarina":           ["dancer"],

    # ---- Transclasses (nomes oficiais do bRO) ----
    "lorde":               ["lord knight"],
    "paladino":            ["paladin"],
    "sumo sacerdote":      ["high priest"],
    "arcimago":            ["high wizard"],
    "mestre ferreiro":     ["whitesmith", "mastersmith"],
    "atirador de elite":   ["sniper"],
    "algoz":               ["assassin cross"],
    "carrasco":            ["assassin cross"],
    "desordeiro":          ["stalker"],
    "mestre":              ["champion"],
    "professor":           ["professor", "scholar"],
    "criador":             ["creator", "biochemist"],
    "menestrel":           ["clown", "minstrel"],
    "cigana":              ["gypsy"],

    # ---- Terceiras classes ----
    "cavaleiro runico":    ["rune knight"],
    "guardiao real":       ["royal guard"],
    "arcebispo":           ["arch bishop", "archbishop"],
    "shura":               ["sura"],
    "arcano":              ["warlock"],
    "sentinela":           ["ranger"],
    "sicario":             ["guillotine cross"],
    "renegado":            ["shadow chaser"],
    "mecanico":            ["mechanic"],
    "bioquimico":          ["genetic", "geneticist"],
    "trovador":            ["minstrel", "maestro"],
    "musa":                ["wanderer"],
    "feiticeira":          ["sorcerer"],

    # ---- Classes expandidas ----
    "justiceiro":          ["gunslinger"],
    "atirador":            ["gunslinger"],
    "ninja":               ["ninja"],
    "taekwon":             ["taekwon"],
    "espiritualista":      ["soul linker"],
    "super aprendiz":      ["super novice"],

    # ---- Termos genericos / equipamentos ----
    "personagem":          ["character"],
    "personagens":         ["character"],
    "classe":              ["class", "job"],
    "monstro":             ["monster"],
    "monstros":            ["monster"],
    "chefe":               ["boss", "mvp"],
    "cabeca":              ["head"],
    "cabelo":              ["hair"],
    "chapeu":              ["hat", "headgear"],
    "montaria":            ["mount", "peco"],
    "espada":              ["sword"],
    "lanca":               ["spear", "lance"],
    "escudo":              ["shield"],
    "arco":                ["bow"],
    "machado":             ["axe"],
    "adaga":               ["dagger"],
    "cajado":              ["staff", "rod"],

    # ---- Monstros famosos ----
    "poring":              ["poring"],
    "lunatico":            ["lunatic"],
    "esporo":              ["spore"],
    "lobo":                ["wolf", "desert wolf"],
    "osiris":              ["osiris"],
    "baphomet":            ["baphomet"],
    "doppelganger":        ["doppelganger"],
}
# fmt: on


def _strip_accents(text: str) -> str:
    """Remove acentos: 'Cavaleiro Rúnico' -> 'cavaleiro runico'."""
    import unicodedata

    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def translate_query(query: str) -> list[str]:
    """
    Recebe o texto livre do usuario e devolve uma lista de termos de busca em
    ingles, do mais especifico para o mais generico.

    Exemplo: "Preciso de um Cavaleiro com lança"
             -> ["knight", "spear", "lance", "cavaleiro", "lanca", ...]
    """
    clean = _strip_accents(query)
    terms: list[str] = []

    # 1) Expressoes compostas primeiro (ex.: "atirador de elite", "algoz")
    for pt_term in sorted(PT_TO_EN, key=len, reverse=True):
        if pt_term in clean:
            for en in PT_TO_EN[pt_term]:
                if en not in terms:
                    terms.append(en)
            # Evita que "atirador de elite" tambem dispare "atirador"
            clean = clean.replace(pt_term, " ")

    # 2) Palavras soltas restantes (podem ja estar em ingles: "knight")
    stopwords = {
        "preciso", "quero", "de", "um", "uma", "com", "o", "a", "do", "da",
        "para", "em", "no", "na", "e", "que", "sprite", "sheet", "por",
        "favor", "me", "gere", "crie", "faca",
    }
    for word in clean.split():
        if len(word) > 2 and word not in stopwords and word not in terms:
            terms.append(word)

    return terms
