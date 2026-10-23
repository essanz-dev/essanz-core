// Essanz im Browser (Prototyp): laedt den Python-Kern in Pyodide und zeigt die Diagnose.
// Die .portfolio-Datei wird mit FileReader gelesen und nur in den Speicher von Pyodide
// geschrieben (MEMFS). Es gibt keine Anfrage, die Daten der Nutzer:innen enthaelt.
'use strict';

const $ = (id) => document.getElementById(id);
const statusEl = $('status');
let py = null;
let eigeneConfig = null; // {name, text}
let letzte = null; // {bytes, name, stichtag, cfg}: zuletzt gepruefte Datei, nur im Speicher dieser Seite
let anonymGewaehlt = false;
const MERK_SCHLUESSEL = 'essanz.config';

function status(text, fehler = false) {
  statusEl.textContent = text;
  statusEl.classList.toggle('fehler', fehler);
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

const eurFmt = new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' });
const eur = (v) => eurFmt.format(v);

// Python-Seite: Module bei jedem Lauf frisch laden, weil analyze.py die Config beim Import liest.
const PY_GLUE = `
import json, os, sys, traceback
sys.path.insert(0, '/essanz')
KERN = ['analyze', 'config', 'diagnose', 'empfehlungen', 'forecast', 'make_dashboard',
        'objektdaten', 'ppparse', 'schwellen', 'steuer', 'stress']

def _lauf(cfg_pfad, arbeit):
    if cfg_pfad:
        os.environ['ESSANZ_CONFIG'] = cfg_pfad
    else:
        os.environ.pop('ESSANZ_CONFIG', None)
    for m in KERN:
        sys.modules.pop(m, None)
    import config, ppparse
    try:
        return json.dumps(dict(ok=True, **arbeit()))
    except (config.ConfigFehler, ppparse.FormatFehler) as e:
        return json.dumps(dict(ok=False, fehler=str(e)))
    except Exception as e:
        return json.dumps(dict(ok=False, fehler='Unerwarteter Fehler: %s: %s' % (type(e).__name__, e),
                               details=traceback.format_exc()))

def essanz_diagnose(pfad, stichtag, cfg_pfad):
    def arbeit():
        import analyze, diagnose
        return dict(bericht=diagnose.bericht(analyze.Book(pfad, stichtag), stichtag))
    return _lauf(cfg_pfad, arbeit)

def essanz_dashboard(pfad, stichtag, cfg_pfad, anonym):
    def arbeit():
        import analyze, make_dashboard
        d = analyze.build(pfad, stichtag)
        if anonym:
            d = analyze.anonymisieren(d)
        return dict(html=make_dashboard.html(d))
    return _lauf(cfg_pfad, arbeit)

def _basis(basis_pfad):
    import yaml
    if not basis_pfad:
        return {}
    with open(basis_pfad, encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

def essanz_formular(pfad, stichtag, cfg_pfad, basis_pfad):
    def arbeit():
        import analyze, formular
        b = analyze.Book(pfad, stichtag)
        return dict(daten=formular.daten(b, stichtag, _basis(basis_pfad)))
    return _lauf(cfg_pfad, arbeit)

def essanz_config(basis_pfad, stand_json):
    def arbeit():
        import formular
        cfg = formular.config_bauen(_basis(basis_pfad), json.loads(stand_json))
        return dict(yaml=formular.als_yaml(cfg))
    return _lauf('', arbeit)
`;

async function start() {
  const t0 = performance.now();
  try {
    py = await loadPyodide({ indexURL: './pyodide/' });
    await py.loadPackage('pyyaml', { messageCallback: () => {} });
    const manifest = await (await fetch('core/manifest.json')).json();
    py.FS.mkdirTree('/essanz');
    await Promise.all(manifest.dateien.map(async (name) => {
      const r = await fetch('core/' + name);
      if (!r.ok) throw new Error(`core/${name}: HTTP ${r.status}`);
      py.FS.writeFile('/essanz/' + name, new Uint8Array(await r.arrayBuffer()));
    }));
    py.FS.mkdirTree('/eingabe');
    py.runPython(PY_GLUE);
    const s = ((performance.now() - t0) / 1000).toFixed(1);
    $('technik').textContent = `Python ${py.runPython('import sys; sys.version.split()[0]')} · Pyodide ${manifest.pyodide} · geladen in ${s} s`;
    status('Bereit. Wähle deine .portfolio-Datei oder sieh dir die Beispieldatei an.');
    $('datei').disabled = false;
    $('demo').disabled = false;
  } catch (e) {
    status('Python konnte nicht geladen werden: ' + e.message, true);
    console.error(e);
  }
}

function eingabeSchreiben(bytes, cfg) {
  py.FS.writeFile('/eingabe/datei.portfolio', bytes);
  if (cfg) {
    py.FS.writeFile('/eingabe/config.yaml', cfg.text);
    return '/eingabe/config.yaml';
  }
  return '';
}

function eingabeLoeschen() {
  for (const p of ['/eingabe/datei.portfolio', '/eingabe/config.yaml']) {
    try { py.FS.unlink(p); } catch { /* war nicht da */ }
  }
}

function aufruf(name, ...args) {
  const fn = py.globals.get(name);
  try {
    return JSON.parse(fn(...args));
  } finally {
    fn.destroy();
  }
}

function pruefen(bytes, dateiname, cfg = eigeneConfig) {
  const t0 = performance.now();
  const stichtag = $('stichtag').value || new Date().toISOString().slice(0, 10);
  const cfgPfad = eingabeSchreiben(bytes, cfg);
  let r;
  try {
    r = aufruf('essanz_diagnose', '/eingabe/datei.portfolio', stichtag, cfgPfad);
  } finally {
    eingabeLoeschen();
  }
  const ms = Math.round(performance.now() - t0);
  if (!r.ok) {
    letzte = null;
    zeigeFehler(r, dateiname);
    status(`Die Datei ${dateiname} ließ sich nicht prüfen.`, true);
    return;
  }
  letzte = { bytes, name: dateiname, stichtag, cfg, demo: dateiname === 'beispiel.portfolio' && !cfg };
  zeige(r.bericht, dateiname);
  status(`${dateiname} geprüft in ${ms} ms.`);
  if (r.bericht.hinweise.some((h) => h.stufe === 'Fehler')) {
    $('dash-status').textContent = 'Erst die Fehler oben beheben, dann entsteht das Dashboard.';
    return;
  }
  // Kurz warten, damit die Diagnose sichtbar ist, bevor die laengere Rechnung startet.
  setTimeout(dashboardBauen, 30);
}

function dashboardBauen() {
  if (!letzte) return;
  const anonym = anonymGewaehlt = $('anonym').checked;
  $('dash-status').textContent = 'Dashboard wird gerechnet …';
  $('speichern').disabled = true;
  setTimeout(() => {
    const t0 = performance.now();
    const cfgPfad = eingabeSchreiben(letzte.bytes, letzte.cfg);
    let r;
    try {
      r = aufruf('essanz_dashboard', '/eingabe/datei.portfolio', letzte.stichtag, cfgPfad, anonym);
    } finally {
      eingabeLoeschen();
    }
    if (!r.ok) {
      $('dash-status').textContent = 'Das Dashboard ließ sich nicht erstellen: ' + r.fehler;
      if (r.details) console.error(r.details);
      return;
    }
    letzte.html = r.html;
    letzte.anonym = anonym;
    zeigeDashboard(r.html);
    $('speichern').disabled = false;
    $('dash-status').textContent = `Gerechnet in ${((performance.now() - t0) / 1000).toFixed(1)} s` +
      (anonym ? ' · anonymisiert (Adressen gekürzt, Mieternamen entfernt)' : '') + '.';
  }, 20);
}

// Das Dashboard laeuft in dashboard.html: eigene CSP, die seine Inline-Skripte erlaubt, aber
// jede Netzwerkverbindung verbietet. Fuer jede Fassung ein frischer Rahmen.
function zeigeDashboard(html) {
  const alt = $('dash-rahmen');
  const f = document.createElement('iframe');
  f.id = 'dash-rahmen';
  f.title = 'Dashboard';
  f.src = 'dashboard.html';
  alt.replaceWith(f);
  const empfang = (ev) => {
    if (ev.origin !== location.origin || ev.source !== f.contentWindow) return;
    if (ev.data?.art === 'bereit') f.contentWindow.postMessage({ art: 'dashboard', html }, location.origin);
    if (ev.data?.art === 'hoehe') f.style.height = Math.max(400, ev.data.hoehe) + 'px';
  };
  window.addEventListener('message', empfang);
  zeigeDashboard.aufraeumen?.();
  zeigeDashboard.aufraeumen = () => window.removeEventListener('message', empfang);
}

// Grundlage fuer das Formular: die geladene Config, bei der Beispieldatei die Beispiel-Config,
// sonst nichts (damit keine erfundenen Beispielwerte in eine echte Config wandern).
function basisPfad() {
  if (letzte?.cfg) {
    py.FS.writeFile('/eingabe/basis.yaml', letzte.cfg.text);
    return '/eingabe/basis.yaml';
  }
  return letzte?.demo ? '/essanz/config.example.yaml' : '';
}

function formularOeffnen() {
  if (!letzte) return;
  const cfgPfad = eingabeSchreiben(letzte.bytes, letzte.cfg);
  let r;
  try {
    r = aufruf('essanz_formular', '/eingabe/datei.portfolio', letzte.stichtag, cfgPfad, basisPfad());
  } finally {
    eingabeLoeschen();
  }
  const el = $('formular');
  if (!r.ok) {
    el.hidden = false;
    el.innerHTML = `<div class="meldung Fehler"><b>Fehler</b>${esc(r.fehler)}</div>`;
    return;
  }
  el.hidden = false;
  Formular.zeigen(el, r.daten, {
    uebernehmen(stand) {
      const text = configBauen(stand);
      if (text === null) return;
      setzeConfig({ name: 'aus dem Formular', text });
      pruefen(letzte.bytes, letzte.name, eigeneConfig);
    },
    herunterladen(stand) {
      const text = configBauen(stand);
      if (text !== null) herunterladen(text, 'config.yaml', 'text/yaml;charset=utf-8');
    },
    abbrechen() {
      el.hidden = true;
      el.innerHTML = '';
    },
  });
  el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function configBauen(stand) {
  let r;
  try {
    r = aufruf('essanz_config', basisPfad(), JSON.stringify(stand));
  } finally {
    eingabeLoeschen();
  }
  if (!r.ok) {
    alert('Die Zuordnung ließ sich nicht übernehmen: ' + r.fehler);
    return null;
  }
  return r.yaml;
}

function merkenSchreiben() {
  try {
    if ($('merken').checked && eigeneConfig) localStorage.setItem(MERK_SCHLUESSEL, eigeneConfig.text);
    else localStorage.removeItem(MERK_SCHLUESSEL);
  } catch { /* Speicher nicht verfuegbar, dann eben nicht merken */ }
}

function setzeConfig(cfg) {
  eigeneConfig = cfg;
  $('config-name').textContent = cfg ? `Config: ${cfg.name}` : 'Ohne eigene Config gilt die Essanz-Namenskonvention.';
  $('config-weg').hidden = !cfg;
  merkenSchreiben();
}

function herunterladen(text, dateiname, typ) {
  const url = URL.createObjectURL(new Blob([text], { type: typ }));
  const a = document.createElement('a');
  a.href = url;
  a.download = dateiname;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function speichern() {
  if (!letzte?.html) return;
  const tag = letzte.stichtag.replaceAll('-', '') + (letzte.anonym ? '_anonym' : '');
  herunterladen(letzte.html, `Dashboard_${tag}.html`, 'text/html;charset=utf-8');
}

function zeigeFehler(r, dateiname) {
  const el = $('ergebnis');
  el.hidden = false;
  el.innerHTML = `<section class="karte"><h2>${esc(dateiname)}</h2>
    <div class="meldung Fehler"><b>Fehler</b>${esc(r.fehler)}</div>
    ${r.details ? `<details class="technik"><summary>Technische Details (für ein Issue, ohne Kontonamen)</summary><pre>${esc(r.details)}</pre></details>` : ''}
  </section>` + rueckmeldungKarte({ fehler: r.fehler, details: r.details });
  rueckmeldungVerdrahten();
}

// Rueckmeldung ohne Tracking: ein vorausgefuelltes GitHub-Issue oder Text zum Kopieren. Enthaelt nur
// technische Angaben (Anzahlen, Hinweisarten, Fehlerart), keine Konto- oder Objektnamen, keine Betraege.
const ISSUES_NEU = 'https://github.com/essanz-dev/essanz-core/issues/new';
const IMPRESSUM = 'https://essanz-dev.github.io/essanz-app/impressum.html';
let rueckmeldungText = '';

const ohneNamen = (t) => String(t || '').replace(/'[^']*'|„[^“]*“|"[^"]*"/g, '…');

function rueckmeldungKarte(k) {
  const z = [
    '**Was ist passiert, was hast du erwartet?**', '', '(bitte hier beschreiben)', '',
    '---', 'Technische Angaben (automatisch, ohne Namen und Beträge):',
    `- Essanz-Prototyp, ${$('technik').textContent}`,
  ];
  if (k.bericht) {
    const b = k.bericht;
    const n = (st) => b.hinweise.filter((h) => h.stufe === st).length;
    z.push(`- ${b.buchungen} Buchungen, ${b.konten.length} Konten, ${b.depots.length} Depots, ${b.objekte.length} Immobilien erkannt`,
           `- Hinweise: ${n('Fehler')} Fehler, ${n('Warnung')} Warnungen, ${n('Info')} Infos`,
           `- Konfiguration: ${b.beispiel_config ? 'Beispiel' : 'eigene'}`);
    for (const h of b.hinweise.filter((x) => x.stufe !== 'Info')) z.push(`  - ${h.stufe}: ${ohneNamen(h.text).slice(0, 160)}`);
  }
  if (k.fehler) z.push(`- Fehler: ${ohneNamen(k.fehler).slice(0, 300)}`);
  if (k.details) z.push('', '```', ohneNamen(k.details).split('\n').slice(-12).join('\n'), '```');
  rueckmeldungText = z.join('\n');
  return `<section class="karte" id="rueckmeldung"><h2>Rückmeldung</h2>
    <p>Hat etwas nicht gepasst oder gefehlt? Jede Rückmeldung hilft. Deine Datei schickst du dabei nicht mit.</p>
    <div class="reihe">
      <button type="button" class="knopf" id="rm-github">Auf GitHub melden</button>
      <button type="button" class="knopf" id="rm-kopieren">Text kopieren</button>
      <a href="${IMPRESSUM}" target="_blank" rel="noopener">Ohne GitHub-Konto: Kontakt laut Impressum</a>
    </div>
    <details class="mehr"><summary>Was mitgeschickt wird</summary><pre>${esc(rueckmeldungText)}</pre></details>
  </section>`;
}

function rueckmeldungVerdrahten() {
  $('rm-github')?.addEventListener('click', () => {
    const url = `${ISSUES_NEU}?title=${encodeURIComponent('Rückmeldung zur Browser-App')}&body=${encodeURIComponent(rueckmeldungText)}`;
    window.open(url, '_blank', 'noopener');
  });
  $('rm-kopieren')?.addEventListener('click', async (ev) => {
    try { await navigator.clipboard.writeText(rueckmeldungText); ev.target.textContent = 'Kopiert'; }
    catch { ev.target.textContent = 'Bitte unten markieren'; }
  });
}

function gruppe(g) {
  return `<span class="gruppe ${esc(g)}">${esc(g)}</span>`;
}

function zeige(b, dateiname) {
  const hinweise = b.hinweise.length
    ? b.hinweise.map((h) => `<div class="meldung ${esc(h.stufe)}"><b>${esc(h.stufe)}</b>${esc(h.text)}</div>`).join('')
    : '<p class="ok">Keine Hinweise. Die Zuordnung passt zur Konfiguration.</p>';

  const konten = b.konten.map((k) => `<tr class="${k.aufgeloest ? 'aufgeloest' : ''}">
      <td>${esc(k.name)}${k.aufgeloest ? ' <span class="leise">(aufgelöst)</span>' : ''}</td>
      <td>${gruppe(k.gruppe)}</td>
      <td class="zahl">${eur(k.saldo)}${k.waehrung && k.waehrung !== 'EUR' ? ' <span class="leise">' + esc(k.waehrung) + '</span>' : ''}</td>
      <td class="grund">${esc(k.grund)}</td></tr>`).join('');

  const depots = b.depots.map((d) => `<tr><td>${esc(d.name)}</td><td>${gruppe(d.gruppe)}</td>
      <td class="zahl">${eur(d.wert)}</td><td class="grund">${esc(d.grund)}</td></tr>`).join('');

  const feld = (v) => (v ? esc(v) : '<span class="fehlt">fehlt</span>');
  const objekte = b.objekte.length
    ? `<div class="objekte">${b.objekte.map((o) => `<div class="objekt">
        <h3>${esc(o.nr)} · ${esc(o.name)}</h3>
        <dl><dt>Konto</dt><dd>${feld(o.konto)}</dd>
        <dt>Wertpapier</dt><dd>${feld(o.wertpapier)}</dd>
        <dt>Darlehen</dt><dd>${o.darlehen.length ? o.darlehen.map(esc).join(', ') : '<span class="leise">keins</span>'}</dd>
        <dt>Erkannt</dt><dd class="leise">${esc(o.grund)}</dd></dl></div>`).join('')}</div>`
    : '<p class="fehlt">Keine Immobilie erkannt. Ordne sie über „Zuordnung bearbeiten“ zu, oder lies, ' +
      '<a href="#anleitung" id="zur-anleitung">wie Essanz Immobilien in Portfolio Performance erwartet</a>.</p>';

  const summen = b.summen.map((s) => `<div class="summe${s.name === 'Nettovermögen' ? ' netto' : ''}">
      <span>${esc(s.name)}</span><strong>${eur(s.wert)}</strong></div>`).join('');

  const vorschlag = b.vorschlag ? `<section class="karte"><h2>Vorschlag für die config.yaml</h2>
      <p class="leise">Prüfen und anpassen, dann in die eigene config.yaml übernehmen und hier wieder laden.</p>
      <pre id="vorschlag">${esc(b.vorschlag)}</pre>
      <button type="button" class="knopf" id="kopieren">Kopieren</button></section>` : '';

  const el = $('ergebnis');
  el.hidden = false;
  el.innerHTML = `
    <section class="karte">
      <h2>${esc(dateiname)}</h2>
      <p class="leise">Stichtag ${esc(b.stichtag)} · Buchungen von ${esc(b.von)} bis ${esc(b.bis)} · ${b.buchungen} Buchungen ·
        ${b.beispiel_config ? 'Beispiel-Konfiguration' : 'eigene Konfiguration'}</p>
      <h2>Hinweise</h2>${hinweise}
      <div class="reihe knopfleiste">
        <button type="button" class="knopf${b.hinweise.some((h) => h.stufe !== 'Info') || !b.objekte.length ? ' haupt' : ''}" id="formular-auf">Zuordnung bearbeiten</button>
        <a href="#dashboard">Zum Dashboard ↓</a>
      </div>
    </section>
    <section class="karte" id="formular" hidden></section>
    <section class="karte"><h2>Summen zum Stichtag</h2><div class="summen">${summen}</div></section>
    <section class="karte"><h2>Immobilien</h2>${objekte}</section>
    <section class="karte"><h2>Konten</h2><div class="tabelle"><table>
      <thead><tr><th>Konto</th><th>Gruppe</th><th class="zahl">Saldo</th><th>Warum</th></tr></thead>
      <tbody>${konten}</tbody></table></div></section>
    <section class="karte"><h2>Depots</h2><div class="tabelle"><table>
      <thead><tr><th>Depot</th><th>Gruppe</th><th class="zahl">Wert</th><th>Warum</th></tr></thead>
      <tbody>${depots}</tbody></table></div></section>
    ${vorschlag}
    <section class="karte" id="dashboard">
      <h2>Dashboard</h2>
      ${b.hinweise.some((h) => h.stufe === 'Warnung')
        ? '<div class="meldung Warnung"><b>Achtung</b>Die Zuordnung oben hat Warnungen. Die Zahlen im Dashboard können deshalb falsch sein.</div>' : ''}
      <div class="reihe">
        <button type="button" class="knopf haupt" id="speichern" disabled>Als HTML speichern</button>
        <label class="schalter"><input type="checkbox" id="anonym"${anonymGewaehlt ? ' checked' : ''}> Anonymisierte Fassung</label>
      </div>
      <p id="dash-status" class="status"></p>
      <iframe id="dash-rahmen" title="Dashboard" hidden></iframe>
    </section>` + rueckmeldungKarte({ bericht: b });
  rueckmeldungVerdrahten();
  $('speichern').addEventListener('click', speichern);
  $('formular-auf').addEventListener('click', formularOeffnen);
  $('zur-anleitung')?.addEventListener('click', () => { $('anleitung').querySelector('details').open = true; });
  $('anonym').addEventListener('change', dashboardBauen);

  const k = $('kopieren');
  if (k) {
    k.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(b.vorschlag);
        k.textContent = 'Kopiert';
      } catch {
        k.textContent = 'Bitte von Hand markieren';
      }
    });
  }
  el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Mit Passwort gespeicherte Dateien (in Portfolio Performance der Vorschlag fuer neue Dateien):
// 'PORTFOLIO', 1 Byte Verfahren (0 = AES-128, 1 = AES-256), 16 Byte IV, dann AES-CBC. Schluessel
// per PBKDF2-HMAC-SHA1 mit festem Salt und 65536 Runden (wie ClientFactory.Decryptor in PP).
// Entschluesselt wird hier im Browser mit Web Crypto; das Passwort wird nirgends gespeichert.
const PP_SIGNATUR = [80, 79, 82, 84, 70, 79, 76, 73, 79]; // "PORTFOLIO"
const PP_SALT = new Uint8Array([112, 67, 103, 107, 164, 131, 144, 161, 159, 142, 117, 200, 203, 187, 231, 228]);

const istVerschluesselt = (b) => b.length > 26 && PP_SIGNATUR.every((x, i) => b[i] === x);

async function entschluesseln(bytes, passwort) {
  const laenge = bytes[9] === 1 ? 256 : 128;
  const iv = bytes.slice(10, 26);
  const basis = await crypto.subtle.importKey('raw', new TextEncoder().encode(passwort), 'PBKDF2', false, ['deriveKey']);
  const schluessel = await crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt: PP_SALT, iterations: 65536, hash: 'SHA-1' },
    basis, { name: 'AES-CBC', length: laenge }, false, ['decrypt']);
  let klar;
  try {
    klar = new Uint8Array(await crypto.subtle.decrypt({ name: 'AES-CBC', iv }, schluessel, bytes.slice(26)));
  } catch {
    return null; // falsches Passwort zeigt sich meist als ungueltiges Padding
  }
  const ansicht = new DataView(klar.buffer);
  const typ = ansicht.getInt32(0), version = ansicht.getInt32(4);
  if (typ < 1 || typ > 2 || version < 1 || version > 200) return null;
  // Typ 1 = XML, 2 = Binaerformat; beides steckt in einem ZIP, das ppparse.py liest.
  return klar.slice(8);
}

