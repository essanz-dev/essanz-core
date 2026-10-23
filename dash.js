'use strict';
const NS='http://www.w3.org/2000/svg';
const el=(t,a={})=>{const n=document.createElementNS(NS,t);for(const k in a)n.setAttribute(k,a[k]);return n;};
const cv=(v,d=0)=>new Intl.NumberFormat('de-DE',{minimumFractionDigits:d,maximumFractionDigits:d}).format(v).replace('-','\u2212');
const eur=(v,d=0)=>cv(v,d)+' €';
const keur=v=>Math.abs(v)>=1e6?cv(v/1e6,2)+' Mio €':cv(Math.round(v/1000))+' T€';
const pct=(v,d=1)=>cv(v,d)+' %';
const sgn=v=>(v>=0?'+':'−')+eur(Math.abs(v));
const MN=['Jan','Feb','Mär','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Dez'];
const mlab=m=>MN[+m.slice(5,7)-1]+' '+m.slice(2,4);
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();

/* ---------- Tooltip ---------- */
const tip=document.getElementById('tip');
function showTip(e,title,rows,total){
  let h='<div class="t">'+title+'</div>';
  for(const r of rows){
    h+='<div class="r"><span>'+(r.c?'<span class="dot" style="background:'+r.c+'"></span>':'')+r.k+
       '</span><span>'+r.v+'</span></div>';
  }
  if(total) h+='<div class="r tot"><span>'+total.k+'</span><span>'+total.v+'</span></div>';
  tip.innerHTML=h; tip.style.opacity=1;
  const b=tip.getBoundingClientRect();
  let x=e.clientX+16, y=e.clientY-b.height/2;
  if(x+b.width>innerWidth-10) x=e.clientX-b.width-16;
  y=Math.max(8,Math.min(y,innerHeight-b.height-8));
  tip.style.left=x+'px'; tip.style.top=y+'px';
}
const hideTip=()=>{tip.style.opacity=0;};
addEventListener('scroll',hideTip,{passive:true});

/* ---------- Achsen-Helfer ---------- */
function ticks(min,max,n){
  const span=max-min; if(span<=0) return [min];
  const raw=span/n, mag=Math.pow(10,Math.floor(Math.log10(raw))), norm=raw/mag;
  const step=(norm<=1?1:norm<=2?2:norm<=2.5?2.5:norm<=5?5:10)*mag;
  const out=[]; for(let v=Math.ceil(min/step)*step; v<=max+1e-9; v+=step) out.push(+v.toFixed(6));
  return out;
}
function frame(svg,W,H,m){
  svg.setAttribute('viewBox','0 0 '+W+' '+H);
  while(svg.firstChild) svg.removeChild(svg.firstChild);
  return {W,H,l:m[3],r:W-m[1],t:m[0],b:H-m[2],iw:W-m[1]-m[3],ih:H-m[0]-m[2]};
}

/* ================= 1. Vermögensentwicklung ================= */
const G1=[['Immobilien','Immobilien','--s1'],['Wertpapiere','Wertpapiere','--s2'],
          ['P2P','P2P-Kredite','--s3'],['CASH','Konten und Liquidität','--s4']];
function chart1(){
  const svg=document.getElementById('c1'); const W=1120,H=360;
  const f=frame(svg,W,H,[14,74,26,8]);
  const M=DATA.months.map(m=>({m:m.month,
    Immobilien:m.Immobilien,Wertpapiere:m.Wertpapiere,P2P:m.P2P,
    CASH:m['Liquidität']+m['Krypto-Konten']+m['Immobilien-Konten'],
    debt:m.Darlehen, net:m.net}));
  const maxA=Math.max(...M.map(d=>G1.reduce((s,g)=>s+d[g[0]],0)));
  const minD=Math.min(...M.map(d=>d.debt));
  const hi=maxA*1.06, lo=minD*1.12;
  const x=i=>f.l+(f.iw*i)/(M.length-1);
  const y=v=>f.b-((v-lo)/(hi-lo))*f.ih;
  const g=el('g',{class:'grid'});
  for(const t of ticks(lo,hi,6)){
    g.appendChild(el('line',{x1:f.l,x2:f.r,y1:y(t),y2:y(t)}));
    const tx=el('text',{x:f.r+8,y:y(t)+4,class:''}); tx.setAttribute('fill',css('--text-muted'));
    tx.setAttribute('font-size','11'); tx.textContent=keur(t); g.appendChild(tx);
  }
  svg.appendChild(g);
  // gestapelte Flächen
  let base=M.map(()=>0);
  G1.forEach(([key,,c])=>{
    const col=css(c);
    let d='M'+x(0)+' '+y(base[0]);
    M.forEach((m,i)=>{d+=' L'+x(i)+' '+y(base[i]+m[key]);});
    for(let i=M.length-1;i>=0;i--) d+=' L'+x(i)+' '+y(base[i]);
    d+='Z';
    svg.appendChild(el('path',{d,fill:col,'fill-opacity':.82,stroke:css('--surface-1'),'stroke-width':1.4}));
    M.forEach((m,i)=>base[i]+=m[key]);
  });
  // Schulden
  let d2='M'+x(0)+' '+y(0);
  M.forEach((m,i)=>{d2+=' L'+x(i)+' '+y(m.debt);});
  d2+=' L'+x(M.length-1)+' '+y(0)+'Z';
  svg.appendChild(el('path',{d:d2,fill:css('--debt'),'fill-opacity':.55}));
  svg.appendChild(el('line',{x1:f.l,x2:f.r,y1:y(0),y2:y(0),class:'zero'}));
  // Netto-Linie
  let dn='';M.forEach((m,i)=>{dn+=(i?'L':'M')+x(i)+' '+y(m.net);});
  svg.appendChild(el('path',{d:dn,fill:'none',stroke:css('--text-primary'),'stroke-width':2.4,
    'stroke-linejoin':'round','stroke-linecap':'round'}));
  const last=M.length-1;
  svg.appendChild(el('circle',{cx:x(last),cy:y(M[last].net),r:4.5,fill:css('--text-primary'),
    stroke:css('--surface-1'),'stroke-width':2}));
  // X-Achse
  M.forEach((m,i)=>{
    if(m.m.slice(5)!=='01'||(+m.m.slice(0,4))%1) return;
    const t=el('text',{x:x(i),y:f.b+18,'text-anchor':'middle','font-size':'11'});
    t.setAttribute('fill',css('--text-muted')); t.textContent=m.m.slice(0,4); svg.appendChild(t);
    svg.appendChild(el('line',{x1:x(i),x2:x(i),y1:f.b,y2:f.b+4,stroke:css('--line-strong')}));
  });
  // Hover
  const cross=el('line',{y1:f.t,y2:f.b,stroke:css('--line-strong'),'stroke-width':1,opacity:0});
  svg.appendChild(cross);
  const hit=el('rect',{x:f.l,y:f.t,width:f.iw,height:f.ih,fill:'transparent'});
  svg.appendChild(hit);
  hit.addEventListener('mousemove',e=>{
    const bb=svg.getBoundingClientRect();
    const px=(e.clientX-bb.left)/bb.width*W;
    const i=Math.max(0,Math.min(M.length-1,Math.round((px-f.l)/f.iw*(M.length-1))));
    const m=M[i];
    cross.setAttribute('x1',x(i)); cross.setAttribute('x2',x(i)); cross.setAttribute('opacity',1);
    const rows=G1.map(([k,l,c])=>({k:l,v:eur(m[k]),c:css(c)}));
    rows.push({k:'Darlehen',v:eur(m.debt),c:css('--debt')});
    showTip(e,mlab(m.m).replace(' ',' 20'),rows,{k:'Nettovermögen',v:eur(m.net)});
  });
  hit.addEventListener('mouseleave',()=>{hideTip();cross.setAttribute('opacity',0);});
  legend('lg1',G1.map(([,l,c])=>[l,css(c)]).concat([['Darlehen',css('--debt')]]),
         [['Nettovermögen',css('--text-primary')]]);
  table('t1',['Monat','Immobilien','Wertpapiere','P2P','Konten','Darlehen','Netto'],
    M.slice().reverse().map(m=>[m.m,eur(m.Immobilien),eur(m.Wertpapiere),eur(m.P2P),
      eur(m.CASH),eur(m.debt),eur(m.net)]));
}

/* ================= 2. Zerlegung ================= */
const G2=[['extern','Sparen und Entnahmen','--s1'],['wp_change','Kursentwicklung Wertpapiere','--s2'],
          ['immo_change','Bewertung Immobilien','--s3'],['laufend','Laufendes Ergebnis','--s4']];
function chart2(){
  const svg=document.getElementById('c2'); const W=1120,H=300;
  const f=frame(svg,W,H,[14,74,26,8]);
  const M=DATA.months.slice(-24);
  let hi=0,lo=0;
  M.forEach(m=>{let p=0,n=0;G2.forEach(([k])=>{const v=m[k];if(v>0)p+=v;else n+=v;});
    hi=Math.max(hi,p);lo=Math.min(lo,n);});
  hi*=1.08; lo*=1.08;
  const bw=Math.min(24,(f.iw/M.length)*0.62);
  const x=i=>f.l+(f.iw/M.length)*(i+0.5);
  const y=v=>f.b-((v-lo)/(hi-lo))*f.ih;
  const g=el('g',{class:'grid'});
  for(const t of ticks(lo,hi,5)){
    g.appendChild(el('line',{x1:f.l,x2:f.r,y1:y(t),y2:y(t)}));
    const tx=el('text',{x:f.r+8,y:y(t)+4,'font-size':'11'});
    tx.setAttribute('fill',css('--text-muted')); tx.textContent=keur(t); g.appendChild(tx);
  }
  svg.appendChild(g);
  M.forEach((m,i)=>{
    let up=0,dn=0;
    G2.forEach(([k,,c])=>{
      const v=m[k]; if(Math.abs(v)<1) return;
      const col=css(c);
      let y0,y1;
      if(v>0){y0=y(up+v);y1=y(up);up+=v;} else {y0=y(dn);y1=y(dn+v);dn+=v;}
      const h=Math.max(0,Math.abs(y1-y0)-2);
      svg.appendChild(el('rect',{x:x(i)-bw/2,y:Math.min(y0,y1),width:bw,height:h,rx:3,fill:col}));
    });
    const hitr=el('rect',{x:x(i)-(f.iw/M.length)/2,y:f.t,width:f.iw/M.length,height:f.ih,fill:'transparent'});
    hitr.addEventListener('mousemove',e=>showTip(e,mlab(m.month).replace(' ',' 20'),
      G2.map(([k,l,c])=>({k:l,v:sgn(m[k]),c:css(c)})),{k:'Veränderung',v:sgn(m.delta)}));
    hitr.addEventListener('mouseleave',hideTip);
    svg.appendChild(hitr);
    if(i%3===0){
      const t=el('text',{x:x(i),y:f.b+18,'text-anchor':'middle','font-size':'11'});
      t.setAttribute('fill',css('--text-muted')); t.textContent=mlab(m.month); svg.appendChild(t);
    }
  });
  svg.appendChild(el('line',{x1:f.l,x2:f.r,y1:y(0),y2:y(0),class:'zero'}));
  legend('lg2',G2.map(([,l,c])=>[l,css(c)]));
  table('t2',['Monat','Sparen/Entnahmen','Wertpapiere','Immobilien','Laufend','Summe'],
    M.slice().reverse().map(m=>[m.month,sgn(m.extern),sgn(m.wp_change),sgn(m.immo_change),
      sgn(m.laufend),sgn(m.delta)]));
}

