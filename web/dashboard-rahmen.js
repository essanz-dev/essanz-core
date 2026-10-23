// Nimmt das fertige Dashboard-HTML von der Essanz-Seite (gleiche Herkunft) entgegen und zeigt es.
// Meldet danach die Hoehe zurueck, damit der Rahmen ohne eigenen Scrollbalken auskommt.
'use strict';

window.addEventListener('message', (ev) => {
  if (ev.origin !== location.origin || ev.source !== window.parent) return;
  if (typeof ev.data !== 'object' || ev.data.art !== 'dashboard') return;
  document.open();
  document.write(ev.data.html);
  document.close();
  const melden = () => window.parent.postMessage(
    { art: 'hoehe', hoehe: document.documentElement.scrollHeight }, location.origin);
  new ResizeObserver(melden).observe(document.documentElement);
  melden();
});

window.parent.postMessage({ art: 'bereit' }, location.origin);
