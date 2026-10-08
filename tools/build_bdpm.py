#!/usr/bin/env python3
"""Construit data/bdpm.json à partir de la Base de données publique des médicaments (BDPM).

Source officielle : https://base-donnees-publique.medicaments.gouv.fr (ANSM / HAS / CNAM).
Le fichier produit associe chaque code CIP13 (celui du DataMatrix des boîtes)
au nom du médicament et, quand on peut le déduire, au nombre d'unités par boîte.

Format :
  {"v": "AAAA-MM-JJ", "n": [dénominations...], "g": [groupe générique ou 0 par nom],
   "c": {"3400...": [index du nom, unités par boîte ou 0], ...}}

Usage : python3 tools/build_bdpm.py            (télécharge les fichiers)
        python3 tools/build_bdpm.py DOSSIER    (utilise des fichiers déjà téléchargés)
"""
import datetime, json, os, re, sys, urllib.request

BASES = [
    "https://base-donnees-publique.medicaments.gouv.fr/download/file/",
    "https://base-donnees-publique.medicaments.gouv.fr/telechargement.php?fichier=",
]
FILES = ["CIS_bdpm.txt", "CIS_CIP_bdpm.txt", "CIS_GENER_bdpm.txt"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "bdpm.json")


def decode(raw):
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1", "replace")


def fetch(name):
    last = None
    for base in BASES:
        try:
            req = urllib.request.Request(base + name, headers={"User-Agent": "pharmacie-foyer (github.com/Toma-971/Pharmacie-foyer)"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            text = decode(data)
            if text.count("\t") > 100:  # vrai fichier tabulé, pas une page d'erreur HTML
                return text
            last = "contenu inattendu depuis " + base
        except Exception as e:  # noqa: BLE001
            last = f"{base}{name}: {e}"
    raise SystemExit(f"Téléchargement impossible de {name} ({last})")


def rows(text):
    for line in text.splitlines():
        if line.strip():
            yield [c.strip() for c in line.split("\t")]


COUNTABLE = (r"comprim|g[ée]lule|capsule|sachet|ampoule|suppositoire|dose|patch|dispositif transdermique|pastille|ovule|"
             r"lyophilisat|unidose|r[ée]cipient unidose|stylo|seringue|film|timbre|pipette|gomme|tablette|cartouche|"
             r"poche|flacon unidose|implant|anneau|inhalateur|applicateur")
CONTAINERS = r"plaquette|blister|tube|flacon|pilulier|bo[iî]te|sachet|bande|film|r[ée]cipient|pot|[ée]tui|plaque|conditionnement|piluliers?"


def units_from_label(label):
    """« 2 plaquette(s) PVC aluminium de 14 comprimé(s) » -> 28 ; 0 si on ne sait pas."""
    t = label.lower().replace("(s)", "")
    m = None
    for m in re.finditer(r"\bde\s+(\d+)\s+(?:" + COUNTABLE + ")", t):
        pass
    if m:
        n = int(m.group(1))
        lead = re.match(r"\s*(\d+)\s+(?:" + CONTAINERS + ")", t)
        if lead and lead.end() <= m.start():
            n *= int(lead.group(1))
        return n if 0 < n < 10000 else 0
    m = re.match(r"\s*(\d+)\s+(?:" + COUNTABLE + ")", t)
    if m:
        n = int(m.group(1))
        return n if 0 < n < 10000 else 0
    return 0


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    texts = {}
    for f in FILES:
        if src:
            with open(os.path.join(src, f), "rb") as fh:
                texts[f] = decode(fh.read())
        else:
            texts[f] = fetch(f)

    names = {}
    for r in rows(texts["CIS_bdpm.txt"]):
        if len(r) >= 2 and r[0].isdigit():
            names[r[0]] = r[1]
    groups = {}
    for r in rows(texts["CIS_GENER_bdpm.txt"]):
        if len(r) >= 3 and r[0].isdigit() and r[2].isdigit():
            groups.setdefault(r[2], int(r[0]))

    idx, name_list, group_list, codes = {}, [], [], {}
    for r in rows(texts["CIS_CIP_bdpm.txt"]):
        if len(r) < 7:
            continue
        cis, label, cip13 = r[0], r[2], r[6]
        if not (cis in names and re.fullmatch(r"\d{13}", cip13)):
            continue
        if cis not in idx:
            idx[cis] = len(name_list)
            name_list.append(names[cis])
            group_list.append(groups.get(cis, 0))
        codes[cip13] = [idx[cis], units_from_label(label)]

    if len(codes) < 1000:
        raise SystemExit(f"Trop peu de présentations lues ({len(codes)}) : format des fichiers inattendu ?")
    out = {"v": datetime.date.today().isoformat(), "n": name_list, "g": group_list, "c": codes}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    with_units = sum(1 for v in codes.values() if v[1])
    print(f"{len(codes)} présentations, {len(name_list)} médicaments, {with_units} avec le nombre d'unités -> {OUT}")


if __name__ == "__main__":
    main()