/* ================= 3. Allokation ================= */
function chart3(){
  const svg=document.getElementById('c3'); const W=520,H=230;
  const f=frame(svg,W,H,[6,8,6,132]);
  const B=Object.entries(DATA.buckets);
  const tot=B.reduce((s,b)=>s+b[1],0);
  const max=Math.max(...B.map(b=>b[1]));
  const rowH=f.ih/B.length, bh=Math.min(18,rowH*0.6);
  B.forEach(([k,v],i)=>{
    const yy=f.t+rowH*i+(rowH-bh)/2;
    const w=Math.max(2,(v/max)*(f.iw-96));
    svg.appendChild(el('rect',{x:f.l,y:yy,width:w,height:bh,rx:3,fill:css('--s1')}));
    const t=el('text',{x:f.l-10,y:yy+bh/2+4,'text-anchor':'end','font-size':'12'});
    t.setAttribute('fill',css('--text-secondary')); t.textContent=k; svg.appendChild(t);
    const val=el('text',{x:f.l+w+9,y:yy+bh/2+4,'font-size':'12','font-weight':'600'});
    val.setAttribute('fill',css('--text-primary'));
    val.textContent=keur(v)+'  ·  '+pct(v/tot*100,0); svg.appendChild(val);
    const hitr=el('rect',{x:0,y:f.t+rowH*i,width:W,height:rowH,fill:'transparent'});
    hitr.addEventListener('mousemove',e=>showTip(e,k,[{k:'Wert',v:eur(v)},
      {k:'Anteil',v:pct(v/tot*100)}]));
    hitr.addEventListener('mouseleave',hideTip); svg.appendChild(hitr);
  });
}

/* ================= 4. Wertentwicklung im Vergleich ================= */
function chart4(){
  const svg=document.getElementById('c4'); const W=520,H=230;
  const f=frame(svg,W,H,[10,54,24,8]);
  const S=DATA.wp_index;
  const SER=[{label:'Eigenes Depot',c:'--s2',pts:S.map(x=>x.index),w:2.2}];
  const BMC=['--s1','--s3','--s4','--s5'];
  (DATA.benchmarks||[]).forEach((b,i)=>SER.push({label:b.label,c:BMC[i%BMC.length],
    pts:b.index.map(x=>x.index),w:1.6}));
  const alle=SER.flatMap(x=>x.pts).filter(v=>v!=null);
  const hi=Math.max(...alle)*1.05, lo=0;
  const x=i=>f.l+(f.iw*i)/(S.length-1);
  const y=v=>f.b-((v-lo)/(hi-lo))*f.ih;
  const g=el('g',{class:'grid'});
  for(const t of ticks(lo,hi,4)){
    g.appendChild(el('line',{x1:f.l,x2:f.r,y1:y(t),y2:y(t)}));
    const tx=el('text',{x:f.r+8,y:y(t)+4,'font-size':'11'});
    tx.setAttribute('fill',css('--text-muted')); tx.textContent=cv(t); g.appendChild(tx);
  }
  svg.appendChild(g);
  SER.forEach((ser,si)=>{
    const col=css(ser.c);
    if(si===0){
      let a='';ser.pts.forEach((v,i)=>{a+=(i?'L':'M')+x(i)+' '+y(v);});
      a+='L'+x(S.length-1)+' '+y(0)+'L'+x(0)+' '+y(0)+'Z';
      svg.appendChild(el('path',{d:a,fill:col,'fill-opacity':.09}));
    }
    let d='';ser.pts.forEach((v,i)=>{if(v==null)return;d+=(d?'L':'M')+x(i)+' '+y(v);});
    svg.appendChild(el('path',{d,fill:'none',stroke:col,'stroke-width':ser.w,
      'stroke-linejoin':'round','stroke-linecap':'round'}));
    const L=ser.pts.length-1, last=ser.pts[L];
    if(last!=null){
      svg.appendChild(el('circle',{cx:x(L),cy:y(last),r:si?3.5:4.5,fill:col,
        stroke:css('--surface-1'),'stroke-width':2}));
      if(si===0){
        const lb=el('text',{x:x(L)-6,y:y(last)-12,'text-anchor':'end','font-size':'12','font-weight':'600'});
        lb.setAttribute('fill',css('--text-primary')); lb.textContent=cv(last,0); svg.appendChild(lb);
      }
    }
  });
  S.forEach((s2,i)=>{
    if(s2.month.slice(5)!=='01'||(+s2.month.slice(0,4))%2) return;
    const t=el('text',{x:x(i),y:f.b+17,'text-anchor':'middle','font-size':'11'});
    t.setAttribute('fill',css('--text-muted')); t.textContent=s2.month.slice(0,4); svg.appendChild(t);
  });
  const cross=el('line',{y1:f.t,y2:f.b,stroke:css('--line-strong'),opacity:0}); svg.appendChild(cross);
  const hit=el('rect',{x:f.l,y:f.t,width:f.iw,height:f.ih,fill:'transparent'}); svg.appendChild(hit);
  hit.addEventListener('mousemove',e=>{
    const bb=svg.getBoundingClientRect(); const px=(e.clientX-bb.left)/bb.width*W;
    const i=Math.max(0,Math.min(S.length-1,Math.round((px-f.l)/f.iw*(S.length-1))));
    cross.setAttribute('x1',x(i)); cross.setAttribute('x2',x(i)); cross.setAttribute('opacity',1);
    showTip(e,mlab(S[i].month).replace(' ',' 20'),
      SER.filter(ser=>ser.pts[i]!=null).map(ser=>({k:ser.label,v:cv(ser.pts[i],1),c:css(ser.c)})),
      {k:'Depotwert',v:eur(S[i].value)});
  });
  hit.addEventListener('mouseleave',()=>{hideTip();cross.setAttribute('opacity',0);});
  legend('lg4',[],SER.map(ser=>[ser.label,css(ser.c)]));
}

/* ================= 5. Immobilien ================= */
function chart5(){
  const svg=document.getElementById('c5'); const W=1120,H=300;
  const f=frame(svg,W,H,[8,178,24,178]);
  const O=DATA.objects.filter(o=>!o.selbstgenutzt)
          .concat(DATA.objects.filter(o=>o.selbstgenutzt));
  const nInv=DATA.objects.filter(o=>!o.selbstgenutzt).length;
  const max=Math.max(...O.map(o=>o.value));
  const rowH=f.ih/O.length, bh=Math.min(24,rowH*0.58);
  O.forEach((o,i)=>{
    const yy=f.t+rowH*i+(rowH-bh)/2;
    const wE=Math.max(0,(o.equity/max)*f.iw), wD=Math.max(0,(o.loan/max)*f.iw);
    if(i===nInv&&nInv>0){
      const sy=f.t+rowH*i-1;
      svg.appendChild(el('line',{x1:f.l-170,x2:f.r,y1:sy,y2:sy,stroke:css('--line-strong')}));
    }
    if(wE>0) svg.appendChild(el('rect',{x:f.l,y:yy,width:wE,height:bh,rx:3,fill:css('--s3')}));
    if(wD>0) svg.appendChild(el('rect',{x:f.l+wE+2,y:yy,width:Math.max(0,wD-2),height:bh,rx:3,fill:css('--debt')}));
    const t=el('text',{x:f.l-12,y:yy+bh/2+4,'text-anchor':'end','font-size':'12'});
    t.setAttribute('fill',css('--text-secondary'));
    t.textContent=o.no+' · '+o.name+(o.selbstgenutzt?'  (Eigennutzung)':''); svg.appendChild(t);
    const val=el('text',{x:f.l+wE+wD+10,y:yy+bh/2+4,'font-size':'12'});
    val.setAttribute('fill',css('--text-primary'));
    val.textContent=keur(o.value)+'  ·  '+pct(o.ltv,0)+' beliehen'; svg.appendChild(val);
    const hitr=el('rect',{x:0,y:f.t+rowH*i,width:W,height:rowH,fill:'transparent'});
    hitr.addEventListener('mousemove',e=>showTip(e,o.no+' · '+o.name+
      (o.selbstgenutzt?' (Eigennutzung)':''),[
      {k:'Verkehrswert',v:eur(o.value)},
      {k:'Eigenkapital',v:eur(o.equity),c:css('--s3')},
      {k:'Restschuld',v:eur(o.loan),c:css('--debt')},
      {k:'Kaltmiete 12M',v:eur(o.rent12)},
      {k:'Zins 12M',v:eur(o.interest12)},
      {k:'Tilgung 12M',v:eur(o.redemption12)}],
      {k:'Cashflow 12M',v:sgn(o.cashflow12)}));
    hitr.addEventListener('mouseleave',hideTip); svg.appendChild(hitr);
  });
  legend('lg5',[['Eigenkapital',css('--s3')],['Restschuld',css('--debt')]]);
}


