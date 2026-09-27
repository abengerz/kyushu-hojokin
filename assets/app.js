(function () {
  var B = window.KH_BASE || '';
  var DATA_URL = window.KH_DATA_URL || (B + '/assets/data.json');

  /* ---------- 共通 ---------- */
  var burger = document.querySelector('.burger'), navm = document.querySelector('nav.main');
  if (burger && navm) burger.addEventListener('click', function () { navm.classList.toggle('open'); });

  function yen(v) {
    if (!v) return '—';
    if (v >= 100000000) return (v / 100000000).toFixed(v % 100000000 ? 1 : 0).replace(/\.0$/, '') + '億円';
    if (v >= 10000) return Math.round(v / 10000).toLocaleString() + '万円';
    return Number(v).toLocaleString() + '円';
  }
  function jday(s) {
    if (!s) return '';
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
    return m ? m[1] + '.' + m[2] + '.' + m[3] : '';
  }
  function daysLeft(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s || '');
    if (!m) return null;
    var d = new Date(+m[1], +m[2] - 1, +m[3]), t = new Date();
    t.setHours(0, 0, 0, 0);
    return Math.round((d - t) / 86400000);
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  var _data = null, _pending = null;
  function load() {
    if (_data) return Promise.resolve(_data);
    if (_pending) return _pending;
    _pending = fetch(DATA_URL).then(function (r) { return r.json(); })
      .then(function (j) { _data = j; window.KH_DATA = j; return j; })
      .catch(function () { _data = []; return []; });
    return _pending;
  }
  if (window.KH_EAGER) load();

  var PREFS = ['福岡県', '佐賀県', '長崎県', '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県'];
  var PSLUG = { '福岡県': 'fukuoka', '佐賀県': 'saga', '長崎県': 'nagasaki', '熊本県': 'kumamoto', '大分県': 'oita', '宮崎県': 'miyazaki', '鹿児島県': 'kagoshima', '沖縄県': 'okinawa' };

  /* ---------- 30秒診断 ---------- */
  var sd = document.getElementById('shindan');
  if (sd) {
    var pick = { pref: '', purpose: '', size: '' };
    sd.querySelectorAll('.opts').forEach(function (g) {
      g.addEventListener('click', function (e) {
        var t = e.target.closest('button'); if (!t) return;
        var was = t.getAttribute('aria-pressed') === 'true';
        g.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', 'false'); });
        t.setAttribute('aria-pressed', was ? 'false' : 'true');
        pick[g.dataset.key] = was ? '' : t.dataset.v;
        run();
      });
    });
    function run() {
      load().then(function (D) {
        var out = document.getElementById('sd-out');
        var hits = D.filter(function (r) {
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
          h += '<p style="font-size:13.5px;opacity:.75;margin:14px 0 0">条件に合う受付中の制度が見つかりませんでした。条件をゆるめるか、<a href="' + B + '/search/" style="color:#8FC2E8;text-decoration:underline">全制度検索</a>から終了分を含めてお探しください。</p>';
        } else {
          hits.slice(0, 8).forEach(function (r) {
            h += '<a class="hit" href="' + B + '/subsidy/' + r.i + '/"><b>' + esc(r.t) + '</b><span>' +
              r.p.join('・') + '　上限 ' + yen(r.m) + (r.d ? '　締切 ' + jday(r.d) : '') + '</span></a>';
          });
          h += '<div style="margin-top:22px"><a class="btn" style="background:#fff;border-color:#fff;color:#14476E" href="' + B + '/search/">条件を細かく指定して探す</a></div>';
        }
        out.innerHTML = h;
      });
    }
    run();
  }

  /* ---------- 全制度検索 ---------- */
  var sp = document.getElementById('searchpage');
  if (sp) {
    var els = ['f-kw', 'f-pref', 'f-purpose', 'f-industry', 'f-status', 'f-sort'].map(function (i) { return document.getElementById(i); });
    var page = 1, PER = 20;
    var u = new URLSearchParams(location.search);
    if (u.get('pref') && els[1]) els[1].value = u.get('pref');
    if (u.get('purpose') && els[2]) els[2].value = u.get('purpose');
    if (u.get('industry') && els[3]) els[3].value = u.get('industry');
    if (u.get('q') && els[0]) els[0].value = u.get('q');
    document.getElementById('res').innerHTML = '<div class="empty">読み込んでいます…</div>';

    function draw() {
      var D = _data || [];
      var kw = (els[0].value || '').trim(), pf = els[1].value, pu = els[2].value, ind = els[3].value, st = els[4].value, so = els[5].value;
      var rs = D.filter(function (r) {
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
        var left = daysLeft(r.d);
        var badge = r.st === 'open'
          ? (left !== null && left <= 30 ? '<span class="tag soon">締切まで' + left + '日</span>' : '<span class="tag open">受付中</span>')
          : r.st === 'soon' ? '<span class="tag soon">受付予定</span>' : '<span class="tag closed">受付終了</span>';
        h += '<a class="row" href="' + B + '/subsidy/' + r.i + '/">' +
          '<div class="no">' + String((page - 1) * PER + k + 1).padStart(3, '0') + '</div>' +
          '<div><h3>' + esc(r.t) + '</h3><div class="meta">' + badge +
          (r.w ? '<span class="tag">全国対象</span>' : r.p.slice(0, 4).map(function (x) { return '<span class="tag pref">' + x + '</span>'; }).join('')) +
          (r.u ? '<span class="tag">' + esc(r.u.split(' / ')[0]) + '</span>' : '') + '</div></div>' +
          '<div class="amt"><small>補助上限</small>' + yen(r.m) +
          (r.r ? '<div class="rt">補助率 ' + esc(r.r) + '</div>' : '') +
          (r.d ? '<div class="dl">締切 ' + jday(r.d) + (left !== null && left >= 0 && left <= 60 ? ' <b>あと' + left + '日</b>' : '') + '</div>' : '') +
          '</div></a>';
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
    load().then(draw);
  }


  /* ---------- 新着カルーセル ---------- */
  document.querySelectorAll('[data-carousel]').forEach(function (car) {
    var track = car.querySelector('.car-track');
    var bar = car.querySelector('.car-bar i');
    var wrapEl = car.closest('.wrap') || document;
    var prev = wrapEl.querySelector('[data-car="prev"]');
    var next = wrapEl.querySelector('[data-car="next"]');
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    function step() {
      var first = track.querySelector('a');
      return first ? first.getBoundingClientRect().width + 16 : 300;
    }
    function sync() {
      var max = track.scrollWidth - track.clientWidth;
      var r = max > 0 ? track.scrollLeft / max : 0;
      if (bar) bar.style.width = Math.max(12, Math.min(100, (track.clientWidth / track.scrollWidth) * 100 + r * 8)) + '%';
      if (bar) bar.style.marginLeft = (r * (100 - parseFloat(bar.style.width))) + '%';
      if (prev) prev.disabled = track.scrollLeft <= 4;
      if (next) next.disabled = track.scrollLeft >= max - 4;
    }
    if (prev) prev.addEventListener('click', function () { track.scrollLeft -= step() * 2; });
    if (next) next.addEventListener('click', function () { track.scrollLeft += step() * 2; });
    track.addEventListener('scroll', sync, { passive: true });
    window.addEventListener('resize', sync);
    sync();

    if (!reduce) {
      var timer = null, paused = false;
      function tick() {
        if (paused) return;
        var max = track.scrollWidth - track.clientWidth;
        if (track.scrollLeft >= max - 4) track.scrollLeft = 0;
        else track.scrollLeft += step();
      }
      function start() { if (!timer) timer = setInterval(tick, 4200); }
      function stop() { clearInterval(timer); timer = null; }
      car.addEventListener('mouseenter', function () { paused = true; });
      car.addEventListener('mouseleave', function () { paused = false; });
      car.addEventListener('focusin', function () { paused = true; });
      track.addEventListener('touchstart', function () { paused = true; }, { passive: true });
      if ('IntersectionObserver' in window) {
        new IntersectionObserver(function (es) {
          es[0].isIntersecting ? start() : stop();
        }, { threshold: .2 }).observe(car);
      } else start();
    }
  });

  /* ---------- 締切アラートの申し込みフォーム ---------- */
  var af = document.getElementById('alertform');
  if (af) {
    af.addEventListener('submit', function (e) {
      e.preventDefault();
      var g = function (id) { return (document.getElementById(id) || {}).value || ''; };
      var pref = g('a-pref'), ind = g('a-ind'), pur = g('a-pur'), co = g('a-co'), nm = g('a-name');
      var lines = [
        '九州補助金ナビの締切アラートを申し込みます。',
        '',
        '会社名・屋号：' + (co || '（未記入）'),
        'お名前：' + (nm || '（未記入）'),
        '都道府県：' + (pref || '指定しない'),
        '業種：' + (ind || '指定しない'),
        '目的：' + (pur || '指定しない'),
        '',
        '（このまま送信してください。折り返しご連絡します。）'
      ];
      var subj = '【締切アラート申込】' + (pref || '九州・沖縄') + (ind ? '／' + ind : '');
      location.href = 'mailto:info@avengerz-japan.com?subject=' + encodeURIComponent(subj) +
        '&body=' + encodeURIComponent(lines.join('\n'));
    });
  }

  /* ================= 補助金AI相談 ================= */
  var FAQ = [
    { k: ['いつ', '入金', 'もらえる', '振り込', '後払い', '前払い'], a:
      '補助金は原則「後払い」です。\n\n1. 申請 → 2. 採択 → 3. 交付決定 → 4. 自分でお金を払って設備を導入 → 5. 実績報告 → 6. 補助金の入金\n\nという順番なので、設備代はいったん全額を自社で立て替える必要があります。入金まで採択から半年〜1年かかることも珍しくありません。九州の地銀・信金はつなぎ資金に慣れているので、採択前の段階で相談しておくと安全です。',
      l: [['資金繰りと申請実務のガイド', '/guide/shinsa/']] },
    { k: ['gbiz', 'ジービズ', 'gビズ'], a:
      '国の補助金の電子申請には、原則としてgBizIDプライムが必要です。\n\n・法人は印鑑証明書、個人事業主は印鑑登録証明書が必要\n・書類郵送方式だと発行まで1〜2週間\n・マイナンバーカードでのオンライン申請なら短縮できます\n\n公募期間は1〜2か月しかないので、制度を探すのと同時に着手してください。',
      l: [['gBizIDプライムの取り方', '/guide/gbizid/']] },
    { k: ['交付決定', '発注', '先に買', '前に買', '契約'], a:
      'いちばん多い事故が「交付決定前の発注」です。\n\n見積書を取るところまでは問題ありませんが、発注書・契約書の日付が交付決定通知より前だと、その経費はまるごと対象外になります。設備の手配は必ず交付決定を受けてから行ってください。',
      l: [['業務改善助成金ガイド', '/guide/gyomu-kaizen/']] },
    { k: ['商工会', '窓口', '相談先', 'どこに'], a:
      '小規模事業者持続化補助金は、商工会または商工会議所の窓口を通して申請します。\n\n市部は商工会議所（福岡市・北九州市・熊本市・鹿児島市・那覇市など）、町村部は商工会が窓口です。事業支援計画書という書類を窓口が発行するので、締切の2週間前までには相談を入れてください。',
      l: [['持続化補助金ガイド', '/guide/jizokuka/']] },
    { k: ['書き方', '事業計画', '採択', '通る', '落ち', '審査'], a:
      '審査は加点方式というより消去法です。冒頭3行で「誰の・どんな困りごとを・どう解決していくら売上を作るのか」が数字で分からない書類は、後段を精読されません。\n\n・「地域に貢献します」→ 雇用○名、地場調達比率○%と数字にする\n・「最新設備を導入します」→ 現状の能力と導入後の差分を出す\n・「売上が伸びます」→ 単価×客数×回数に分解して根拠を示す',
      l: [['採択される事業計画書の書き方', '/guide/shinsa/']] },
    { k: ['個人事業主', 'フリーランス', '一人', 'ひとり'], a:
      '個人事業主でも申請できる制度は多くあります。持続化補助金は個人事業主の利用が中心ですし、IT導入補助金やキャリアアップ助成金も対象です。開業届と確定申告書の控えが基本の添付書類になります。',
      l: [['個人事業主向けの制度一覧', '/audience/sole/'], ['小規模事業者向け', '/audience/micro/']] },
    { k: ['沖縄', '離島', '振興'], a:
      '沖縄には、沖縄振興特別措置法にもとづく独自の支援の系統があります。全国共通の補助金と並行して、内閣府沖縄総合事務局・沖縄県・沖縄県産業振興公社の公募も必ず確認してください。同じ投資計画でも、どちらのルートで出すかで補助率と上限が変わることがあります。',
      l: [['沖縄限定の支援の枠組み', '/guide/okinawa/'], ['沖縄県の補助金一覧', '/pref/okinawa/']] },
    { k: ['許可', '免許', '届出', '開業', '許認可'], a:
      '補助金より先に、その事業を始めるための許認可が必要なことがあります。建設業許可、飲食店営業許可、運送事業許可など、業種別にまとめています。内装工事の着工前に管轄窓口へ事前相談するのが実務の鉄則です。',
      l: [['許認可・届出ガイド', '/permit/']] },
    { k: ['税金', '課税', '確定申告', '仕訳', '圧縮記帳'], a:
      '補助金は原則として課税対象の収入になります（法人は益金、個人は事業所得の総収入金額）。固定資産の取得に充てた場合は、一定の要件のもとで圧縮記帳により課税の繰り延べができます。処理方法は顧問税理士にご確認ください。',
      l: [['専門家に相談する', '/experts/']] },
    { k: ['締切', '期限', 'いつまで', '急ぎ'], a:
      '締切が近い順に並べたカレンダーを用意しています。申請書の作成には通常2〜4週間かかるので、締切まで3週間を切っている制度は専門家の力を借りることをおすすめします。',
      l: [['締切カレンダー', '/deadline/']] }
  ];
  var IND_KW = [['製造', '製造業'], ['工場', '製造業'], ['建設', '建設業'], ['工務店', '建設業'], ['土木', '建設業'],
    ['IT', '情報通信業'], ['アプリ', '情報通信業'], ['ソフト', '情報通信業'], ['通信', '情報通信業'],
    ['小売', '小売業'], ['卸', '卸売業'], ['店', '小売業'], ['飲食', '飲食サービス業'], ['レストラン', '飲食サービス業'],
    ['居酒屋', '飲食サービス業'], ['カフェ', '飲食サービス業'], ['宿泊', '宿泊業'], ['ホテル', '宿泊業'], ['旅館', '宿泊業'],
    ['民泊', '宿泊業'], ['医療', '医療'], ['病院', '医療'], ['クリニック', '医療'], ['介護', '福祉'], ['福祉', '福祉'],
    ['農', '農業'], ['林業', '林業'], ['漁', '漁業'], ['水産', '漁業'], ['養殖', '漁業'],
    ['運送', '運輸業'], ['物流', '運輸業'], ['トラック', '運輸業'], ['タクシー', '運輸業'],
    ['不動産', '不動産業'], ['美容', '生活関連サービス'], ['理容', '生活関連サービス'], ['サロン', '生活関連サービス'],
    ['教育', '教育'], ['塾', '教育'], ['保育', '福祉']];
  var PUR_KW = [['設備', '設備整備'], ['機械', '設備整備'], ['導入', '設備整備'], ['IT', '設備整備'], ['DX', '設備整備'],
    ['システム', '設備整備'], ['販路', '販路拡大'], ['売上', '販路拡大'], ['海外', '販路拡大'], ['輸出', '販路拡大'],
    ['展示会', '販路拡大'], ['EC', '販路拡大'], ['採用', '雇用'], ['人手', '雇用'], ['人材不足', '雇用'],
    ['正社員', '雇用'], ['職場', '雇用'], ['育成', '人材育成'], ['研修', '人材育成'], ['教育訓練', '人材育成'],
    ['リスキ', '人材育成'], ['創業', '新たな事業'], ['起業', '新たな事業'], ['新規事業', '新たな事業'],
    ['新事業', '新たな事業'], ['研究', '研究開発'], ['開発', '研究開発'], ['承継', '引き継'], ['事業承継', '引き継'],
    ['資金繰り', '資金繰り'], ['賃上げ', '賃上げ'], ['観光', 'まちづくり'], ['地域', 'まちづくり']];
  var SIZE_KW = [['一人', 5], ['ひとり', 5], ['1人', 5], ['5人', 5], ['5名', 5], ['10人', 20], ['20人', 20],
    ['20名', 20], ['30人', 50], ['50人', 50], ['100人', 100], ['300人', 300]];

  function analyze(q) {
    var f = { pref: '', ind: '', pur: '', size: 0, soon: false, big: false, text: q };
    PREFS.forEach(function (p) { if (q.indexOf(p.slice(0, -1)) >= 0) f.pref = p; });
    for (var i = 0; i < IND_KW.length; i++) if (q.indexOf(IND_KW[i][0]) >= 0) { f.ind = IND_KW[i][1]; break; }
    for (var j = 0; j < PUR_KW.length; j++) if (q.indexOf(PUR_KW[j][0]) >= 0) { f.pur = PUR_KW[j][1]; break; }
    for (var k = 0; k < SIZE_KW.length; k++) if (q.indexOf(SIZE_KW[k][0]) >= 0) { f.size = SIZE_KW[k][1]; break; }
    if (/締切|急ぎ|近い|今月|すぐ/.test(q)) f.soon = true;
    if (/大きい|高額|多い|上限|たくさん/.test(q)) f.big = true;
    return f;
  }

  function search(f) {
    var D = _data || [];
    return D.filter(function (r) {
      if (r.st === 'closed') return false;
      if (f.pref && r.p.indexOf(f.pref) < 0) return false;
      if (f.ind && (r.g || '').indexOf(f.ind) < 0) return false;
      if (f.pur && (r.u || '').indexOf(f.pur) < 0) return false;
      if (f.size && r.e && r.e.indexOf('制約なし') < 0) {
        var m = /(\d+)名以下/.exec(r.e);
        if (m && +m[1] < f.size) return false;
      }
      return true;
    }).sort(function (a, b) {
      if (f.soon) return (a.d || '9999') < (b.d || '9999') ? -1 : 1;
      return (b.m || 0) - (a.m || 0);
    });
  }

  function cardHTML(r) {
    var left = daysLeft(r.d);
    return '<a class="card" href="' + B + '/subsidy/' + r.i + '/"><b>' + esc(r.t) + '</b><span>' +
      (r.w ? '全国対象' : r.p.slice(0, 3).join('・')) + '　上限 ' + yen(r.m) +
      (r.d ? '　締切 ' + jday(r.d) + (left !== null && left >= 0 ? '（あと' + left + '日）' : '') : '') + '</span></a>';
  }

  function answer(q) {
    var lower = q.toLowerCase();
    for (var i = 0; i < FAQ.length; i++) {
      var hit = FAQ[i].k.some(function (w) { return lower.indexOf(w.toLowerCase()) >= 0; });
      if (hit) {
        var t = FAQ[i].a;
        if (FAQ[i].l) t += '\n\n' + FAQ[i].l.map(function (x) { return '<a href="' + B + x[1] + '">' + x[0] + ' →</a>'; }).join('\n');
        return t;
      }
    }
    var f = analyze(q);
    if (!f.pref && !f.ind && !f.pur && !f.soon && !f.big) {
      return '恐れ入ります、もう少し手がかりをいただけますか。\n\n・事業所のある県（例：熊本）\n・業種（例：製造業、飲食店）\n・やりたいこと（例：設備を入れたい、人を採りたい）\n\nのどれかが入っていると探せます。\n\n' +
        '<a href="' + B + '/search/">検索画面で細かく絞り込む →</a>';
    }
    var hits = search(f);
    var cond = [];
    if (f.pref) cond.push(f.pref);
    if (f.ind) cond.push(f.ind);
    if (f.pur) cond.push(f.pur + '関連');
    if (f.size) cond.push('従業員' + f.size + '名規模');
    var head = (cond.length ? cond.join('／') + ' の条件で、' : '') + '受付中の制度が <b>' + hits.length + '件</b> 見つかりました。';
    if (!hits.length) {
      return head + '\n\n条件をゆるめるか、受付終了分も含めて検索してみてください。国の公募は年度替わりに再開するものが多いので、終了分の内容を見ておくと次の公募で先回りできます。\n\n' +
        '<a href="' + B + '/search/' + (f.pref ? '?pref=' + encodeURIComponent(f.pref) : '') + '">検索画面をひらく →</a>';
    }
    var body = head + (f.soon ? '締切の早い順' : '補助上限の大きい順') + 'に並べています。\n';
    hits.slice(0, 4).forEach(function (r) { body += cardHTML(r); });
    body += '\n<a href="' + B + '/search/' + (f.pref ? '?pref=' + encodeURIComponent(f.pref) : '') + '">すべての結果を検索画面で見る →</a>';
    if (f.pref) body += '\n<a href="' + B + '/pref/' + PSLUG[f.pref] + '/">' + f.pref + 'の補助金ページ →</a>';
    return body;
  }

  var panel = document.getElementById('ai-panel');
  if (panel) {
    var log = document.getElementById('ai-log'), chips = document.getElementById('ai-chips');
    var form = document.getElementById('ai-form'), input = document.getElementById('ai-text');
    var started = false;
    function say(text, who) {
      var d = document.createElement('div');
      d.className = 'ai-msg ' + (who || 'bot');
      d.innerHTML = who === 'me' ? esc(text) : text;
      log.appendChild(d); log.scrollTop = log.scrollHeight;
    }
    function setChips(list) {
      chips.innerHTML = list.map(function (q) { return '<button type="button">' + esc(q) + '</button>'; }).join('');
    }
    var STARTERS = ['熊本の製造業で設備を入れたい', '福岡で人を採用したい', '締切が近いものは？', 'gBizIDって必要？', '補助金はいつもらえる？'];
    function open() {
      panel.classList.add('open');
      if (!started) {
        started = true;
        load();
        say('九州・沖縄8県の補助金を探すお手伝いをします。\n県・業種・やりたいことを文章で入れてください。\n\n例：「熊本の製造業で設備を入れたい」');
        setChips(STARTERS);
      }
      setTimeout(function () { input.focus(); }, 60);
    }
    document.getElementById('ai-open').addEventListener('click', open);
    document.getElementById('ai-close').addEventListener('click', function () { panel.classList.remove('open'); });
    chips.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      ask(b.textContent);
    });
    var ex = document.getElementById('ai-examples');
    if (ex) ex.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-q]'); if (!b) return;
      e.preventDefault(); open(); ask(b.dataset.q);
    });
    function ask(q) {
      q = (q || '').trim(); if (!q) return;
      say(q, 'me'); input.value = '';
      chips.innerHTML = '';
      load().then(function () {
        setTimeout(function () {
          say(answer(q));
          setChips(['締切が近いものは？', '補助率はどれくらい？', '個人事業主でも使える？', '申請に何が必要？']);
        }, 260);
      });
    }
    form.addEventListener('submit', function (e) { e.preventDefault(); ask(input.value); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); ask(input.value); }
    });
  }
})();