function passwortAbfragen(dateiname) {
  return new Promise((fertig) => {
    const el = $('ergebnis');
    el.hidden = false;
    el.innerHTML = `<section class="karte"><h2>${esc(dateiname)}</h2>
      <p>Die Datei ist mit einem Passwort geschützt. Es wird nur hier im Browser zum Entschlüsseln
        benutzt und weder gespeichert noch gesendet.</p>
      <form id="pw-form" class="reihe">
        <input type="password" id="pw" autocomplete="current-password" placeholder="Passwort aus Portfolio Performance" class="eingabe">
        <button type="submit" class="knopf haupt">Öffnen</button>
        <button type="button" class="knopf leise-knopf" id="pw-weg">Abbrechen</button>
      </form><p id="pw-status" class="status"></p></section>`;
    $('pw').focus();
    $('pw-form').addEventListener('submit', (ev) => { ev.preventDefault(); fertig($('pw').value); });
    $('pw-weg').addEventListener('click', () => { el.hidden = true; el.innerHTML = ''; fertig(null); });
  });
}

async function dateiOeffnen(bytes, name) {
  if (!istVerschluesselt(bytes)) return pruefen(bytes, name);
  for (;;) {
    const pw = await passwortAbfragen(name);
    if (pw === null) { status('Abgebrochen.'); return; }
    status('Entschlüssele …');
    const klar = await entschluesseln(bytes, pw);
    if (klar) return pruefen(klar, name);
    status('Das Passwort passt nicht. Bitte noch einmal.', true);
  }
}