/* ================= 6. Liquiditätsvorschau ================= */
function liqchart(id, keyA, keyB, farbe){
  const svg=document.getElementById(id); const W=520,H=240;
  const f=frame(svg,W,H,[26,66,26,8]);
  const R=DATA.vorschau.reihe;
  const alle=R.flatMap(r=>[r[keyA],r[keyB]]).concat([0]);
  const spanne=Math.max(...alle)-Math.min(...alle);
  const hi=Math.max(...alle)+spanne*0.12, lo=Math.min(...alle)-spanne*0.12;
  const x=i=>f.l+(f.iw*i)/(R.length-1);
  const y=v=>f.b-((v-lo)/(hi-lo))*f.ih;
  const g=el('g',{class:'grid'});
  for(const t of ticks(lo,hi,4)){
    g.appendChild(el('line',{x1:f.l,x2:f.r,y1:y(t),y2:y(t)}));
    const tx=el('text',{x:f.r+8,y:y(t)+4,'font-size':'11'});
    tx.setAttribute('fill',css('--text-muted')); tx.textContent=keur(t); g.appendChild(tx);
  }
  svg.appendChild(g);
  const col=css(farbe);
  let d='M'+x(0)+' '+y(R[0][keyA]);
  R.forEach((r,i)=>{d+=' L'+x(i)+' '+y(r[keyA]);});
  for(let i=R.length-1;i>=0;i--) d+=' L'+x(i)+' '+y(R[i][keyB]);
  d+='Z';
  svg.appendChild(el('path',{d,fill:col,'fill-opacity':.15}));
  [[keyA,2.2,1],[keyB,1.6,.55]].forEach(([key,wd,op])=>{
    let l='';R.forEach((r,i)=>{l+=(i?'L':'M')+x(i)+' '+y(r[key]);});
    svg.appendChild(el('path',{d:l,fill:'none',stroke:col,'stroke-width':wd,
      'stroke-opacity':op,'stroke-linejoin':'round','stroke-linecap':'round'}));
  });
  if(lo<0&&hi>0) svg.appendChild(el('line',{x1:f.l,x2:f.r,y1:y(0),y2:y(0),class:'zero'}));
  const iS=R.findIndex(r=>r.quelle!=='geplant');
  if(iS>0){
    const xs=(x(iS-1)+x(iS))/2;
    svg.appendChild(el('line',{x1:xs,x2:xs,y1:f.t,y2:f.b,stroke:css('--line-strong')}));
    const t1=el('text',{x:xs-6,y:f.t-8,'text-anchor':'end','font-size':'10.5'});
    t1.setAttribute('fill',css('--text-muted')); t1.textContent='geplant'; svg.appendChild(t1);
    const t2=el('text',{x:xs+6,y:f.t-8,'font-size':'10.5'});
    t2.setAttribute('fill',css('--text-muted')); t2.textContent='fortgeschrieben'; svg.appendChild(t2);
  }
  R.forEach((r,i)=>{
    if(i%3) return;
    const t=el('text',{x:x(i),y:f.b+18,'text-anchor':'middle','font-size':'11'});
    t.setAttribute('fill',css('--text-muted')); t.textContent=mlab(r.month); svg.appendChild(t);
  });
  const L=R.length-1;
  svg.appendChild(el('circle',{cx:x(L),cy:y(R[L][keyA]),r:4,fill:col,
    stroke:css('--surface-1'),'stroke-width':2}));
  const lb=el('text',{x:x(L)-8,y:y(R[L][keyA])-11,'text-anchor':'end','font-size':'12','font-weight':'600'});
  lb.setAttribute('fill',css('--text-primary')); lb.textContent=keur(R[L][keyA]); svg.appendChild(lb);
  const cross=el('line',{y1:f.t,y2:f.b,stroke:css('--line-strong'),opacity:0}); svg.appendChild(cross);
  const hit=el('rect',{x:f.l,y:f.t,width:f.iw,height:f.ih,fill:'transparent'}); svg.appendChild(hit);
  hit.addEventListener('mousemove',e=>{
    const bb=svg.getBoundingClientRect(); const px=(e.clientX-bb.left)/bb.width*W;
    const i=Math.max(0,Math.min(R.length-1,Math.round((px-f.l)/f.iw*(R.length-1))));
    const r=R[i];
    cross.setAttribute('x1',x(i)); cross.setAttribute('x2',x(i)); cross.setAttribute('opacity',1);
    showTip(e,mlab(r.month).replace(' ',' 20')+' · '+r.quelle,[
      {k:'Basisfall',v:eur(r[keyA]),c:col},
      {k:'Konservativ',v:eur(r[keyB])}]);
  });
  hit.addEventListener('mouseleave',()=>{hideTip();cross.setAttribute('opacity',0);});
}
function chart6(){
  liqchart('c6','frei','frei_k','--s3');
  liqchart('c6b','objektkonten','objektkonten_k','--s1');
  legend('lg6',[],[['Basisfall: geplante Buchungen und Daueraufträge',css('--text-secondary')],
    ['Konservativ: Sonderausgaben laufen im gleichen Tempo weiter',css('--line-strong')]]);
  const R=DATA.vorschau.reihe;
  table('t6',['Monat','Quelle','Frei verfügbar','konservativ','Objektkonten','konservativ','P2P','Gesamt konservativ'],
    R.map(r=>[r.month,r.quelle,eur(r.frei),eur(r.frei_k),eur(r.objektkonten),
      eur(r.objektkonten_k),eur(r.p2p),eur(r.gesamt_k)]));
}

/* ================= 7. Stresstest ================= */
function chart7(){
  const svg=document.getElementById('c7'); const W=1120,H=280;
  const f=frame(svg,W,H,[10,96,54,8]);
  const S=DATA.stress.szenarien;
  const hi=Math.max(...S.map(s=>s.net))*1.06, lo=0;
  const bw=Math.min(58,(f.iw/S.length)*0.56);
  const x=i=>f.l+(f.iw/S.length)*(i+0.5);
  const y=v=>f.b-((v-lo)/(hi-lo))*f.ih;
  const g=el('g',{class:'grid'});
  for(const t of ticks(lo,hi,4)){
    g.appendChild(el('line',{x1:f.l,x2:f.r,y1:y(t),y2:y(t)}));
    const tx=el('text',{x:f.r+8,y:y(t)+4,'font-size':'11'});
    tx.setAttribute('fill',css('--text-muted')); tx.textContent=keur(t); g.appendChild(tx);
  }
  svg.appendChild(g);
  S.forEach((s,i)=>{
    const basis=s.key==='basis';
    const col=basis?css('--s1'):(s.key==='kombi'?css('--critical'):css('--debt'));
    svg.appendChild(el('rect',{x:x(i)-bw/2,y:y(s.net),width:bw,
      height:Math.max(0,f.b-y(s.net)),rx:4,fill:col}));
    const val=el('text',{x:x(i),y:y(s.net)-8,'text-anchor':'middle','font-size':'12','font-weight':'600'});
    val.setAttribute('fill',css('--text-primary')); val.textContent=keur(s.net); svg.appendChild(val);
    const words=s.label.split(' '); const lines=[];
    let cur='';
    words.forEach(w=>{ if((cur+' '+w).trim().length>14){lines.push(cur.trim());cur=w;} else cur+=' '+w; });
    lines.push(cur.trim());
    lines.forEach((ln,j)=>{
      const t=el('text',{x:x(i),y:f.b+18+j*13,'text-anchor':'middle','font-size':'11'});
      t.setAttribute('fill',css(basis?'--text-primary':'--text-secondary')); t.textContent=ln;
      svg.appendChild(t);
    });
    const hitr=el('rect',{x:x(i)-(f.iw/S.length)/2,y:f.t,width:f.iw/S.length,height:f.ih,fill:'transparent'});
    hitr.addEventListener('mousemove',e=>showTip(e,s.label,[
      {k:'Nettovermögen',v:eur(s.net)},
      {k:'Veränderung',v:(s.d_net==null||Math.abs(s.d_net)<1)?'—':sgn(s.d_net)},
      {k:'Eigenkapitalquote',v:pct(s.ek_quote)},
      {k:'Beleihung Kapitalanlagen',v:pct(s.inv_ltv)},
      {k:'Cashflow Kapitalanlagen',v:sgn(s.cashflow)}]));
    hitr.addEventListener('mouseleave',hideTip); svg.appendChild(hitr);
  });
  legend('lg7',[['Ausgangslage',css('--s1')],['Einzelszenario',css('--debt')],
    ['Alles zusammen',css('--critical')]]);
}

/* ---------- Bausteine ---------- */
function legend(id,items,lines){
  const n=document.getElementById(id); n.innerHTML='';
  for(const [l,c] of items) n.insertAdjacentHTML('beforeend',
    '<i><b style="background:'+c+'"></b>'+l+'</i>');
  for(const [l,c] of (lines||[])) n.insertAdjacentHTML('beforeend',
    '<i><b class="ln" style="background:'+c+'"></b>'+l+'</i>');
}
function table(id,head,rows,foot){
  let h='<table><thead><tr>'+head.map(x=>'<th>'+x+'</th>').join('')+'</tr></thead><tbody>';
  for(const r of rows) h+='<tr>'+r.map((c,i)=>'<td'+(i===0?' class="name"':'')+'>'+c+'</td>').join('')+'</tr>';
  h+='</tbody>'+(foot?'<tfoot><tr>'+foot.map(x=>'<td>'+x+'</td>').join('')+'</tr></tfoot>':'')+'</table>';
  document.getElementById(id).innerHTML=h;
}
const cls=v=>v>=0?'up':'down';
const sg=v=>'<span class="'+cls(v)+'">'+sgn(v)+'</span>';

