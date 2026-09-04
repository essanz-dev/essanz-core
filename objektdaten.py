# -*- coding: utf-8 -*-
"""Stammdaten je Objekt und je Darlehen: Zinsbindung, Objektsteckbrief, hergeleiteter
Verkehrswert.

Alles, was nicht aus der .portfolio-Datei folgt, sondern von Hand aus Vertrags- und
Kaufunterlagen stammt, wird hier bereitgestellt — aber anders als frueher NICHT als
Python-Konstante in dieser Datei, sondern aus der externen Konfiguration (config.py),
damit dieses Modul ohne persönliche Daten im Repo liegen kann.

analyze.py ruft nur die drei Funktionen unten auf; wie die Werte hinterlegt sind, ist
dafür unsichtbar.
"""
import config


def zinsbindung_fuer(konto):
    """Liefert die Zinsbindungsdaten fuer ein Darlehenskonto, oder None."""
    return config.zinsbindungen().get(konto)


def stamm_fuer(objekt_no, anonym=False):
    """Liefert die Objektstammdaten fuer eine Objektnummer (als String oder Zahl).

    Mit anonym=True: 'lage' wird auf die in 'lage_anonym' hinterlegte Stadt-/
    Stadtteil-Angabe ohne Strasse und Hausnummer verkuerzt, 'mieter_name' entfaellt.
    """
    s = config.objektstamm().get(str(objekt_no))
    if not s or not anonym:
        return s
    s2 = dict(s)
    s2['lage'] = s.get('lage_anonym', s.get('lage'))
    s2['mieter_name'] = None
    return s2


def verkehrswert_fuer(objekt_no):
    return config.verkehrswert_herleitung().get(str(objekt_no))