$('datei').addEventListener('change', async (ev) => {
  const f = ev.target.files[0];
  if (!f) return;
  status(`Lese ${f.name} …`);
  const bytes = new Uint8Array(await f.arrayBuffer());
  ev.target.value = '';
  await dateiOeffnen(bytes, f.name);
});

$('demo').addEventListener('click', () => {
  // Die Beispieldatei passt zur mitgelieferten Beispiel-Config, deshalb ohne eigene Config.
  if (!$('stichtag').value) $('stichtag').value = '2026-08-31';
  pruefen(py.FS.readFile('/essanz/beispiel.portfolio'), 'beispiel.portfolio', null);
});

$('config').addEventListener('change', async (ev) => {
  const f = ev.target.files[0];
  if (!f) return;
  setzeConfig({ name: f.name, text: await f.text() });
  ev.target.value = '';
});

$('config-weg').addEventListener('click', () => setzeConfig(null));
$('merken').addEventListener('change', merkenSchreiben);

// Gemerkte Config (nur wenn sie ausdruecklich gemerkt wurde) wieder einsetzen.
try {
  const text = localStorage.getItem(MERK_SCHLUESSEL);
  if (text) {
    $('merken').checked = true;
    setzeConfig({ name: 'in diesem Browser gemerkt', text });
  }
} catch { /* Speicher nicht verfuegbar */ }

start();