/* ---------- Kopf ---------- */
function head(){
  const k=DATA.kpi, d=new Date(DATA.asof);
  document.getElementById('stichtag').textContent=
    d.toLocaleDateString('de-DE',{day:'numeric',month:'long',year:'numeric'});
  document.getElementById('heroNet').textContent=eur(k.net);
  const set=(id,v,l)=>{const n=document.getElementById(id);
    n.textContent=sgn(v); n.className=cls(v); if(l)document.getElementById(l).textContent=
      'im '+MN[+k.month.slice(5,7)-1]+' '+k.month.slice(0,4);};
  set('dMon',k.delta_m,'dMonL');
  set('dYtd',k.delta_ytd); set('d12',k.delta12);
  const T=[
    ['Vermögen gesamt',eur(k.assets),'Immobilien, Depots, Konten'],
    ['Verbindlichkeiten',eur(k.debt),(()=>{const o=k.n_inv+k.n_eig, n=(DATA.darlehen||[]).length;
      return o+(o===1?' Objekt, ':' Objekte, ')+n+' Darlehen';})()],
    ['Eigenkapitalquote',pct(k.eigenkapitalquote),'Netto zu Gesamtvermögen'],
    ['Kapitalvermögen liquide',eur(k.liquid),'Depots, P2P, freie Konten'],
    ['Kapitalanlage-Immobilien',eur(k.inv_val),k.n_inv+' vermietete Objekte · '+pct(k.inv_ltv,0)+' beliehen'],
    ['Eigenheim',eur(k.eig_val),'selbstgenutzt · '+pct(k.eig_ltv,0)+' beliehen'],
    ['Bruttomietrendite',pct(k.mietrendite,2),'nur Kapitalanlagen · netto '+pct(k.nettomietrendite,2)],
    ['Eigenkapitalrendite Immobilien',pct(k.eigenkapitalrendite,1),'nach Zinsen, vor Steuern und Wertsteigerung'],
    ['Wertpapierrendite p.a.',pct(DATA.kpi.twr_pa||0),
      (DATA.benchmarks&&DATA.benchmarks[0])
        ? 'MSCI World '+pct(DATA.benchmarks[0].pa)+' · Vorsprung '+pct(DATA.benchmarks[0].differenz_pa)
        : 'zeitgewichtet seit 2019'],
    ['Frei verfügbare Liquidität',eur(k.free_cash),'zusätzlich '+eur(k.immo_cash)+' auf Objektkonten'],
  ];
  document.getElementById('tiles').innerHTML=T.map(([l,v,m])=>
    '<div class="tile"><span class="l">'+l+'</span><div class="v">'+v+'</div><div class="m">'+m+'</div></div>').join('');
}

function herkunft(){
  const H=DATA.herkunft, tot=DATA.kpi.net;
  document.getElementById('herkunft').innerHTML=H.map(([l,v])=>
    '<div class="tile"><span class="l">'+l+'</span><div class="v '+cls(v)+'">'+sgn(v)+
    '</div><div class="m">'+cv(v/tot*100,0)+' % des Nettovermögens</div></div>').join('')+
    '<div class="tile" style="background:var(--surface-2)"><span class="l">Nettovermögen heute</span>'+
    '<div class="v">'+eur(tot)+'</div><div class="m">Summe der Bausteine links</div></div>';
}
/* ---------- Bilanz ---------- */
function bilanz(){
  const k=DATA.kpi, m=DATA.months[DATA.months.length-1];
  const A=[
    ['Immobilien, vermietet',k.inv_val,k.n_inv+' Objekte zum Verkehrswert'],
    ['Immobilie, selbstgenutzt',k.eig_val,'Eigenheim zum Verkehrswert'],
    ['Wertpapierdepots',k.wp_total,'Aktien, ETF, Krypto, Crowd, Riester'],
    ['P2P-Anlagen',m.P2P,'Bondora, Mintos, ViaInvest, Twino'],
    ['Guthaben auf Objektkonten',k.immo_konten,'Mieteingänge, Rücklagen, Baukonto'],
    ['Frei verfügbare Bankguthaben',k.free_cash,'Giro- und Verrechnungskonten'],
  ].filter(r=>Math.abs(r[1])>0.5);
  const sumA=A.reduce((s,r)=>s+r[1],0);
  const L=DATA.accounts.filter(a=>a.group==='Darlehen').sort((a,b)=>a.balance-b.balance);
  const sumL=L.reduce((s,a)=>s-a.balance,0);
  table('taktiva',['Position','Betrag','Anteil'],
    A.map(([l,v,note])=>['<div>'+l+'</div><div style="font-size:11.5px;color:var(--text-muted)">'+note+'</div>',
      eur(v),pct(v/sumA*100)]),
    ['Summe Aktiva',eur(sumA),pct(100)]);
  table('tpassiva',['Darlehen','Restschuld','Anteil'],
    L.map(a=>[a.name,eur(-a.balance),pct(-a.balance/sumL*100)]),
    ['Summe Passiva',eur(sumL),pct(100)]);
  document.getElementById('netcard').innerHTML=
    '<div><span class="l">Aktiva</span><span class="s">'+eur(sumA)+'</span></div>'+
    '<div style="color:var(--text-muted);font-size:20px">−</div>'+
    '<div><span class="l">Passiva</span><span class="s">'+eur(sumL)+'</span></div>'+
    '<div style="color:var(--text-muted);font-size:20px">=</div>'+
    '<div><span class="l">Nettovermögen</span><span class="v">'+eur(sumA-sumL)+'</span></div>'+
    '<div><span class="l">Eigenkapitalquote</span><span class="s">'+pct(k.eigenkapitalquote)+'</span></div>';
}

function immokpi(){
  const k=DATA.kpi;
  const T=[
    ['Kapitalanlagen',eur(k.inv_val),k.n_inv+' Objekte · '+eur(k.inv_debt)+' Restschuld'],
    ['Bruttomietrendite',pct(k.mietrendite,2),'Kaltmiete '+eur(k.inv_rent)+' im Jahr'],
    ['Nettomietrendite',pct(k.nettomietrendite,2),'nach Nebenkosten und Bewirtschaftung'],
    ['Sollzins im Schnitt',pct(k.inv_zinssatz,2),'Abstand zur Nettorendite '+pct(k.nettomietrendite-k.inv_zinssatz,2)],
    ['Cashflow nach Kapitaldienst',eur(k.inv_cf),'Annuität '+eur(k.inv_ann)+' im Jahr'],
    ['Eigenheim',eur(k.eig_val),'Wohnkosten '+eur((k.eig_annuitaet12+k.eig_cost)/12)+' im Monat'],
    ['Eigenkapital heute',eur(k.inv_equity),'eingesetzt waren '+eur(k.inv_ek0)],
    ['Rendite auf heutiges Eigenkapital',pct(k.eigenkapitalrendite,1),'nur laufender Überschuss, ohne Wertsteigerung'],
    ['Rendite auf eingesetztes Kapital',k.eigenkapitalrendite_einsatz==null?'—':pct(k.eigenkapitalrendite_einsatz,1),'laufender Überschuss auf den Eigenkapitaleinsatz'],
    ['Gesamtrendite seit Kauf',k.irr_immobilien==null?'—':pct(k.irr_immobilien,1),'geldgewichtet p.a., inklusive Wertsteigerung und Tilgung'],
  ];
  document.getElementById('immokpi').innerHTML=T.map(([l,v,m])=>
    '<div class="tile"><span class="l">'+l+'</span><div class="v">'+v+'</div><div class="m">'+m+'</div></div>').join('');
}
function liqkpi(){
  const v=DATA.vorschau, k=DATA.kpi;
  const T=[
    ['Frei verfügbar heute',eur(v.frei_start),'Giro- und Verrechnungskonten'],
    ['In zwölf Monaten',eur(v.frei_ende),'Basisfall, nur wiederkehrende Vorgänge'],
    ['Konservativ gerechnet',eur(v.frei_ende_k),'wenn die Sonderausgaben so weitergehen'],
    ['Guthaben Objektkonten',eur(v.objekt_ende),'heute '+eur(v.objekt_start)],
    ['Einmalzahlungen '+v.basis_monate+' Monate',eur(v.einmalig_abfluss),
      'tatsächlich abgeflossen, nicht fortgeschrieben'],
    ['Geplante Buchungen',cv(v.n_geplant),'in Portfolio Performance bis '+v.planende],
    ['Konten unter null',cv(v.warnungen.length),v.warnungen.length?'siehe Tabelle unten':'keine'],
  ];
  document.getElementById('liqkpi').innerHTML=T.map(([l,val,m])=>
    '<div class="tile"><span class="l">'+l+'</span><div class="v">'+val+'</div><div class="m">'+m+'</div></div>').join('');
  const W=v.warnungen;
  table('twarn',['Konto','Kategorie','Saldo heute','Tiefstand','erreicht'],
    W.length?W.map(w=>[w.konto,w.gruppe,eur(w.heute),
      '<span class="down">'+eur(w.tiefstand)+'</span>',w.monat])
     :[['Kein Konto läuft im Betrachtungszeitraum ins Minus.','','','','']]);
}

function stresstab(){
  const S=DATA.stress.szenarien, P=DATA.stress.puffer;
  table('tstress',['Szenario','Nettovermögen','Veränderung','Eigenkapitalquote',
    'Beleihung Kapitalanlagen','Zinsaufwand','Cashflow Kapitalanlagen'],
    S.map(s=>[s.label+'<div style="font-size:11.5px;color:var(--text-muted)">'+s.beschreibung+'</div>',
      eur(s.net), (s.d_net==null||Math.abs(s.d_net)<1)?'—':sg(s.d_net), pct(s.ek_quote), pct(s.inv_ltv),
      eur(s.zins), sg(s.cashflow)]));
  table('tpuffer',['Wie viel Wertverlust trägt die Bilanz','Verlust','Anteil am Vermögen'],
    [['bis die Eigenkapitalquote auf 30 % fällt',eur(P['30'].verlust),pct(P['30'].anteil)],
     ['bis die Eigenkapitalquote auf 20 % fällt',eur(P['20'].verlust),pct(P['20'].anteil)],
     ['bis das Eigenkapital aufgebraucht ist',eur(P['0'].verlust),pct(P['0'].anteil)]]);
}

