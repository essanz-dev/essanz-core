# -*- coding: utf-8 -*-
"""Lädt die persönliche Konfiguration (Objektstammdaten, Steuerwerte, Kontokonventionen,
Wechselkurse) aus einer YAML-Datei.

Diese Datei enthält bewusst KEINE persönlichen Daten. Alles, was frueher hier oder in
objektdaten.py/steuer.py als Python-Konstante hartcodiert war, kommt jetzt aus einer externen
Konfigurationsdatei, die NICHT Teil dieses Repos ist (siehe .gitignore).

Reihenfolge, in der der Pfad gesucht wird:
  1. Umgebungsvariable ESSANZ_CONFIG
  2. 'config.yaml' im aktuellen Arbeitsverzeichnis
  3. 'config.example.yaml' neben diesem Modul (Demo-Daten, frei erfunden)

Wer eigene Daten hat: config.example.yaml nach config.yaml kopieren und mit den eigenen
Werten befuellen. Das Schema steht in config.example.yaml als Kommentar.
"""
import os
import re
import functools

try:
    import yaml
except ImportError:
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))


class ConfigFehler(Exception):
    """Konfiguration fehlt oder ist nicht lesbar; die Meldung ist fuer Nutzer:innen gedacht."""


def _find_path():
    env = os.environ.get('ESSANZ_CONFIG')
    if env:
        return env
    local = os.path.join(os.getcwd(), 'config.yaml')
    if os.path.exists(local):
        return local
    return os.path.join(HERE, 'config.example.yaml')


@functools.lru_cache(maxsize=1)
def load():
    """Laedt und cached die Konfiguration. Erneut aufrufen nach os.environ-Aenderung: load.cache_clear()."""
    if yaml is None:
        raise ConfigFehler(
            "Das Paket 'pyyaml' fehlt. Installieren mit: pip install pyyaml")
    path = _find_path()
    if not os.path.exists(path):
        raise ConfigFehler(
            f"Keine Konfiguration gefunden unter {path}. Kopiere config.example.yaml nach "
            "config.yaml und trage deine eigenen Werte ein, oder setze ESSANZ_CONFIG.")
    try:
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        ort = getattr(e, 'problem_mark', None)
        zeile = f' (Zeile {ort.line + 1}, Spalte {ort.column + 1})' if ort else ''
        raise ConfigFehler(
            f"Die Konfiguration {path} ist kein gültiges YAML{zeile}: "
            f"{getattr(e, 'problem', None) or e}. Häufige Ursache: Tabulator statt Leerzeichen "
            "oder ein Doppelpunkt im Text ohne Anführungszeichen.") from None
    if not isinstance(data, dict):
        raise ConfigFehler(f"Die Konfiguration {path} muss aus Abschnitten wie 'zinsbindungen:' "
                           "bestehen, gefunden wurde etwas anderes.")
    data['_pfad'] = path
    return data


def pfad():
    return load().get('_pfad')


# ---------------------------------------------------------------------------
# Objektdaten (frueher objektdaten.py)
def zinsbindungen():
    return load().get('zinsbindungen', {})


def objektstamm():
    return load().get('objektstamm', {})


def verkehrswert_herleitung():
    return load().get('verkehrswert_herleitung', {})


# ---------------------------------------------------------------------------
# Steuerdaten (frueher steuer.py)
def steuer():
    s = load().get('steuer') or {}
    for no, e in (s.get('afa') or {}).items():
        if not isinstance(e, dict):
            raise ConfigFehler(f"steuer.afa: Eintrag für Objekt {no} muss die Felder satz, betrag "
                               "und eigentum haben, z. B. {satz: 2.0, betrag: 1500, eigentum: \"Alleineigentum\"}.")
    return dict(
        grenzsteuersatz=s.get('grenzsteuersatz', 0.0),
        durchschnittsatz=s.get('durchschnittsatz', 0.0),
        soli=s.get('soli', 0.0),
        kirchensteuer=s.get('kirchensteuer', 0.0),
        quelle=s.get('quelle', ''),
        jahr=s.get('jahr', ''),
        zve=s.get('zve', 0.0),
        afa=s.get('afa', {}),
        ergebnis=s.get('ergebnis', {}),
        anlage_v_zeile85=s.get('anlage_v_zeile85', {}),
        beteiligung=s.get('beteiligung', 0.0),
        vuv_person1=s.get('vuv_person1', 0.0),
        vuv_person2=s.get('vuv_person2', 0.0),
        historie=s.get('historie', []),
    )


# ---------------------------------------------------------------------------
# Allgemeine Einstellungen (frueher Konstanten in analyze.py)
def allgemein():
    a = load().get('allgemein', {})
    return dict(
        fx=a.get('fx', {'EUR': 1.0}),
        fx_date=a.get('fx_date', ''),
        selbstgenutzt=set(str(x) for x in a.get('selbstgenutzt', [])),
        ruecklage_eur_m2_monat_altbau=a.get('ruecklage_eur_m2_monat_altbau', 1.10),
        ruecklage_eur_m2_monat_neubau=a.get('ruecklage_eur_m2_monat_neubau', 0.80),
        anschluss_stress_pp=a.get('anschluss_stress_pp', 2.0),
        capex_words=tuple(a.get('capex_words', DEFAULT_CAPEX_WORDS)),
        gift_words=tuple(a.get('gift_words', DEFAULT_GIFT_WORDS)),
        fin_words=tuple(a.get('fin_words', DEFAULT_FIN_WORDS)),
        p2p_konten=tuple(a.get('p2p_konten', ())),
        krypto_konten=tuple(a.get('krypto_konten', ())),
        kontoname_anonym=a.get('kontoname_anonym', {}),
        benchmarks=a.get('benchmarks', DEFAULT_BENCHMARKS),
    )


