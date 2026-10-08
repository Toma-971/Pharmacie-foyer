#!/usr/bin/env python3
"""Construit data/bdpm.json à partir de la Base de données publique des médicaments (BDPM).

Source officielle : https://base-donnees-publique.medicaments.gouv.fr (ANSM / HAS / CNAM).
Le fichier produit associe chaque code CIP13 (celui du DataMatrix des boîtes)
au nom du médicament et, quand on peut le déduire, au nombre d'unités par boîte.
Il donne aussi, pour chaque médicament, sa substance et son dosage (« Paracétamol 1000 mg ») :
l'appli s'en sert pour ranger Doliprane et Paracétamol Biogaran sous le même médicament.

Format :
  {"v": "AAAA-MM-JJ", "n": [dénominations...], "g": [groupe générique ou 0 par nom],
   "s": [substances et dosages...], "ns": [index dans s ou -1, par nom],
   "c": {"3400...": [index du nom, unités par boîte ou 0], ...}}

Usage : python3 tools/build_bdpm.py            (télécharge les fichiers)
        python3 tools/build_bdpm.py DOSSIER    (utilise des fichiers déjà téléchargés)
"""
import datetime, json, os, re, sys, urllib.request

BASES = [
    "https://base-donnees-publique.medicaments.gouv.fr/download/file/",
    "https://base-donnees-publique.medicaments.gouv.fr/telechargement.php?fichier=",
]
FILES = ["CIS_bdpm.txt", "CIS_CIP_bdpm.txt", "CIS_GENER_bdpm.txt", "CIS_COMPO_bdpm.txt"]
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


SALT_BEFORE = (r"(?:chlorhydrate|dichlorhydrate|bromhydrate|maléate|sulfate|tartrate|hémitartrate|fumarate|hémifumarate|citrate|"
               r"acétate|phosphate|bésilate|bésylate|mésilate|mésylate|succinate|lactate|gluconate|oxalate|nitrate|"
               r"chlorure|bromure|iodure|valérate|propionate|dipropionate|furoate|butyrate|stéarate|palmitate|"
               r"embonate|tosilate|camsilate|édisilate|napadisilate|benzoate|salicylate|lysinate)\s+(?:de\s+|d')")
SALT_AFTER = (r"\s+(?:sodique|disodique|potassique|dipotassique|calcique|magnésique|monosodique|"
              r"anhydre|base|trihydraté|trihydratée|monohydraté|monohydratée|dihydraté|dihydratée|"
              r"hémihydraté|hémihydratée|sesquihydraté|sesquihydratée|pentahydraté|hexahydraté|"
              r"heptahydraté|hydraté|hydratée|micronisé|micronisée)\b")


def clean_subst(name):
    t = name.lower().strip()
    t = re.sub(r"^" + SALT_BEFORE, "", t)
    for _ in range(3):
        t = re.sub(SALT_AFTER, "", t)
    t = re.sub(r"\s+", " ", t).strip(" ,")
    return t[:1].upper() + t[1:]


def clean_num(x):
    x = x.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        v = float(x)
    except ValueError:
        return None
    return v


def fmt_num(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return s.replace(".", ",")


def clean_dose(dose, ref):
    """« 1,000 g » / « un comprimé » -> « 1000 mg » ; « 2,4 g » / « 100 ml » -> « 2,4 g/100 ml »."""
    d = re.sub(r"\s+", " ", dose.lower()).strip()
    m = re.fullmatch(r"([\d\s\u00a0]+(?:[.,]\d+)?)\s*(g|mg|µg|microgrammes?|microgramme|mcg|ui|u\.i\.|%|ml)(.*)", d)
    if not m:
        return d
    v, unit, rest = clean_num(m.group(1)), m.group(2), m.group(3).strip()
    if v is None:
        return d
    if unit == "g" and not rest:
        v, unit = v * 1000, "mg"
    elif unit in ("microgramme", "microgrammes", "mcg"):
        unit = "µg"
    elif unit == "u.i.":
        unit = "UI"
    elif unit == "ui":
        unit = "UI"
    out = fmt_num(v) + " " + unit + ((" " + rest) if rest else "")
    if "/" not in out:
        r = re.fullmatch(r"([\d\s\u00a0]+(?:[.,]\d+)?)\s*(ml|l|g)\b.*", ref.lower().strip())
        if r:
            rv = clean_num(r.group(1))
            if rv is not None:
                out += "/" + fmt_num(rv) + " " + r.group(2)
    return out


def substance_labels(compo, routes):
    """CIS -> « Paracétamol 1000 mg » (plusieurs substances jointes par « + »), ou absent."""
    by_cis = {}
    for r in rows(compo):
        if len(r) < 7 or not r[0].isdigit():
            continue
        cis, elem, name, dose, ref, nature = r[0], r[1], r[3], r[4], r[5], r[6].upper()
        link = r[7] if len(r) > 7 and r[7] else name
        if not name or not dose:
            continue
        slot = by_cis.setdefault(cis, {}).setdefault((elem.lower(), link), {})
        slot[nature] = (name, dose, ref)
    out = {}
    for cis, links in by_cis.items():
        parts = set()
        for slot in links.values():
            name, dose, ref = slot.get("FT") or slot.get("SA") or next(iter(slot.values()))
            parts.add(clean_subst(name) + " " + clean_dose(dose, ref))
        if not parts or len(parts) > 4:
            continue
        label = " + ".join(sorted(parts))
        route = routes.get(cis, "")
        if route and route != "orale":
            label += ", voie " + route
        out[cis] = label
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    texts = {}
    for f in FILES:
        if src:
            with open(os.path.join(src, f), "rb") as fh:
                texts[f] = decode(fh.read())
        else:
            texts[f] = fetch(f)

    names, routes = {}, {}
    for r in rows(texts["CIS_bdpm.txt"]):
        if len(r) >= 2 and r[0].isdigit():
            names[r[0]] = r[1]
            if len(r) >= 4:
                routes[r[0]] = "/".join(sorted(v.strip().lower() for v in r[3].split(";") if v.strip()))
    labels = substance_labels(texts["CIS_COMPO_bdpm.txt"], routes)
    groups = {}
    for r in rows(texts["CIS_GENER_bdpm.txt"]):
        if len(r) >= 3 and r[0].isdigit() and r[2].isdigit():
            groups.setdefault(r[2], int(r[0]))

    idx, name_list, group_list, codes = {}, [], [], {}
    subst_idx, subst_list, ns_list = {}, [], []
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
            lab = labels.get(cis)
            if lab and lab not in subst_idx:
                subst_idx[lab] = len(subst_list)
                subst_list.append(lab)
            ns_list.append(subst_idx[lab] if lab else -1)
        codes[cip13] = [idx[cis], units_from_label(label)]

    if len(codes) < 1000:
        raise SystemExit(f"Trop peu de présentations lues ({len(codes)}) : format des fichiers inattendu ?")
    out = {"v": datetime.date.today().isoformat(), "n": name_list, "g": group_list, "s": subst_list, "ns": ns_list, "c": codes}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    with_units = sum(1 for v in codes.values() if v[1])
    with_subst = sum(1 for v in ns_list if v >= 0)
    print(f"{len(codes)} présentations, {len(name_list)} médicaments, {with_units} avec le nombre d'unités, "
          f"{with_subst} avec la substance ({len(subst_list)} substances et dosages) -> {OUT}")
    for lab in subst_list[:15]:
        print("  ", lab)


if __name__ == "__main__":
    main()