function steuerkpi(){
  const st=DATA.steuer, k=DATA.kpi;
  const T=[
    ['Grenzsteuersatz',pct(st.satz,2),(st.jahr?'Erklärung '+st.jahr+' · ':'')+'Durchschnitt '+pct(st.durchschnitt,1)],
    ['Steuerliches Ergebnis',eur(st.ergebnis),'Kapitalanlagen, letzte zwölf Monate'],
    ['Steuerlast darauf',eur(st.steuer),st.ergebnis<0?'Entlastung':'zu zahlen'],
    ['Cashflow nach Steuern',eur(st.cashflow_nach_steuern),'vor Steuern '+eur(st.cashflow)],
    ['Steuerwirkung der AfA',eur(st.afa_wirkung),eur(st.afa)+' Abschreibung ohne Zahlung'],
    ['Eigenkapitalrendite nach Steuern',pct(st.rendite_nach_steuern,1),'vor Steuern '+pct(k.eigenkapitalrendite,1)],
  ];
  document.getElementById('steuerkpi').innerHTML=T.map(([l,v,m])=>
    '<div class="tile"><span class="l">'+l+'</span><div class="v">'+v+'</div><div class="m">'+m+'</div></div>').join('');

  const Z=st.zeilen, inv=Z.filter(z=>!z.selbstgenutzt), eig=Z.filter(z=>z.selbstgenutzt);
  const sum=(L,key)=>L.reduce((s,z)=>s+z[key],0);
  const row=z=>[z.no+' · '+z.name+(z.selbstgenutzt?' <span class="chip">Eigennutzung</span>':''),
    (z.selbstgenutzt||!z.afa_satz)?'—':pct(z.afa_satz,2), eur(z.einnahmen), eur(z.bewirtschaftung), eur(z.zinsen),
    eur(z.afa), sg(z.ergebnis), sg(-z.steuer), sg(z.cashflow), sg(z.cashflow_nach_steuern)];
  table('tsteuer',['Objekt','AfA-Satz','Einnahmen','Bewirtschaftung','Schuldzinsen','AfA',
    'Steuerliches Ergebnis','Steuerwirkung','Cashflow','Cashflow nach Steuern'],
    inv.map(row).concat([['<b>Kapitalanlagen</b>','',
      '<b>'+eur(sum(inv,'einnahmen'))+'</b>','<b>'+eur(sum(inv,'bewirtschaftung'))+'</b>',
      '<b>'+eur(sum(inv,'zinsen'))+'</b>','<b>'+eur(sum(inv,'afa'))+'</b>',
      '<b>'+sg(sum(inv,'ergebnis'))+'</b>','<b>'+sg(-sum(inv,'steuer'))+'</b>',
      '<b>'+sg(sum(inv,'cashflow'))+'</b>','<b>'+sg(sum(inv,'cashflow_nach_steuern'))+'</b>']])
      .concat(eig.map(row)));

  table('tueberleit',['Vom Cashflow zum steuerlichen Ergebnis','Betrag'],
    [['Cashflow der Kapitalanlagen nach Kapitaldienst',eur(st.cashflow)],
     ['zurück: Tilgung (kein Aufwand)',sg(k.inv_red)],
     ['ab: Abschreibung (Aufwand ohne Zahlung)',sg(-st.afa)],
     ['<b>Steuerliches Ergebnis</b>','<b>'+sg(st.ergebnis)+'</b>'],
     ['Steuer bei '+pct(st.satz,2),sg(-st.steuer)],
     ['<b>Cashflow nach Steuern</b>','<b>'+sg(st.cashflow_nach_steuern)+'</b>']]);

  // Abgleich: die Summenzeile vergleicht nur die Kapitalanlagen, sonst stuenden auf der
  // linken Seite acht und auf der rechten sieben Objekte.
  const erklSpalte='Erklärung'+(st.jahr?' '+st.jahr:'');
  const invE = inv.filter(z=>z.ergebnis_erklaerung!=null);
  const eigE = eig.filter(z=>z.ergebnis_erklaerung!=null);
  const erklInv = invE.reduce((s,z)=>s+z.ergebnis_erklaerung,0);
  table('tabgleich',['Objekt',erklSpalte,'Modell letzte 12 Monate','Differenz'],
    invE.map(z=>[z.no+' · '+z.name, sg(z.ergebnis_erklaerung), sg(z.ergebnis),
                 sg(z.ergebnis-z.ergebnis_erklaerung)])
    .concat([['<b>Summe Kapitalanlagen</b>','<b>'+sg(erklInv)+'</b>',
              '<b>'+sg(st.ergebnis)+'</b>','<b>'+sg(st.ergebnis-erklInv)+'</b>']])
    .concat(eigE.map(z=>[z.no+' · '+z.name+' <span class="chip">Eigennutzung</span>',
                         sg(z.ergebnis_erklaerung),'—','—']))
    .concat([['<b>Gesamt laut Erklärung</b>','<b>'+sg(st.ergebnis_erklaerung_summe)+'</b>','','']]));

  const H=st.historie||[];
  table('tsteuerhist',['Jahr','Stand','Bruttolohn','zu verst. Einkommen',
    'Einkommensteuer','Ergebnis V+V','Erstattung'],
    H.map(h=>[h.jahr, h.status, eur(h.bruttolohn), eur(h.zve), eur(h.est),
              sg(h.vuv), eur(h.erstattung)]));
}

function benchTabelle(){
  const B=DATA.benchmarks||[]; if(!B.length) return;
  table('tbench',['Vergleichsindex','Währung','Zeitraum','Index gesamt','Index p.a.',
    'Eigenes Depot gesamt','Eigenes Depot p.a.','Vorsprung p.a.'],
    B.map(b=>[b.label+(b.warnung?' <span class="chip">nur indikativ</span>':''),
      b.waehrung, 'ab '+mlab(b.von+'-01').replace(' ',' 20')+' · '+cv(b.jahre,1)+' Jahre',
      pct(b.total,1), pct(b.pa,2), pct(b.pf_total,1), pct(b.pf_pa,2),
      '<span class="'+cls(b.differenz_pa)+'">'+pct(b.differenz_pa,2)+'</span>']));
  document.getElementById('bmfn').innerHTML =
    B.map(b=>'<b>'+b.label+'</b> — '+b.kurz+'. '+b.art).join('<br>')
    + '<br>Jeder Index wird nur über den Zeitraum verglichen, für den Kurse vorliegen; '
    + 'die Depotrendite daneben ist für genau denselben Zeitraum gerechnet.';
}

function darlehenTabelle(){
  const D=DATA.darlehen||[]; if(!D.length) return;
  const sum=k=>D.reduce((s,l)=>s+(l[k]||0),0);
  table('tdarlehen',['Darlehen','Nutzung','Restschuld','Zins 12 Monate',
    'Zins Run-Rate','Zinssatz','Tilgung 12 Monate','Tilgungssatz'],
    D.map(l=>[l.label||l.konto,
      l.selbstgenutzt?'<span class="chip">Eigennutzung</span>':'Kapitalanlage',
      eur(l.saldo), eur(l.zins12), eur(l.zins_runrate),
      '<span class="'+(l.zinssatz<2?'pos':'')+'">'+pct(l.zinssatz,2)+'</span>',
      eur(l.tilgung12), pct(l.tilgungssatz,2)]),
    ['Summe','',eur(sum('saldo')),eur(sum('zins12')),eur(sum('zins_runrate')),
     pct(sum('zins_runrate')/sum('saldo')*100,2),eur(sum('tilgung12')),
     pct(sum('tilgung12')/sum('saldo')*100,2)]);
  const tf=D.filter(l=>l.tilgungssatz!=null&&l.tilgungssatz<0);
  if(tf.length) document.getElementById('tdarlehen').insertAdjacentHTML('afterend',
    '<p class="fn">Negative Tilgung bei '+tf.map(l=>l.label||l.konto).join(' und ')+
    ': diese Tranchen wurden im Lauf der letzten zwölf Monate erst valutiert, die gezahlte '+
    'Annuität lag deshalb unter den aufgelaufenen Sollzinsen. Ab dem nächsten vollen Jahr '+
    'greift die reguläre Tilgung.</p>');
}

function zbkpi(){
  const k=DATA.kpi;
  const T=[
    ['Fällig binnen 12 Monaten',eur(k.zb_faellig_12m),'Restschuld, deren Zinsbindung ausläuft'],
    ['Fällig binnen 36 Monaten',eur(k.zb_faellig_36m),'Mehrkosten im Stressfall '+eur(k.zb_mehrkosten_36m_stress)+' pro Jahr'],
    ['Nächste Fälligkeit',k.zb_naechste_konto||'—',k.zb_naechste_datum?('am '+k.zb_naechste_datum.split('-').reverse().join('.')):''],
  ];
  document.getElementById('zbkpi').innerHTML=T.map(([l,v,m])=>
    '<div class="tile"><span class="l">'+l+'</span><div class="v">'+v+'</div><div class="m">'+m+'</div></div>').join('');
}

function faelligkeitTabelle(){
  const F=DATA.faelligkeitsleiste||[]; if(!F.length) return;
  table('tfaelligkeit',['Zinsbindung endet in','Betroffene Darlehen','Restschuld',
    'Anteil Immobiliendarlehen','gewichteter Sollzins','Mehrkosten p.a. bei +2 %-Punkten'],
    F.map(f=>[f.jahr+(f.kfw_hinweis?' <span class="chip">KfW-Sonderfall</span>':''),
      f.konten.map(x=>x.konto.replace('Darlehenskonto ','')).join(', '),
      eur(f.restschuld), pct(f.anteil_gesamt,1),
      f.zins_gewichtet==null?'—':pct(f.zins_gewichtet,2), eur(f.mehrkosten_stress_pa)]),
    ['Summe','',eur(F.reduce((s,f)=>s+f.restschuld,0)),'','',
     eur(F.reduce((s,f)=>s+f.mehrkosten_stress_pa,0))]);
}