# ---------------------------------------------------------------------------
# Kontenzuordnung (frueher fest in analyze.Book.classify)
GRUPPEN_KONTO = ('Liquidität', 'Immobilien-Konten', 'Darlehen', 'P2P', 'Krypto-Konten')
GRUPPEN_DEPOT = ('Wertpapiere', 'Immobilien')

DEFAULT_KONTEN = dict(
    darlehen_praefix=['Darlehenskonto'],
    immobilien_konto_praefix=['Immobilie '],
    immobilien_depot_praefix=['Immo'],
    objekt_muster=r'Immobilie (\d+): (.*)',
    darlehen_muster=r'Darlehenskonto (\d+)',
    konten_gruppe={'Immobilien Rücklagenkonto': 'Immobilien-Konten',
                   'Tagesgeldkonto Immo': 'Immobilien-Konten'},
    depot_gruppe={'Immo Depot': 'Wertpapiere'},
    objekte={},
)


def konten():
    """Regeln, nach denen Konten, Depots und Objekte erkannt werden.

    Ohne Abschnitt 'konten:' gilt die Essanz-Konvention (DEFAULT_KONTEN). Listen und Muster
    aus der Config ersetzen die Voreinstellung, die Zuordnungen nach exaktem Namen
    (konten_gruppe, depot_gruppe) ergaenzen sie. Die alten Listen allgemein.p2p_konten und
    allgemein.krypto_konten gelten weiter.
    """
    k = load().get('konten') or {}
    a = load().get('allgemein') or {}
    out = {key: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v)
           for key, v in DEFAULT_KONTEN.items()}
    for key in ('darlehen_praefix', 'immobilien_konto_praefix', 'immobilien_depot_praefix',
                'objekt_muster', 'darlehen_muster'):
        if key in k:
            v = k[key]
            out[key] = ([] if v is None else [v] if isinstance(v, str) else list(v)) \
                if key.endswith('praefix') else (v or None)
    for n in a.get('p2p_konten', ()) or ():
        out['konten_gruppe'][n] = 'P2P'
    for n in a.get('krypto_konten', ()) or ():
        out['konten_gruppe'][n] = 'Krypto-Konten'
    out['konten_gruppe'].update(k.get('konten_gruppe') or {})
    out['depot_gruppe'].update(k.get('depot_gruppe') or {})
    out['objekte'] = {str(no): dict(o or {}) for no, o in (k.get('objekte') or {}).items()}
    for no in out['objekte']:
        if not no.isdigit():
            raise ConfigFehler(f"konten.objekte: Objektnummer {no!r} ist keine Zahl. Die Nummer "
                               "verbindet das Objekt mit objektstamm und steuer.afa, z. B. \"1\".")
    for name, g in out['konten_gruppe'].items():
        if g not in GRUPPEN_KONTO:
            raise ConfigFehler(f"konten.konten_gruppe: Gruppe {g!r} für {name!r} gibt es nicht. "
                               f"Möglich: {', '.join(GRUPPEN_KONTO)}.")
    for name, g in out['depot_gruppe'].items():
        if g not in GRUPPEN_DEPOT:
            raise ConfigFehler(f"konten.depot_gruppe: Gruppe {g!r} für {name!r} gibt es nicht. "
                               f"Möglich: {', '.join(GRUPPEN_DEPOT)}.")
    for key in ('objekt_muster', 'darlehen_muster'):
        if out[key]:
            try:
                rx = re.compile(out[key])
            except re.error as e:
                raise ConfigFehler(f"konten.{key}: {out[key]!r} ist kein gültiges Muster ({e}).") from None
            if rx.groups < (2 if key == 'objekt_muster' else 1):
                raise ConfigFehler(f"konten.{key}: Das Muster braucht "
                                   + ("zwei Klammergruppen (Nummer, Name)" if key == 'objekt_muster'
                                      else "eine Klammergruppe (Objektnummer)") + ".")
    return out


# Sinnvolle deutsche Standardwoerter, falls in der Konfiguration nichts angegeben ist.
# Wer andere Buchungstexte verwendet, ueberschreibt diese Listen in config.yaml.
DEFAULT_CAPEX_WORDS = (
    'dach', 'solar', 'heizung', 'gastherme', 'schreiner', 'architekt', 'daemm', 'dämm',
    'fenster', 'sanier', 'modernis', 'kueche', 'küche', 'balkonkraftwerk', 'geruest',
    'gerüst', 'handwerker', 'elektro')
DEFAULT_GIFT_WORDS = ('schenkung', 'pflichtteil', 'erbschaft', 'erbteil', 'nachlass', 'geschenk')
DEFAULT_FIN_WORDS = ('kredit', 'finanzierung', 'darlehen', 'kaution', 'förderung', 'foerderung',
                      'bafa', 'zuschuss')
DEFAULT_BENCHMARKS = [
    dict(label='MSCI World', security='MSCI World', kurz='MSCI World',
         art='Vergleichsindex, so wie er in Portfolio Performance beobachtet wird.',
         leitindex=True),
]
