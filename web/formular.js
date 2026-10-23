// Zuordnung per Formular: Immobilien (Konto, Wertpapier, Darlehen, Stammdaten), Zinsbindungen,
// weitere Konten und Depots. Liefert einen "Stand", aus dem formular.config_bauen() die
// config.yaml baut. Kennt nur Daten aus der Datei und einer geladenen Config.
'use strict';

window.Formular = (() => {
  const GRUPPE_TEXT = {
    'Liquidität': 'Liquidität', 'Immobilien-Konten': 'Immobilien-Konto', 'Darlehen': 'Darlehen',
    'P2P': 'P2P-Kredite', 'Krypto-Konten': 'Krypto', 'Wertpapiere': 'Wertpapiere', 'Immobilien': 'Immobilien',
  };
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const eur = (v) => new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format(v);

  function zeigen(el, daten, aktionen) {
    const saldo = Object.fromEntries(daten.konten.map((k) => [k.name, k.saldo]));
    const depotVon = Object.fromEntries(daten.wertpapiere.map((w) => [w.name, w.depot]));
    const st = {
      objekte: daten.objekte.map((o) => ({ ...o, darlehen: [...o.darlehen], alleKonten: false })),
      konten_gruppe: Object.fromEntries(daten.konten.map((k) => [k.name, k.gruppe])),
      depot_gruppe: Object.fromEntries(daten.depots.map((d) => [d.name, d.gruppe])),
      zinsbindungen: JSON.parse(JSON.stringify(daten.zinsbindungen || {})),
    };
    if (!st.objekte.length) st.objekte.push(neuesObjekt());

    function neuesObjekt() {
      const nr = String(Math.max(0, ...st.objekte?.map((o) => +o.nr) ?? []) + 1);
      return { nr, name: '', konto: '', wertpapier: '', darlehen: [], selbstgenutzt: false,
               lage: '', lage_anonym: '', baujahr: null, wohnflaeche_m2: null, alleKonten: false };
    }
    const vergeben = () => {
      const m = {};
      for (const o of st.objekte) {
        if (o.konto) m[o.konto] = o.nr;
        for (const d of o.darlehen) m[d] = o.nr;
      }
      return m;
    };
    const darlehenListe = () => {
      const v = vergeben();
      const aus = st.objekte.flatMap((o) => o.darlehen);
      const weitere = daten.konten.filter((k) => !(k.name in v) && st.konten_gruppe[k.name] === 'Darlehen').map((k) => k.name);
      return [...new Set([...aus, ...weitere])];
    };

    function kontoOptionen(gewaehlt, nr) {
      const v = vergeben();
      return '<option value="">— keins —</option>' + daten.konten.map((k) => {
        const belegt = v[k.name] && v[k.name] !== nr;
        return `<option value="${esc(k.name)}"${k.name === gewaehlt ? ' selected' : ''}${belegt ? ' disabled' : ''}>` +
          `${esc(k.name)} (${eur(k.saldo)})${belegt ? ' · Objekt ' + esc(v[k.name]) : ''}</option>`;
      }).join('');
    }

    function wpOptionen(gewaehlt) {
      return '<option value="">— keins —</option>' + daten.wertpapiere.map((w) =>
        `<option value="${esc(w.name)}"${w.name === gewaehlt ? ' selected' : ''}>${esc(w.name)}` +
        `${w.wert ? ' (' + eur(w.wert) + (w.depot ? ', ' + esc(w.depot) : '') + ')' : ''}</option>`).join('');
    }

    function darlehenAuswahl(o) {
      const v = vergeben();
      const kandidaten = daten.konten.filter((k) => o.alleKonten || o.darlehen.includes(k.name) ||
        k.saldo < 0 || k.gruppe === 'Darlehen');
      const liste = kandidaten.filter((k) => k.name !== o.konto).map((k) => {
        const belegt = v[k.name] && v[k.name] !== o.nr;
        return `<label class="wahl${belegt ? ' belegt' : ''}"><input type="checkbox" data-o="${esc(o.nr)}" data-feld="darlehen" value="${esc(k.name)}"` +
          `${o.darlehen.includes(k.name) ? ' checked' : ''}${belegt ? ' disabled' : ''}> ${esc(k.name)} <span class="leise">${eur(k.saldo)}` +
          `${belegt ? ' · Objekt ' + esc(v[k.name]) : ''}</span></label>`;
      }).join('') || '<p class="leise">Kein Konto mit negativem Saldo.</p>';
      return liste + `<button type="button" class="knopf leise-knopf" data-o="${esc(o.nr)}" data-aktion="alle">` +
        `${o.alleKonten ? 'Nur Konten im Minus zeigen' : 'Alle Konten zeigen'}</button>`;
    }

    function objektKarte(o) {
      const fehlt = [];
      if (!o.konto) fehlt.push('Konto');
      if (!o.wertpapier) fehlt.push('Wertpapier (sonst Verkehrswert 0)');
      const feld = (f, label, typ = 'text', extra = '') =>
        `<label>${label}<input type="${typ}" data-o="${esc(o.nr)}" data-feld="${f}" value="${esc(o[f] ?? '')}" ${extra}></label>`;
      return `<fieldset class="objekt-form">
        <legend>Immobilie ${esc(o.nr)}</legend>
        <div class="raster">
          ${feld('name', 'Bezeichnung', 'text', 'placeholder="z. B. Wohnung Musterstraße"')}
          <label>Konto für Miete und Kosten<select data-o="${esc(o.nr)}" data-feld="konto">${kontoOptionen(o.konto, o.nr)}</select></label>
          <label>Wertpapier mit dem Verkehrswert<select data-o="${esc(o.nr)}" data-feld="wertpapier">${wpOptionen(o.wertpapier)}</select></label>
          <label class="schalter"><input type="checkbox" data-o="${esc(o.nr)}" data-feld="selbstgenutzt"${o.selbstgenutzt ? ' checked' : ''}> selbst bewohnt</label>
        </div>
        <div class="unterfeld"><span class="feldname">Darlehen</span>${darlehenAuswahl(o)}</div>
        <details class="mehr"><summary>Objektdaten (optional)</summary><div class="raster">
          ${feld('lage', 'Adresse', 'text', 'placeholder="Ort, Straße Nr."')}
          ${feld('lage_anonym', 'Ort für die anonyme Fassung', 'text', 'placeholder="Ort oder Stadtteil"')}
          ${feld('baujahr', 'Baujahr', 'number', 'min="1700" max="2100" step="1"')}
          ${feld('wohnflaeche_m2', 'Wohnfläche m²', 'number', 'min="0" step="0.1"')}
        </div></details>
        ${fehlt.length ? `<p class="fehlt">Fehlt: ${fehlt.join(', ')}</p>` : ''}
        <button type="button" class="knopf leise-knopf" data-o="${esc(o.nr)}" data-aktion="weg">Immobilie entfernen</button>
      </fieldset>`;
    }

    function zinsKarte(name) {
      const z = st.zinsbindungen[name] || (st.zinsbindungen[name] = { ende: '', sollzins: null, nennbetrag: null, sondertilgung: null, kfw: false });
      const f = (feld, label, typ, extra = '') =>
        `<label>${label}<input type="${typ}" data-z="${esc(name)}" data-feld="${feld}" value="${esc(z[feld] ?? '')}" ${extra}></label>`;
      const unvollstaendig = (z.ende && (z.sollzins === null || z.sollzins === '')) || (!z.ende && z.sollzins);
      return `<div class="zins"><h3>${esc(name)} <span class="leise">${eur(saldo[name] ?? 0)}</span></h3><div class="raster">
        ${f('ende', 'Zinsbindung bis', 'date')}
        ${f('sollzins', 'Sollzins %', 'number', 'step="0.01" min="0"')}
        ${f('nennbetrag', 'Darlehensbetrag €', 'number', 'step="1" min="0"')}
        ${f('sondertilgung', 'Sondertilgung € pro Jahr', 'number', 'step="1" min="0"')}
        <label class="schalter"><input type="checkbox" data-z="${esc(name)}" data-feld="kfw"${z.kfw ? ' checked' : ''}> KfW-Darlehen</label>
      </div>${unvollstaendig ? '<p class="fehlt">Für die Fälligkeitsleiste braucht es Datum und Sollzins.</p>' : ''}</div>`;
    }

    function render() {
      const v = vergeben();
      const weitere = daten.konten.filter((k) => !(k.name in v));
      const gruppeWahl = (attr, name, gruppen, aktuell) => `<select ${attr}="${esc(name)}">` +
        gruppen.map((g) => `<option value="${esc(g)}"${g === aktuell ? ' selected' : ''}>${esc(GRUPPE_TEXT[g] || g)}</option>`).join('') + '</select>';
      const darlehen = darlehenListe();
      el.innerHTML = `
        <h2>Zuordnung bearbeiten</h2>
        <p class="leise">Ordne jeder Immobilie ihr Konto, ihr Wertpapier und ihre Darlehen zu. Die Namen in Portfolio Performance bleiben, wie sie sind.</p>
        <h3 class="abschnitt">Immobilien</h3>
        ${st.objekte.map(objektKarte).join('')}
        <button type="button" class="knopf" data-aktion="neu">+ Immobilie hinzufügen</button>

        <h3 class="abschnitt">Darlehen und Zinsbindung</h3>
        ${darlehen.length ? darlehen.map(zinsKarte).join('') : '<p class="leise">Noch kein Darlehen zugeordnet.</p>'}

        <h3 class="abschnitt">Weitere Konten</h3>
        <div class="tabelle"><table><tbody>${weitere.map((k) => `<tr><td>${esc(k.name)}${k.aufgeloest ? ' <span class="leise">(aufgelöst)</span>' : ''}</td>
          <td class="zahl">${eur(k.saldo)}</td><td>${gruppeWahl('data-kg', k.name, daten.gruppen_konto, st.konten_gruppe[k.name])}</td></tr>`).join('')}
        </tbody></table></div>

        <h3 class="abschnitt">Depots</h3>
        <div class="tabelle"><table><tbody>${daten.depots.map((d) => `<tr><td>${esc(d.name)}</td>
          <td>${gruppeWahl('data-dg', d.name, daten.gruppen_depot, st.depot_gruppe[d.name])}</td></tr>`).join('')}
        </tbody></table></div>

        <div class="reihe knopfleiste">
          <button type="button" class="knopf haupt" data-aktion="uebernehmen">Übernehmen und neu rechnen</button>
          <button type="button" class="knopf" data-aktion="laden">config.yaml herunterladen</button>
          <button type="button" class="knopf leise-knopf" data-aktion="abbrechen">Abbrechen</button>
        </div>`;
    }

    const objekt = (nr) => st.objekte.find((o) => o.nr === nr);
    const stand = () => ({
      objekte: st.objekte.map(({ alleKonten, ...o }) => o),
      konten_gruppe: st.konten_gruppe, depot_gruppe: st.depot_gruppe,
      zinsbindungen: Object.fromEntries(darlehenListe().map((n) => [n, st.zinsbindungen[n] || {}])),
    });

    el.oninput = (ev) => {
      const t = ev.target;
      if (t.dataset.o && t.type !== 'checkbox' && t.tagName === 'INPUT') objekt(t.dataset.o)[t.dataset.feld] = t.value;
      if (t.dataset.z && t.type !== 'checkbox') st.zinsbindungen[t.dataset.z][t.dataset.feld] = t.value;
    };
    el.onchange = (ev) => {
      const t = ev.target;
      if (t.dataset.o) {
        const o = objekt(t.dataset.o);
        if (t.dataset.feld === 'darlehen') {
          o.darlehen = t.checked ? [...o.darlehen, t.value] : o.darlehen.filter((d) => d !== t.value);
        } else if (t.type === 'checkbox') {
          o[t.dataset.feld] = t.checked;
        } else if (t.tagName === 'SELECT') {
          o[t.dataset.feld] = t.value;
          o.darlehen = o.darlehen.filter((d) => d !== o.konto);
          // Das Depot mit dem Immobilien-Wertpapier zaehlt als Immobilien-Depot.
          if (t.dataset.feld === 'wertpapier' && depotVon[t.value]) st.depot_gruppe[depotVon[t.value]] = 'Immobilien';
          if (t.dataset.feld === 'konto' && !o.name && t.value) o.name = t.value;
        } else {
          return;
        }
        render();
      } else if (t.dataset.z && t.type === 'checkbox') {
        st.zinsbindungen[t.dataset.z].kfw = t.checked;
      } else if (t.dataset.kg) {
        st.konten_gruppe[t.dataset.kg] = t.value;
        render();
      } else if (t.dataset.dg) {
        st.depot_gruppe[t.dataset.dg] = t.value;
      } else if (t.dataset.z) {
        render();
      }
    };
    el.onclick = (ev) => {
      const t = ev.target.closest('[data-aktion]');
      if (!t) return;
      const a = t.dataset.aktion;
      if (a === 'neu') { st.objekte.push(neuesObjekt()); render(); }
      if (a === 'weg') { st.objekte = st.objekte.filter((o) => o.nr !== t.dataset.o); render(); }
      if (a === 'alle') { const o = objekt(t.dataset.o); o.alleKonten = !o.alleKonten; render(); }
      if (a === 'uebernehmen') aktionen.uebernehmen(stand());
      if (a === 'laden') aktionen.herunterladen(stand());
      if (a === 'abbrechen') aktionen.abbrechen();
    };
    render();
  }

  return { zeigen };
})();