function steckbriefTabelle(){
  const O=(DATA.objects||[]).filter(o=>!o.selbstgenutzt).concat((DATA.objects||[]).filter(o=>o.selbstgenutzt));
  if(!O.length) return;
  table('tsteckbrief',['Nr.','Objekt','Lage','Baujahr','Wohnfläche','Miete kalt/m²',
    'Mieter seit','Bodenrichtwert','Sollrücklage/Jahr'],
    O.map(o=>[o.no,o.name,o.lage||'—',o.baujahr||'—',
      o.wohnflaeche_m2?cv(o.wohnflaeche_m2,1)+' m²':'—',
      (o.selbstgenutzt||!o.miete_pro_m2_kalt)?'—':eur(o.miete_pro_m2_kalt,2),
      o.mieter_name||o.mieter_seit||(o.mieter_seit_hinweis?'<span class="chip">offen</span>':'—'),
      o.bodenrichtwert?o.bodenrichtwert+' €/m²':'—',
      o.ruecklage_soll_m2?eur(o.ruecklage_soll_m2):'—']));
  const hinweise=O.filter(o=>o.mieter_seit_hinweis||o.bodenrichtwert_hinweis)
    .map(o=>'Objekt '+o.no+': '+(o.mieter_seit_hinweis||o.bodenrichtwert_hinweis));
  const gemeinsam=O.find(o=>o.verkehrswert_gesamtobjekt_differenz!=null);
  let fn='Sollrücklage: 1,10 €/m² und Monat für Baujahr vor 1948, 0,80 €/m² danach — eine '+
    'Faustregel, kein Gutachten.';
  if(gemeinsam) fn+=' '+(gemeinsam.lage||'Gemeinsam bewertetes Grundstück')+': Verkehrswertgutachten '+eur(gemeinsam.verkehrswert_gesamtobjekt)+
    ' für das Gesamtgrundstück, in dieser Bilanz mit '+eur(gemeinsam.verkehrswert_gesamtobjekt_kurs)+
    ' angesetzt (Differenz '+eur(gemeinsam.verkehrswert_gesamtobjekt_differenz)+').';
  if(hinweise.length) fn+=' '+hinweise.join(' ');
  document.getElementById('steckbrieffn').innerHTML=fn;
}

function tables(){
  const P=DATA.positions;
  const BW=new Set((DATA.bewertungshinweise||[]).map(x=>x.name));
  table('tpos',['Position','Depot','Stück','Kurs','Wert','Einstand','Gewinn/Verlust',''],
    P.map(p=>[p.name+(p.isin?' <span class="chip">'+p.isin+'</span>':'')
      +(BW.has(p.name)?' <span class="chip">Buchwert</span>':''),p.depot,
      cv(p.shares,p.shares<10?4:2),eur(p.price,2),eur(p.value),eur(p.cost),
      sg(p.gain),p.gain_pct==null?'':'<span class="'+cls(p.gain)+'">'+pct(p.gain_pct,0)+'</span>']),
    ['Summe','','','',eur(P.reduce((s,p)=>s+p.value,0)),eur(P.reduce((s,p)=>s+p.cost,0)),
     sg(P.reduce((s,p)=>s+p.gain,0)),'']);
  const dop=Object.entries(P.reduce((m,p)=>{(m[p.name]=m[p.name]||[]).push(p.depot);return m;},{}))
    .filter(([,v])=>v.length>1);
  let hin=[];
  if(dop.length) hin.push('In mehreren Depots geführt: '+dop.map(([n,v])=>n+' ('+v.join(', ')+')').join('; ')
    +'. Für Klumpenrisiko und Top-Liste werden diese Zeilen zusammengefasst.');
  if(BW.size) hin.push('Mit „Buchwert" markierte Positionen haben keinen aktuellen Marktkurs '
    +'und stehen mit dem zuletzt bekannten Wert in der Bilanz — zusammen '
    +eur(DATA.kpi.bewertungshinweis_summe)+'.');
  if(hin.length) document.getElementById('tpos').insertAdjacentHTML('afterend',
    '<p class="fn">'+hin.join('<br>')+'</p>');
  const O=DATA.objects;
  const INV=O.filter(o=>!o.selbstgenutzt), EIG=O.filter(o=>o.selbstgenutzt);
  const sum=(L,k)=>L.reduce((s,o)=>s+o[k],0);
  const row=o=>[o.no+' · '+o.name+(o.selbstgenutzt?' <span class="chip">Eigennutzung</span>':''),
    eur(o.value),eur(o.loan),eur(o.equity),pct(o.ltv),
    o.selbstgenutzt?'—':pct(o.net_yield,2),
    eur(o.rent12),eur(o.cost12),eur(o.interest12),eur(o.redemption12),sg(o.cashflow12)];
  const sub=(L,label)=>['<b>'+label+'</b>','<b>'+eur(sum(L,'value'))+'</b>',
    '<b>'+eur(sum(L,'loan'))+'</b>','<b>'+eur(sum(L,'equity'))+'</b>',
    '<b>'+pct(sum(L,'loan')/sum(L,'value')*100)+'</b>',
    '<b>'+(L===EIG?'—':pct((sum(L,'rent12')+sum(L,'nk12')-sum(L,'cost12'))/sum(L,'value')*100,2))+'</b>',
    '<b>'+eur(sum(L,'rent12'))+'</b>','<b>'+eur(sum(L,'cost12'))+'</b>',
    '<b>'+eur(sum(L,'interest12'))+'</b>','<b>'+eur(sum(L,'redemption12'))+'</b>',
    '<b>'+sg(sum(L,'cashflow12'))+'</b>'];
  table('tobj',['Objekt','Verkehrswert','Restschuld','Eigenkapital','Beleihung','Nettorendite',
    'Kaltmiete 12M','Kosten 12M','Zins 12M','Tilgung 12M','Cashflow 12M'],
    INV.map(row).concat([sub(INV,'Kapitalanlagen')]).concat(EIG.map(row))
       .concat(EIG.length>1?[sub(EIG,'Eigennutzung')]:[]),
    ['Gesamt',eur(sum(O,'value')),eur(sum(O,'loan')),eur(sum(O,'equity')),
      pct(sum(O,'loan')/sum(O,'value')*100),'',eur(sum(O,'rent12')),eur(sum(O,'cost12')),
      eur(sum(O,'interest12')),eur(sum(O,'redemption12')),sg(sum(O,'cashflow12'))]);
  const Y=Object.keys(DATA.years).sort().reverse();
  table('tyear',['Jahr','Nettovermögen','Veränderung','Sparen/Entnahmen','Wertpapiere',
    'Immobilienbewertung','Laufendes Ergebnis','Kaltmiete','Zinsaufwand','Tilgung'],
    Y.map(y=>{const v=DATA.years[y];return [y,eur(v.net_end),sg(v.delta),sg(v.extern),
      sg(v.wp_change),sg(v.immo_change),sg(v.laufend),eur(v.kaltmiete),eur(v.zinsaufwand),
      eur(v.tilgung)];}));
  table('tacc',['Konto','Kategorie','Saldo'],
    DATA.accounts.map(a=>[a.label||a.name,a.group,eur(a.balance,2)]));
  const k=DATA.kpi;
  document.getElementById('foot').innerHTML=
    '<b>Wie gerechnet wird.</b> Alle Kennzahlen sind eigene Berechnungen aus den in Portfolio '+
    'Performance gebuchten Vorgängen. Aus Portfolio Performance übernommen sind nur die Rohdaten: '+
    'Buchungen, Wertpapierkurse und die von dir gepflegten Verkehrswerte. Keine der Renditen unten '+
    'stammt aus der Software.<br><br>'+
    '<b>Bruttomietrendite</b> = Kaltmiete der letzten zwölf Monate geteilt durch den Verkehrswert '+
    'der vermieteten Objekte. Die Kaltmiete ist die Summe der Buchungen, die du als Dividende auf '+
    'das jeweilige Immobilien-Wertpapier gebucht hast: '+eur(k.inv_rent)+' ÷ '+eur(k.inv_val)+
    ' = '+pct(k.mietrendite,2)+'. Das selbstgenutzte Objekt ist in Zähler und Nenner nicht enthalten.<br>'+
    '<b>Nettomietrendite</b> = (Kaltmiete + Nebenkostenvorauszahlungen der Mieter − sämtliche '+
    'Bewirtschaftungskosten) ÷ Verkehrswert = ('+eur(k.inv_rent)+' + '+eur(k.inv_nk)+' − '+
    eur(k.inv_cost)+') ÷ '+eur(k.inv_val)+' = '+pct(k.nettomietrendite,2)+'. Sie ist vor Zinsen, '+
    'vor Tilgung und vor Steuern.<br>'+
    '<b>Eigenkapitalrendite auf heutiges Eigenkapital</b> = Überschuss nach Zinsen ÷ '+
    '(Verkehrswert − Restschuld) = '+eur(k.inv_ueberschuss)+' ÷ '+eur(k.inv_equity)+' = '+
    pct(k.eigenkapitalrendite,1)+'. Der Nenner ist der heutige Marktwert deines Anteils, nicht das, '+
    'was du eingesetzt hast — deshalb fällt die Zahl niedriger aus, als man erwartet. Sie enthält '+
    'außerdem keine Wertsteigerung.<br>'+
    '<b>Rendite auf eingesetztes Kapital</b> = derselbe Überschuss ÷ Eigenkapitaleinsatz beim Kauf '+
    '('+eur(k.inv_ek0)+', also Kaufpreise inklusive Nebenkosten minus ausgezahlte Darlehen) = '+
    pct(k.eigenkapitalrendite_einsatz,1)+'.<br>'+
    '<b>Gesamtrendite seit Kauf</b> = interner Zinsfuß über alle Zahlungen seit dem jeweiligen Kauf: '+
    'Kaufpreise, Darlehensauszahlungen, Mieten, Nebenkosten, Bewirtschaftung, Kapitaldienst — '+
    'zuzüglich des heutigen Eigenkapitals als Endwert. Ergebnis '+pct(k.irr_immobilien,1)+' pro Jahr. '+
    'Diese Zahl hängt unmittelbar an deinen selbst geschätzten Verkehrswerten; sind die zu '+
    'optimistisch, ist es die Rendite auch.<br>'+
    '<b>Kapitaldienst und Tilgung.</b> Die Überweisung auf ein Darlehenskonto ist die volle Annuität. '+
    'Nur der Teil nach Abzug der Sollzinsen senkt die Restschuld — deshalb steht hier '+
    eur(k.tilgung12)+' Tilgung bei '+eur(k.annuitaet12)+' Kapitaldienst.<br>'+
    '<b>Wertpapiere</b> sind zeitgewichtet gerechnet (modifizierte Dietz-Methode je Monat, verkettet) '+
    'und damit unabhängig vom Zeitpunkt der Ein- und Auszahlungen.<br><br>'+
    'Erstellt aus der Portfolio-Performance-Datei, Stichtag '+DATA.asof+'. '+
    'Fremdwährungspositionen zu EZB-Referenzkursen vom '+DATA.fx_date+' umgerechnet. '+
    'Keine Anlage-, Steuer- oder Rechtsberatung.';
}

