(function(){
  'use strict';

  function isMobile(){ return window.matchMedia('(max-width:860px)').matches; }
  function trunc(s,n){ s=(s||'').trim(); return s.length>n ? s.slice(0,n-1).trim()+'…' : s; }

  /* ── Árbol completo de navegación (una sola fuente) ───── */
  var TREE = [
    { g:'Disposiciones Generales', items:[
      ['Disposiciones Generales del SEN','disposiciones_sen.html'],
      ['Disposiciones y Glosario','disposiciones.html']
    ]},
    { g:'Manual INTE — Centrales', code:'inte', items:[
      ['Cap. 1 — Tipos de Centrales Eléctricas','cap1.html'],
      ['Cap. 2 — Variaciones de frecuencia · control primario y secundario','cap2.html'],
      ['Cap. 3 — Variaciones de tensión','cap3.html'],
      ['Cap. 4 — Control de tensión en condiciones dinámicas o de falla','cap4.html'],
      ['Cap. 5 — Restauración del SEN','cap5.html'],
      ['Cap. 6 — Administración del SEN','cap6.html'],
      ['Cap. 7 — Calidad de la potencia','cap7.html'],
      ['Cap. 8 — Verificación de la Conformidad','cap8_inte.html']
    ]},
    { g:'Manual CONE — Centros de Carga', code:'cone', items:[
      ['Cap. 1 — Criterios de Conexión','cone_c1.html'],
      ['Cap. 2 — Requerimientos técnicos · 2.8 Calidad de la Potencia','cap8.html'],
      ['Cap. 2 — Requerimientos técnicos · 2.1–2.7 y 2.9','cone_c2.html'],
      ['Cap. 3 — Verificación de la Conformidad','cone_c3.html'],
      ['Cap. 4 — Plan de Trabajo','cone_c4.html']
    ]},
    { g:'Disposiciones Operativas', items:[
      ['Manual PSE — Planeación','manual_pse.html'],
      ['Manual ESO — Estados Operativos','manual_eso.html'],
      ['Manual CO — Coordinación Operativa','manual_co.html'],
      ['Manual SEA — Sistemas Aislados','manual_sea.html'],
      ['Manual TIC','manual_tic.html']
    ]}
  ];
  var INTE_FILES = ['cap1.html','cap2.html','cap3.html','cap4.html','cap5.html','cap6.html','cap7.html','cap8_inte.html'];
  var CONE_FILES = ['cone_c1.html','cap8.html','cone_c2.html','cone_c3.html','cone_c4.html'];

  var sb  = document.getElementById('sidebar');
  var btn = document.getElementById('sb-toggle');
  var cur = window.location.pathname.split('/').pop();

  /* Secciones de la página actual (para sub-navegación viva) */
  var pageSecs = [];
  document.querySelectorAll('#contenido h2.sec[id]').forEach(function(h){
    var snum = h.querySelector('.snum');
    var num = snum ? snum.textContent.trim() : '';
    var title = h.textContent.replace(num,'').trim();
    pageSecs.push({ id:h.id, label:(num ? num+' — ' : '')+trunc(title,30) });
  });

  /* ── Barra superior fija con INTE y CONE ──────────────── */
  if (sb) {
    var bar = document.createElement('nav');
    bar.className = 'topbar';
    bar.setAttribute('aria-label','Navegación principal');
    var curManual = INTE_FILES.indexOf(cur)>=0 ? 'inte' : (CONE_FILES.indexOf(cur)>=0 ? 'cone' : '');
    bar.innerHTML =
      '<a class="tb-brand" href="../index_cdr_2v4.html"><span class="tb-mark"><i class="ti ti-bolt" aria-hidden="true"></i></span>Código de Red 2.0</a>'+
      '<div class="tb-links">'+
        '<a href="cap1.html"'+(curManual==='inte'?' class="active"':'')+'>Manual INTE</a>'+
        '<a href="cone_c1.html"'+(curManual==='cone'?' class="active"':'')+'>Manual CONE</a>'+
      '</div>';
    document.body.insertBefore(bar, document.body.firstChild);
    document.body.classList.add('has-topbar');
  }

  /* ── Construir el árbol en la barra lateral ───────────── */
  var sbNav = sb ? sb.querySelector('.sb-nav') : null;
  if (sbNav) {
    sbNav.innerHTML = '';
    TREE.forEach(function(grp){
      var lbl = document.createElement('span');
      lbl.className = 'sb-section-lbl';
      lbl.textContent = grp.g;
      sbNav.appendChild(lbl);
      grp.items.forEach(function(it){
        var a = document.createElement('a');
        a.className = 'sb-cap';
        a.href = it[1];
        a.textContent = it[0];
        if (it[1] === cur){
          a.classList.add('active');
          a.setAttribute('aria-current','page');
        }
        sbNav.appendChild(a);
        /* Sub-secciones vivas de la página actual */
        if (it[1] === cur && pageSecs.length){
          pageSecs.forEach(function(s){
            var sub = document.createElement('a');
            sub.className = 'sb-sub';
            sub.href = '#'+s.id;
            sub.textContent = s.label;
            sbNav.appendChild(sub);
          });
        }
      });
    });
    var fuentes = document.createElement('span');
    fuentes.className = 'sb-section-lbl';
    fuentes.textContent = 'Fuente Oficial';
    sbNav.appendChild(fuentes);
    var dof = document.createElement('a');
    dof.className = 'sb-cap'; dof.href = 'https://dof.gob.mx/2021/CRE/CRE_311221.pdf';
    dof.target = '_blank'; dof.rel = 'noopener'; dof.textContent = '↗ DOF — Texto oficial (PDF)';
    sbNav.appendChild(dof);
  }

  /* ── Toggle barra lateral (escritorio colapsa · móvil desliza) ── */
  if (sb && btn) {
    btn.textContent = isMobile() ? '☰' : '‹';
    btn.setAttribute('aria-label', 'Mostrar u ocultar el índice lateral');
    btn.addEventListener('click', function(){
      if (isMobile()) {
        var o = sb.classList.toggle('open');
        btn.setAttribute('aria-expanded', o);
        btn.textContent = o ? '✕' : '☰';
      } else {
        var c = document.body.classList.toggle('sb-collapsed');
        btn.setAttribute('aria-expanded', !c);
        btn.textContent = c ? '›' : '‹';
        btn.title = c ? 'Mostrar índice' : 'Ocultar índice';
      }
    });
    document.addEventListener('click', function(e){
      if (isMobile() && sb.classList.contains('open') && !sb.contains(e.target) && e.target !== btn){
        sb.classList.remove('open');
        btn.setAttribute('aria-expanded', 'false');
        btn.textContent = '☰';
      }
    });
    window.addEventListener('resize', function(){
      if (isMobile()) {
        document.body.classList.remove('sb-collapsed');
        btn.textContent = sb.classList.contains('open') ? '✕' : '☰';
      } else {
        sb.classList.remove('open');
        btn.textContent = document.body.classList.contains('sb-collapsed') ? '›' : '‹';
      }
    });
  }

  /* ── Barra lateral: grupos colapsables ────────────────── */
  if (sbNav) {
    Array.from(sbNav.querySelectorAll('.sb-section-lbl')).forEach(function(lbl){
      var items = [], n = lbl.nextElementSibling;
      while (n && !n.matches('.sb-section-lbl')) { items.push(n); n = n.nextElementSibling; }
      if (!items.length) return;
      var hasActive = items.some(function(el){ return el.classList.contains('active'); });
      var wrap = document.createElement('div');
      wrap.className = 'sb-group-body';
      if (!hasActive) wrap.hidden = true;
      items.forEach(function(item){ wrap.appendChild(item); });
      lbl.after(wrap);
      var arrow = document.createElement('span');
      arrow.className = 'sb-group-arrow'; arrow.setAttribute('aria-hidden','true');
      arrow.textContent = hasActive ? '▼' : '▶';
      lbl.appendChild(arrow);
      lbl.setAttribute('role','button'); lbl.setAttribute('tabindex','0');
      lbl.setAttribute('aria-expanded', hasActive ? 'true' : 'false');
      function toggleSb(){
        wrap.hidden = !wrap.hidden;
        var open = !wrap.hidden;
        lbl.setAttribute('aria-expanded', open ? 'true' : 'false');
        arrow.textContent = open ? '▼' : '▶';
      }
      lbl.addEventListener('click', toggleSb);
      lbl.addEventListener('keydown', function(e){ if (e.key==='Enter'||e.key===' '){ e.preventDefault(); toggleSb(); } });
    });
  }

  /* ── Contenido: secciones colapsables (h2.sec) ────────── */
  var contenido = document.getElementById('contenido');
  var openSection;
  if (contenido) {
    var h2s = Array.from(contenido.querySelectorAll('h2.sec'));
    var byId = {};

    h2s.forEach(function(h2, idx){
      var siblings = [], n = h2.nextElementSibling;
      while (n && !n.matches('h2.sec, .nav-footer, nav.nav-footer')) { siblings.push(n); n = n.nextElementSibling; }
      if (!siblings.length) return;

      var bodyId = 'sec-body-' + idx;
      var body = document.createElement('div');
      body.className = 'sec-body'; body.id = bodyId; body.hidden = true;
      siblings.forEach(function(sib){ body.appendChild(sib); });
      h2.after(body);

      var tog = document.createElement('button');
      tog.className = 'sec-toggle'; tog.type = 'button';
      tog.setAttribute('aria-expanded','false'); tog.setAttribute('aria-controls', bodyId);
      tog.setAttribute('title','Expandir / colapsar sección');
      tog.innerHTML = '<span aria-hidden="true">▾</span>';
      h2.appendChild(tog);

      function setOpen(open){
        body.hidden = !open;
        tog.setAttribute('aria-expanded', open ? 'true':'false');
        tog.querySelector('span').textContent = open ? '▴':'▾';
      }
      function toggleSec(e){ if (e) e.stopPropagation(); setOpen(body.hidden); }
      tog.addEventListener('click', toggleSec);
      h2.style.cursor = 'pointer';
      h2.addEventListener('click', function(e){ if (e.target !== tog && !tog.contains(e.target)) toggleSec(); });
      if (h2.id) byId[h2.id] = setOpen;

      var endBtn = document.createElement('button');
      endBtn.className = 'sec-collapse-end'; endBtn.type = 'button';
      endBtn.innerHTML = '<span aria-hidden="true">▲</span> Contraer sección';
      endBtn.addEventListener('click', function(){
        setOpen(false);
        h2.scrollIntoView({ behavior:'smooth', block:'start' });
      });
      body.appendChild(endBtn);
    });

    openSection = function(id){ if (byId[id]){ byId[id](true); } };
    /* Al llegar por un enlace #sección, ábrela */
    function openFromHash(){
      var id = location.hash.replace('#','');
      if (id && byId[id]){ byId[id](true);
        var el = document.getElementById(id); if (el) setTimeout(function(){ el.scrollIntoView(); }, 30);
      }
    }
    window.addEventListener('hashchange', openFromHash);
    if (location.hash) openFromHash();
    /* Clic en sub-enlaces del índice → abre la sección destino */
    document.addEventListener('click', function(e){
      var a = e.target.closest && e.target.closest('a[href^="#"]');
      if (a){ var id = a.getAttribute('href').slice(1); if (byId[id]) byId[id](true); }
    });

    if (h2s.length >= 2) {
      var allBtn = document.createElement('button');
      allBtn.className = 'all-toggle'; allBtn.type = 'button';
      allBtn.textContent = 'Expandir todo';
      var allOpen = false;
      allBtn.addEventListener('click', function(){
        allOpen = !allOpen;
        contenido.querySelectorAll('.sec-body').forEach(function(b){ b.hidden = !allOpen; });
        contenido.querySelectorAll('.sec-toggle').forEach(function(b){
          b.setAttribute('aria-expanded', allOpen?'true':'false');
          b.querySelector('span').textContent = allOpen?'▴':'▾';
        });
        allBtn.textContent = allOpen ? 'Colapsar todo' : 'Expandir todo';
      });
      var anchor = contenido.querySelector('h1.titulo') || contenido.querySelector('.eyebrow');
      if (anchor && anchor.nextElementSibling){ anchor.parentNode.insertBefore(allBtn, anchor.nextElementSibling); }
    }

    /* ── Copiar tablas (TSV → Excel/Sheets) ─────────────── */
    function tableToTSV(table){
      var rows = [];
      table.querySelectorAll('tr').forEach(function(tr){
        var cells = [];
        tr.querySelectorAll('th,td').forEach(function(c){ cells.push((c.innerText||c.textContent||'').replace(/\s+/g,' ').trim()); });
        rows.push(cells.join('\t'));
      });
      return rows.join('\n');
    }
    function copyText(txt){
      if (navigator.clipboard && window.isSecureContext){ return navigator.clipboard.writeText(txt); }
      return new Promise(function(res, rej){
        var ta = document.createElement('textarea');
        ta.value = txt; ta.style.position='fixed'; ta.style.opacity='0';
        document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); res(); } catch(e){ rej(e); }
        document.body.removeChild(ta);
      });
    }
    contenido.querySelectorAll('.tbl-wrap').forEach(function(wrap){
      var table = wrap.querySelector('table'); if (!table) return;
      var cap = wrap.querySelector('.tbl-caption');
      var cbtn = document.createElement('button');
      cbtn.className = 'tbl-copy'; cbtn.type = 'button';
      cbtn.setAttribute('aria-label','Copiar tabla');
      cbtn.innerHTML = '<span aria-hidden="true">⧉</span><span class="tc-t">Copiar</span>';
      cbtn.addEventListener('click', function(e){
        e.stopPropagation();
        copyText(tableToTSV(table)).then(function(){
          cbtn.classList.add('ok'); cbtn.querySelector('.tc-t').textContent='Copiada ✓';
          setTimeout(function(){ cbtn.classList.remove('ok'); cbtn.querySelector('.tc-t').textContent='Copiar'; },1500);
        });
      });
      if (cap) cap.appendChild(cbtn); else wrap.insertBefore(cbtn, wrap.firstChild);
    });
  }

})();
