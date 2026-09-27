(function () {
  var B = window.KH_BASE || '';
  var b = document.querySelector('.burger'), n = document.querySelector('nav.main');
  if (b && n) b.addEventListener('click', function () { n.classList.toggle('open'); });

  var yen = function (v) {
    if (!v && v !== 0) return '—';
    if (v >= 100000000) return (v / 100000000).toFixed(v % 100000000 ? 1 : 0) + '億円';
    if (v >= 10000) return Math.round(v / 10000).toLocaleString() + '万円';
    return Number(v).toLocaleString() + '円';
  };
  var jday = function (s) {
    if (!s) return '';
    var d = new Date(s);
    if (isNaN(d)) return '';
    return d.getFullYear() + '.' + ('0' + (d.getMonth() + 1)).slice(-2) + '.' + ('0' + d.getDate()).slice(-2);
  };

  /* ---------- 30秒診断 ---------- */
  var sd = document.getElementById('shindan');
  if (sd && window.KH_DATA) {
    var pick = { pref: '', purpose: '', size: '' };
    sd.querySelectorAll('.opts').forEach(function (g) {
      g.addEventListener('click', function (e) {
        var t = e.target.closest('button'); if (!t) return;
        g.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', 'false'); });
        t.setAttribute('aria-pressed', 'true');
        pick[g.dataset.key] = t.dataset.v;
        run();
      });
    });
    function run() {
      var out = document.getElementById('sd-out');
      var hits = window.KH_DATA.filter(function (r) {
        if (r.st === 'closed') return false;
        if (pick.pref && r.p.indexOf(pick.pref) < 0) return false;
        if (pick.purpose && (r.u || '').indexOf(pick.purpose) < 0) return false;
        if (pick.size && r.e && r.e.indexOf('制約なし') < 0 && r.e.indexOf(pick.size) < 0) return false;
        return true;
      });
      hits.sort(function (a, b) { return (b.m || 0) - (a.m || 0); });
      var h = '<div id="sd-count">受付中の該当制度 ' + hits.length + ' 件' +
        (hits.length > 8 ? '<span style="font-weight:400;font-size:12px;opacity:.6"> / 上位8件を表示</span>' : '') + '</div>';
      if (!hits.length) {
        h += '<p style="font-size:13.5px;opacity:.7;margin:14px 0 0">条件に合う受付中の制度が見つかりませんでした。条件をゆるめるか、<a href="' + B + '/search/" style="color:#C08A2E;text-decoration:underline">全制度検索</a>から終了分を含めてお探しください。</p>';
      } else {
        hits.slice(0, 8).forEach(function (r) {
          h += '<a class="hit" href="' + B + '/subsidy/' + r.i + '/"><b>' + r.t + '</b><span>' +
            r.p.join('・') + '　上限 ' + yen(r.m) + (r.d ? '　締切 ' + jday(r.d) : '') + '</span></a>';
        });
        h += '<div style="margin-top:22px"><a class="btn" style="background:#C08A2E;border-color:#C08A2E;color:#171A1C" href="' + B + '/search/">条件を細かく指定して探す</a></div>';
      }
      out.innerHTML = h;
    }
    run();
  }

  /* ---------- 全制度検索 ---------- */
  var sp = document.getElementById('searchpage');
  if (sp && window.KH_DATA) {
    var els = ['f-kw', 'f-pref', 'f-purpose', 'f-industry', 'f-status', 'f-sort'].map(function (i) { return document.getElementById(i); });
    var page = 1, PER = 20;
    function params() {
      var u = new URLSearchParams(location.search);
      if (u.get('pref') && els[1]) els[1].value = u.get('pref');
      if (u.get('purpose') && els[2]) els[2].value = u.get('purpose');
      if (u.get('industry') && els[3]) els[3].value = u.get('industry');
      if (u.get('q') && els[0]) els[0].value = u.get('q');
    }
    params();
    function draw() {
      var kw = (els[0].value || '').trim(), pf = els[1].value, pu = els[2].value, ind = els[3].value, st = els[4].value, so = els[5].value;
      var rs = window.KH_DATA.filter(function (r) {
        if (pf && r.p.indexOf(pf) < 0) return false;
        if (pu && (r.u || '').indexOf(pu) < 0) return false;
        if (ind && (r.g || '').indexOf(ind) < 0) return false;
        if (st === 'open' && r.st === 'closed') return false;
        if (st === 'closed' && r.st !== 'closed') return false;
        if (kw && (r.t + ' ' + (r.n || '')).toLowerCase().indexOf(kw.toLowerCase()) < 0) return false;
        return true;
      });
      rs.sort(function (a, b) {
        if (so === 'amount') return (b.m || 0) - (a.m || 0);
        if (so === 'deadline') return (a.d || '9999') < (b.d || '9999') ? -1 : 1;
        return (b.s || '') < (a.s || '') ? -1 : 1;
      });
      var tot = rs.length, pages = Math.max(1, Math.ceil(tot / PER));
      if (page > pages) page = 1;
      document.getElementById('res-count').innerHTML = '<strong>' + tot.toLocaleString() + '</strong> 件';
      var h = '';
      rs.slice((page - 1) * PER, page * PER).forEach(function (r, k) {
        var badge = r.st === 'open' ? '<span class="tag open">受付中</span>' : r.st === 'soon' ? '<span class="tag soon">受付予定</span>' : '<span class="tag closed">受付終了</span>';
        h += '<a class="row" href="' + B + '/subsidy/' + r.i + '/">' +
          '<div class="no">' + String((page - 1) * PER + k + 1).padStart(3, '0') + '</div>' +
          '<div><h3>' + r.t + '</h3><div class="meta">' + badge +
          r.p.slice(0, 4).map(function (x) { return '<span class="tag pref">' + x + '</span>'; }).join('') +
          (r.u ? '<span class="tag">' + r.u.split(' / ')[0] + '</span>' : '') + '</div></div>' +
          '<div class="amt"><small>補助上限</small>' + yen(r.m) + (r.d ? '<div class="dl">締切 ' + jday(r.d) + '</div>' : '') + '</div></a>';
      });
      document.getElementById('res').innerHTML = h || '<div class="empty">条件に合う制度が見つかりませんでした。条件を減らしてお試しください。</div>';
      var pn = '';
      if (pages > 1) {
        if (page > 1) pn += '<a href="#" data-p="' + (page - 1) + '">前へ</a>';
        for (var i = Math.max(1, page - 2); i <= Math.min(pages, page + 2); i++)
          pn += i === page ? '<span class="cur">' + i + '</span>' : '<a href="#" data-p="' + i + '">' + i + '</a>';
        if (page < pages) pn += '<a href="#" data-p="' + (page + 1) + '">次へ</a>';
      }
      document.getElementById('pgn').innerHTML = pn;
    }
    els.forEach(function (e) { if (e) e.addEventListener(e.tagName === 'INPUT' ? 'input' : 'change', function () { page = 1; draw(); }); });
    document.getElementById('pgn').addEventListener('click', function (e) {
      var a = e.target.closest('a'); if (!a) return; e.preventDefault();
      page = +a.dataset.p; draw(); window.scrollTo({ top: sp.offsetTop - 80, behavior: 'smooth' });
    });
    draw();
  }
})();