/* ================= Formatierung nach Kennzahlentyp ================= */
function fmtWert(v,f){
  if(v==null) return '—';
  if(f==='eur') return eur(v);
  if(f==='pct') return pct(v,1);
  if(f==='x')   return cv(v,2)+' ×';
  if(f==='mon') return cv(v,1)+' Monate';
  return cv(v,2);
}
const DELTA_EPS={eur:0.5,pct:0.005,x:0.005,mon:0.05};
function fmtDelta(v,f){
  if(v==null||Math.abs(v)<(DELTA_EPS[f]||0.005)) return '±0';
  const z=v>0?'+':'−', a=Math.abs(v);
  if(f==='eur') return z+eur(a);
  if(f==='pct') return z+cv(a,2)+' pp';
  if(f==='x')   return z+cv(a,2);
  if(f==='mon') return z+cv(a,1);
  return z+cv(a,2);
}

/* ================= Statusleiste ================= */
const STATUS=[
  {key:'net',            label:'Nettovermögen',   format:'eur'},
  {key:'eigenkapitalquote',label:'Eigenkapital',  format:'pct'},
  {key:'dscr',           label:'Kapitaldienstdeckung',format:'x'},
  {key:'free_cash',      label:'Puffer',          format:'eur'},
  {key:'delta_ytd',      label:'seit Jahresbeginn',format:'eur'},
];
function statusbar(){
  const k=DATA.kpi, A=(DATA.bewertung&&DATA.bewertung.ampeln)||[];
  const stufe=key=>{const a=A.find(x=>x.key===key);return a?a.stufe:null;};
  const V=(DATA.vergleich&&DATA.vergleich.werte)||{};
  document.getElementById('statusbar').innerHTML=STATUS.map(x=>{
    const st=stufe(x.key), v=V[x.key];
    const d=(v&&v.delta!=null&&Math.abs(v.delta)>=(DELTA_EPS[x.format]||0.005))
      ? ' <i class="'+cls(v.delta)+'">'+fmtDelta(v.delta,x.format)+'</i>' : '';
    return '<span class="s">'+(st?'<span class="lamp '+st+'"></span>':'')+
      x.label+' <b>'+fmtWert(k[x.key],x.format)+'</b>'+d+'</span>';
  }).join('');
}

/* ================= Rechenweg einer Ampel ================= */
function rechnung(a){
  const R=a.rechnung||[]; if(!R.length) return '';
  const zelle=r=>{
    if(r.format==='text'||r.wert==null) return '';
    if(r.format==='anz') return cv(r.wert);
    return fmtWert(r.wert,r.format);
  };
  const zeilen=R.map(r=>
    '<tr class="'+(r.art||'')+'"><td>'+r.label+'</td><td>'+zelle(r)+'</td></tr>').join('');
  return '<div class="rechnung"><div class="rh">So ist die Zahl gerechnet</div>'+
    '<table>'+zeilen+'</table></div>';
}

/* ================= Ampeln ================= */
function ampeln(){
  const A=(DATA.bewertung&&DATA.bewertung.ampeln)||[];
  const wort={gruen:'im Zielbereich',gelb:'beobachten',rot:'außerhalb des Ziels',
              unbekannt:'nicht berechenbar'};
  document.getElementById('ampeln').innerHTML=A.map(a=>{
    const d=a.delta!=null&&Math.abs(a.delta)>=(DELTA_EPS[a.format]||0.005)
      ? '<span class="dlt '+cls(a.delta)+'">'+fmtDelta(a.delta,a.format)+'</span>'
      : '<span class="dlt"></span>';
    const skala=a.richtung==='hoch'
      ? 'Grün ab '+fmtWert(a.gruen,a.format)+', gelb ab '+fmtWert(a.gelb,a.format)+', darunter rot.'
      : 'Grün bis '+fmtWert(a.gruen,a.format)+', gelb bis '+fmtWert(a.gelb,a.format)+', darüber rot.';
    return '<details class="amp '+a.stufe+'"><summary>'+
      '<span class="lamp '+a.stufe+'"></span>'+
      '<span class="lbl">'+a.label+'</span>'+
      '<span class="val">'+fmtWert(a.wert,a.format)+'</span>'+d+
      '<span class="ziel">Ziel '+a.ziel+' · '+wort[a.stufe]+'</span>'+
      '<span class="caret">›</span></summary>'+
      '<div class="warum">'+a.warum+
      rechnung(a)+
      (a.quelle?'<div class="skala"><b>Woher die Zahlen kommen.</b> '+a.quelle+'</div>':'')+
      '<div class="skala"><b>Der Maßstab.</b> '+skala+'</div></div></details>';
  }).join('');
}

/* ================= Vergleich mit dem Vormonat ================= */
function vergleich(){
  const V=DATA.vergleich;
  const note=document.getElementById('vergleichnote');
  if(!V){note.textContent='Für den Vormonat liegt kein Vergleichslauf vor.';return;}
  note.innerHTML='Dieselbe Auswertung ein zweites Mal gerechnet, zum Stichtag '+
    V.stichtag.split('-').reverse().join('.')+'. Bestandsgrößen wie Vermögen und Restschuld '+
    'ändern sich durch echte Vorgänge. Zwölfmonatsgrößen wie die Kaltmiete ändern sich auch '+
    'dann, wenn nur das Fenster einen Monat weiterrückt — dort steht immer ein Monat neu drin '+
    'und einer fällt hinten heraus.';
  const W=V.werte;
  table('tvergleich',['Kennzahl','Vormonat','Stichtag','Veränderung'],
    Object.keys(W).map(k=>{
      const v=W[k];
      return [v.label, fmtWert(v.vorher,v.format), fmtWert(v.jetzt,v.format),
        '<span class="'+cls(v.delta==null?0:v.delta)+'">'+fmtDelta(v.delta,v.format)+'</span>'];
    }));
}

