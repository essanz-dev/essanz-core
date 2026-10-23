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
  letzte = { bytes, name: dateiname, stichtag, cfg };
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

function speichern() {
  if (!letzte?.html) return;
  const tag = letzte.stichtag.replaceAll('-', '') + (letzte.anonym ? '_anonym' : '');
  const url = URL.createObjectURL(new Blob([letzte.html], { type: 'text/html;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `Dashboard_${tag}.html`;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function zeigeFehler(r, dateiname) {
  const el = $('ergebnis');
  el.hidden = false;
  el.innerHTML = `<section class="karte"><h2>${esc(dateiname)}</h2>
    <div class="meldung Fehler"><b>Fehler</b>${esc(r.fehler)}</div>
    ${r.details ? `<details class="technik"><summary>Technische Details (für ein Issue, ohne Kontonamen)</summary><pre>${esc(r.details)}</pre></details>` : ''}
  </section>`;
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
    : '<p class="fehlt">Keine Immobilie erkannt.</p>';

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
      <p><a href="#dashboard">Zum Dashboard ↓</a></p>
    </section>
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
    </section>`;
  $('speichern').addEventListener('click', speichern);
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

$('datei').addEventListener('change', async (ev) => {
  const f = ev.target.files[0];
  if (!f) return;
  status(`Lese ${f.name} …`);
  pruefen(new Uint8Array(await f.arrayBuffer()), f.name);
  ev.target.value = '';
});

$('demo').addEventListener('click', () => {
  // Die Beispieldatei passt zur mitgelieferten Beispiel-Config, deshalb ohne eigene Config.
  if (!$('stichtag').value) $('stichtag').value = '2026-08-31';
  pruefen(py.FS.readFile('/essanz/beispiel.portfolio'), 'beispiel.portfolio', null);
});

$('config').addEventListener('change', async (ev) => {
  const f = ev.target.files[0];
  if (!f) return;
  eigeneConfig = { name: f.name, text: await f.text() };
  $('config-name').textContent = `Config: ${f.name}`;
  $('config-weg').hidden = false;
  ev.target.value = '';
});

$('config-weg').addEventListener('click', () => {
  eigeneConfig = null;
  $('config-name').textContent = 'Ohne eigene Config gilt die Essanz-Namenskonvention.';
  $('config-weg').hidden = true;
});

start();
