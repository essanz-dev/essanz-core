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
import functools

try:
    import yaml
except ImportError:
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))


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
        raise RuntimeError(
            "Das Paket 'pyyaml' fehlt. Installieren mit: pip install pyyaml")
    path = _find_path()
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Keine Konfiguration gefunden unter {path}. Kopiere config.example.yaml nach "
            "config.yaml und trage deine eigenen Werte ein, oder setze ESSANZ_CONFIG.")
    with open(path, encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
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
    s = load().get('steuer', {})
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