/* ================= Objekt-Detailsicht ================= */
let OBJ_AKTIV=null;
function objektwahl(){
  const O=DATA.objects;
  document.getElementById('objpick').innerHTML=O.map(o=>
    '<button data-no="'+o.no+'">'+o.no+' · '+o.name+
    '<s>'+keur(o.value)+(o.selbstgenutzt?' · Eigennutzung':' · '+pct(o.gross_yield,2))+'</s></button>'
  ).join('');
  document.querySelectorAll('#objpick button').forEach(b=>
    b.addEventListener('click',()=>objektzeigen(+b.dataset.no)));
  objektzeigen(O[0].no);
}
function objektzeigen(no){
  OBJ_AKTIV=no;
  const o=DATA.objects.find(x=>x.no===no); if(!o) return;
  document.querySelectorAll('#objpick button').forEach(b=>
    b.setAttribute('aria-pressed', (+b.dataset.no===no)?'true':'false'));
  const st=(DATA.steuer.zeilen||[]).find(z=>z.no===no)||{};
  const dl=(DATA.darlehen||[]).filter(l=>l.objekt===no);
  const row=(k,v)=>'<dt>'+k+'</dt><dd>'+v+'</dd>';
  const sep='<div class="sep"></div>';
  const kauf=o.kaufdatum?o.kaufdatum.split('-').reverse().join('.'):'—';
  const halte=o.haltedauer?cv(o.haltedauer,1)+' Jahre':'—';

  const links='<div class="card"><div class="bh">Objekt '+o.no+' · '+o.name+
    (o.selbstgenutzt?' <span class="chip">Eigennutzung</span>':'')+'</div><dl class="kv">'+
    row('Gekauft am',kauf+' · seit '+halte)+
    row('Kaufpreis mit Nebenkosten',eur(o.kaufpreis))+
    row('Verkehrswert heute',eur(o.value))+
    row('Wertveränderung','<span class="'+cls(o.wertaenderung)+'">'+sgn(o.wertaenderung)+' · '+
      pct(o.kaufpreis?o.wertaenderung/o.kaufpreis*100:0,1)+'</span>')+
    row('Modernisierung bisher',eur(o.capex_total))+
    sep+
    row('Restschuld',eur(o.loan))+
    row('Eigenkapital im Objekt',eur(o.equity))+
    row('Beleihung',pct(o.ltv,1))+
    row('Guthaben auf dem Objektkonto',eur(o.opaccount))+
    sep+
    row('Kaltmiete 12 Monate',o.selbstgenutzt?'—':eur(o.rent12))+
    row('Umgelegte Nebenkosten',eur(o.nk12))+
    row('Bewirtschaftung',eur(o.cost12))+
    row('Ergebnis vor Finanzierung',eur(o.noi12))+
    row('Zins 12 Monate',eur(o.interest12))+
    row('Zins hochgerechnet auf heute',eur(o.interest_runrate))+
    row('Tilgung 12 Monate',eur(o.redemption12))+
    row('Cashflow nach Kapitaldienst','<span class="'+cls(o.cashflow12)+'">'+sgn(o.cashflow12)+'</span>')+
    '</dl></div>';

  const irrtext=o.irr!=null
    ? '<dl class="kv">'+row('Rendite seit Kauf (IRR)','<b>'+pct(o.irr,2)+'</b>')+'</dl>'+
      '<p class="fn">Interner Zinsfuß auf alle tatsächlichen Zahlungen dieses Objekts: '+
      'Kaufpreis und Nebenkosten, Darlehensauszahlungen, Annuitäten, Mieten, Nebenkosten '+
      'und Bewirtschaftung, zuzüglich des heutigen Eigenkapitals als Endwert.</p>'
    : '<p class="fn">'+(o.irr_hinweis||'Keine Rendite berechenbar.')+'</p>';

  const rechts='<div>'+
    '<div class="card"><div class="bh">Rendite</div>'+
    '<dl class="kv">'+
      row('Bruttomietrendite',o.selbstgenutzt?'—':pct(o.gross_yield,2))+
      row('Nettomietrendite',o.selbstgenutzt?'—':pct(o.net_yield,2))+
      row('Sollzins',pct(o.zinssatz,2))+
      row('Tilgungssatz',pct(o.tilgungssatz,2))+
    '</dl>'+irrtext+'</div>'+
    '<div class="card" style="margin-top:16px"><div class="bh">Steuerlich</div><dl class="kv">'+
      row('AfA-Satz',o.selbstgenutzt?'—':pct(st.afa_satz||0,2))+
      row('Abschreibung im Jahr',o.selbstgenutzt
          ? '<span style="color:var(--text-muted)">nicht abziehbar</span>'
          : eur(st.afa||0))+
      row('Werbungskosten',o.selbstgenutzt?'—':eur(st.werbungskosten||0))+
      row('Steuerliches Ergebnis (Modell)',o.selbstgenutzt?'—':
          '<span class="'+cls(st.ergebnis||0)+'">'+sgn(st.ergebnis||0)+'</span>')+
      row('Ergebnis laut Erklärung'+(DATA.steuer.jahr?' '+DATA.steuer.jahr:''), st.ergebnis_erklaerung!=null
          ? '<span class="'+cls(st.ergebnis_erklaerung)+'">'+sgn(st.ergebnis_erklaerung)+'</span>':'—')+
      row('Eigentum',st.eigentum||'—')+
    '</dl></div>'+
    '<div class="card" style="margin-top:16px"><div class="bh">Finanzierung</div>'+
    (dl.length?'<dl class="kv">'+dl.map(l=>
        row(l.konto+' <span class="chip">'+pct(l.zinssatz,2)+'</span>',eur(l.saldo))).join('')+
      '</dl>':'<p class="fn">Kein Darlehen auf diesem Objekt.</p>')+
    '</div></div>';

  document.getElementById('objdetail').innerHTML=
    '<div class="od">'+links+rechts+'</div>'+
    '<div class="card" style="margin-top:16px"><div class="bh">Wert und Restschuld im Verlauf</div>'+
    '<figure><svg id="cobj" height="220" role="img" aria-label="Verlauf des Objekts"></svg></figure>'+
    '<div class="legend" id="lgobj"></div></div>';
  chartObj(o);
}
function chartObj(o){
  const svg=document.getElementById('cobj'); if(!svg) return;
  const V=o.verlauf||[]; const W=1120,H=220; const f=frame(svg,W,H,[12,64,24,8]);
  if(V.length<2) return;
  const hi=Math.max(...V.map(x=>x.wert))*1.08, lo=0;
  const x=i=>f.l+(f.iw*i)/(V.length-1);
  const y=v=>f.b-((v-lo)/(hi-lo))*f.ih;
  const g=el('g',{class:'grid'});
  for(const t of ticks(lo,hi,4)){
    g.appendChild(el('line',{x1:f.l,x2:f.r,y1:y(t),y2:y(t)}));
    const tx=el('text',{x:f.r+8,y:y(t)+4,'font-size':'11'});
    tx.setAttribute('fill',css('--text-muted')); tx.textContent=keur(t); g.appendChild(tx);
  }
  svg.appendChild(g);
  const flaeche=(vals,col,op)=>{
    let a=''; vals.forEach((v,i)=>{a+=(i?'L':'M')+x(i)+' '+y(v);});
    a+='L'+x(vals.length-1)+' '+y(0)+'L'+x(0)+' '+y(0)+'Z';
    svg.appendChild(el('path',{d:a,fill:col,'fill-opacity':op}));
  };
  const linie=(vals,col,w)=>{
    let d=''; vals.forEach((v,i)=>{d+=(i?'L':'M')+x(i)+' '+y(v);});
    svg.appendChild(el('path',{d,fill:'none',stroke:col,'stroke-width':w,
      'stroke-linejoin':'round','stroke-linecap':'round'}));
  };
  // Gefuellt wird das Eigenkapital — der Abstand zwischen Verkehrswert und Restschuld.
  let band='';
  V.forEach((v,i)=>{band+=(i?'L':'M')+x(i)+' '+y(v.wert);});
  for(let i=V.length-1;i>=0;i--){band+='L'+x(i)+' '+y(V[i].darlehen);}
  band+='Z';
  svg.appendChild(el('path',{d:band,fill:css('--s1'),'fill-opacity':.16}));
  flaeche(V.map(v=>v.darlehen),css('--debt'),.20);
  linie(V.map(v=>v.wert),css('--s1'),2.2);
  linie(V.map(v=>v.darlehen),css('--debt'),2);
  V.forEach((v,i)=>{
    if(v.month.slice(5)!=='01') return;
    const t=el('text',{x:x(i),y:f.b+17,'text-anchor':'middle','font-size':'11'});
    t.setAttribute('fill',css('--text-muted')); t.textContent=v.month.slice(0,4); svg.appendChild(t);
  });
  const cross=el('line',{y1:f.t,y2:f.b,stroke:css('--line-strong'),opacity:0}); svg.appendChild(cross);
  const hit=el('rect',{x:f.l,y:f.t,width:f.iw,height:f.ih,fill:'transparent'}); svg.appendChild(hit);
  hit.addEventListener('mousemove',e=>{
    const bb=svg.getBoundingClientRect(); const px=(e.clientX-bb.left)/bb.width*W;
    const i=Math.max(0,Math.min(V.length-1,Math.round((px-f.l)/f.iw*(V.length-1))));
    cross.setAttribute('x1',x(i)); cross.setAttribute('x2',x(i)); cross.setAttribute('opacity',1);
    showTip(e,mlab(V[i].month).replace(' ',' 20'),
      [{k:'Verkehrswert',v:eur(V[i].wert),c:css('--s1')},
       {k:'Restschuld',v:eur(V[i].darlehen),c:css('--debt')}],
      {k:'Eigenkapital',v:eur(V[i].wert-V[i].darlehen)});
  });
  hit.addEventListener('mouseleave',()=>{hideTip();cross.setAttribute('opacity',0);});
  legend('lgobj',[['Eigenkapital',css('--s1')]],[['Verkehrswert',css('--s1')],['Restschuld',css('--debt')]]);
}

/* ================= Wegweiser und Glossar ================= */
const REITERNAME={ueberblick:'Überblick',immobilien:'Immobilien',depot:'Kapitalanlagen',
  risiko:'Liquidität und Risiko',steuern:'Steuern',empfehlungen:'Empfehlungen'};
function wegweiser(){
  const L=DATA.lesepfade||[];
  document.getElementById('lesepfade').innerHTML=L.map(p=>{
    const links=(p.reiter||[]).map(r=>
      '<a href="#'+r+'" data-goto="'+r+'">'+REITERNAME[r]+'</a>').join(' · ');
    return '<div class="tile"><span class="l">'+p.titel+'</span>'+
      '<div class="m" style="font-size:13px;color:var(--text-secondary);margin-top:2px">'+
      p.text+'</div>'+(links?'<div class="m" style="margin-top:8px">'+links+'</div>':'')+'</div>';
  }).join('');
  document.querySelectorAll('#lesepfade a[data-goto]').forEach(a=>
    a.addEventListener('click',e=>{e.preventDefault();zeige(a.dataset.goto);}));
  document.getElementById('glossarliste').innerHTML=(DATA.glossar||[])
    .map(([t,d])=>'<dt>'+t+'</dt><dd>'+d+'</dd>').join('');
}

/* ================= Reiter ================= */
const VIEWS=['ueberblick','immobilien','depot','risiko','steuern','empfehlungen'];
function zeige(name){
  if(!VIEWS.includes(name)) name=VIEWS[0];
  VIEWS.forEach(v=>{
    const n=document.getElementById('v-'+v);
    if(n) n.hidden=(v!==name);
  });
  document.querySelectorAll('#tabs button').forEach(b=>
    b.setAttribute('aria-selected', b.dataset.view===name?'true':'false'));
  if(location.hash.slice(1)!==name) history.replaceState(null,'','#'+name);
  draw();
  if(name==='immobilien'&&OBJ_AKTIV!=null) objektzeigen(OBJ_AKTIV);
}
function reiter(){
  document.querySelectorAll('#tabs button').forEach(b=>
    b.addEventListener('click',()=>{zeige(b.dataset.view);scrollTo({top:0,behavior:'smooth'});}));
  addEventListener('hashchange',()=>zeige(location.hash.slice(1)));
  zeige(location.hash.slice(1)||'ueberblick');
}

function draw(){chart1();chart2();chart3();chart4();chart5();chart6();chart7();}
head();statusbar();ampeln();vergleich();bilanz();tables();herkunft();immokpi();liqkpi();
stresstab();steuerkpi();benchTabelle();darlehenTabelle();objektwahl();wegweiser();reiter();
zbkpi();faelligkeitTabelle();steckbriefTabelle();
const btn=document.getElementById('theme');
function sync(){const dark=document.documentElement.getAttribute('data-theme')==='dark';
  btn.textContent=dark?'Hell':'Dunkel';}
btn.addEventListener('click',()=>{
  const dark=document.documentElement.getAttribute('data-theme')==='dark';
  document.documentElement.setAttribute('data-theme',dark?'light':'dark');
  sync();draw();});
if(matchMedia('(prefers-color-scheme:dark)').matches)
  document.documentElement.setAttribute('data-theme','dark');
sync();draw();
if(OBJ_AKTIV!=null) objektzeigen(OBJ_AKTIV);
let rt;addEventListener('resize',()=>{clearTimeout(rt);rt=setTimeout(draw,180);});
