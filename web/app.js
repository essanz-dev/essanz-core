// Essanz im Browser (Prototyp): laedt den Python-Kern in Pyodide und zeigt die Diagnose.
// Die .portfolio-Datei wird mit FileReader gelesen und nur in den Speicher von Pyodide
// geschrieben (MEMFS). Es gibt keine Anfrage, die Daten der Nutzer:innen enthaelt.
'use strict';

const $ = (id) => document.getElementById(id);
const statusEl = $('status');
let py = null;
let eigeneConfig = null; // {name, text}

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

def essanz_diagnose(pfad, stichtag, cfg_pfad):
    if cfg_pfad:
        os.environ['ESSANZ_CONFIG'] = cfg_pfad
    else:
        os.environ.pop('ESSANZ_CONFIG', None)
    for m in KERN:
        sys.modules.pop(m, None)
    import config, ppparse
    try:
        import analyze, diagnose
        b = analyze.Book(pfad, stichtag)
        return json.dumps(dict(ok=True, bericht=diagnose.bericht(b, stichtag)))
    except (config.ConfigFehler, ppparse.FormatFehler) as e:
        return json.dumps(dict(ok=False, fehler=str(e)))
    except Exception as e:
        return json.dumps(dict(ok=False, fehler='Unerwarteter Fehler: %s: %s' % (type(e).__name__, e),
                               details=traceback.format_exc()))
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

function pruefen(bytes, dateiname) {
  const t0 = performance.now();
  py.FS.writeFile('/eingabe/datei.portfolio', bytes);
  let cfgPfad = '';
  if (eigeneConfig) {
    py.FS.writeFile('/eingabe/config.yaml', eigeneConfig.text);
    cfgPfad = '/eingabe/config.yaml';
  }
  const stichtag = $('stichtag').value || new Date().toISOString().slice(0, 10);
  const fn = py.globals.get('essanz_diagnose');
  const r = JSON.parse(fn('/eingabe/datei.portfolio', stichtag, cfgPfad));
  fn.destroy();
  // Kopie im Pyodide-Speicher gleich wieder loeschen.
  py.FS.unlink('/eingabe/datei.portfolio');
  const ms = Math.round(performance.now() - t0);
  if (!r.ok) {
    zeigeFehler(r, dateiname);
    status(`Die Datei ${dateiname} ließ sich nicht prüfen.`, true);
    return;
  }
  zeige(r.bericht, dateiname);
  status(`${dateiname} geprüft in ${ms} ms.`);
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
    </section>
    <section class="karte"><h2>Summen zum Stichtag</h2><div class="summen">${summen}</div></section>
    <section class="karte"><h2>Immobilien</h2>${objekte}</section>
    <section class="karte"><h2>Konten</h2><div class="tabelle"><table>
      <thead><tr><th>Konto</th><th>Gruppe</th><th class="zahl">Saldo</th><th>Warum</th></tr></thead>
      <tbody>${konten}</tbody></table></div></section>
    <section class="karte"><h2>Depots</h2><div class="tabelle"><table>
      <thead><tr><th>Depot</th><th>Gruppe</th><th class="zahl">Wert</th><th>Warum</th></tr></thead>
      <tbody>${depots}</tbody></table></div></section>
    ${vorschlag}`;

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
  const merk = eigeneConfig;
  eigeneConfig = null; // die Beispieldatei passt zur Beispiel-Config
  if (!$('stichtag').value) $('stichtag').value = '2026-08-31';
  pruefen(py.FS.readFile('/essanz/beispiel.portfolio'), 'beispiel.portfolio');
  eigeneConfig = merk;
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
