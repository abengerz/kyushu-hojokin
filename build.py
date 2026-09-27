# -*- coding: utf-8 -*-
"""九州補助金ナビ — 静的サイトジェネレータ（jGrants公開APIの実データを使用）"""
import json, os, re, html, shutil, datetime, collections

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(ROOT, "site")
SITE_NAME = "九州補助金ナビ"
SITE_DESC = "福岡・佐賀・長崎・熊本・大分・宮崎・鹿児島・沖縄の補助金／助成金を、国のオープンデータから毎回まとめて検索。"
BASE_URL  = os.environ.get("KH_BASE_URL", "").rstrip("/")   # オリジン。例: https://abengerz.github.io
TODAY     = datetime.date.today()
TODAY_JP  = f"{TODAY.year}年{TODAY.month}月{TODAY.day}日"

PREFS = [
    ("fukuoka","福岡県","FUKUOKA","九州の経済中枢。天神・博多の商業集積とアジア向け物流拠点を抱え、県・市の上乗せ支援が最も厚い。"),
    ("saga","佐賀県","SAGA","有田焼・伊万里の窯業と農業が基幹。県外展開や事業承継を後押しする制度が目立つ。"),
    ("nagasaki","長崎県","NAGASAKI","造船・水産と観光。離島が多く、離島振興・交通・インバウンド関連の枠が用意されやすい。"),
    ("kumamoto","熊本県","KUMAMOTO","TSMC進出で半導体サプライチェーンが急拡大。設備投資・人材確保の需要が全国屈指。"),
    ("oita","OITA_DUMMY","OITA","温泉観光と自動車・半導体関連の製造業が両輪。省エネ・地熱など環境系の制度が特徴。"),
    ("miyazaki","宮崎県","MIYAZAKI","畜産・施設園芸が全国上位。一次産業の設備更新と加工・輸出の支援が中心。"),
    ("kagoshima","鹿児島県","KAGOSHIMA","焼酎・黒毛和牛・養殖。食品加工と輸出、離島・過疎地域の事業維持が論点。"),
    ("okinawa","沖縄県","OKINAWA","観光とIT。沖縄振興特別措置法にもとづく沖縄限定の優遇・補助が別枠で存在する。"),
]
PREFS[4] = ("oita","大分県","OITA",PREFS[4][3])
PREF_BY_NAME = {p[1]: p for p in PREFS}
PREF_NAMES   = [p[1] for p in PREFS]

def esc(s): return html.escape(s or "", quote=True)

def slug(s):
    s = re.sub(r"[^\w぀-ヿ一-鿿]+", "-", s or "").strip("-")
    import hashlib
    return hashlib.md5((s or "x").encode()).hexdigest()[:10]

def yen(v):
    if not v: return "—"
    v = int(v)
    if v >= 100000000:
        a = v/100000000
        return (f"{a:.1f}".rstrip("0").rstrip(".")) + "億円"
    if v >= 10000: return f"{round(v/10000):,}万円"
    return f"{v:,}円"

def jd(s):
    if not s: return ""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    return f"{m.group(1)}.{m.group(2)}.{m.group(3)}" if m else ""

def jd_long(s):
    if not s: return "—"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    return f"{m.group(1)}年{int(m.group(2))}月{int(m.group(3))}日" if m else "—"

def dateobj(s):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s or "")
    return datetime.date(int(m.group(1)),int(m.group(2)),int(m.group(3))) if m else None

# ---------------------------------------------------------------- データ読込
def _load(name, default):
    fp = os.path.join(ROOT, "data", name)
    if not os.path.exists(fp):
        print(f"[warn] data/{name} がありません。fetch.py を先に実行してください。")
        return default
    return json.load(open(fp, encoding="utf-8"))

idx = _load("index.json", {})
det = _load("details.json", {})
if not idx:
    raise SystemExit("data/index.json が空です。`python3 fetch.py` を実行してください。")

RECS = []
for sid, base in idx.items():
    d = det.get(sid, {})
    areas = [a.strip() for a in (d.get("target_area_search") or base.get("target_area_search") or "").split("/") if a.strip()]
    kpref = [a for a in areas if a in PREF_NAMES]
    if not kpref: continue
    nationwide = len([a for a in areas if a.endswith(("県","府","都","道"))]) >= 40
    st_s, st_e = d.get("acceptance_start_datetime") or base.get("acceptance_start_datetime"), d.get("acceptance_end_datetime") or base.get("acceptance_end_datetime")
    ds, de = dateobj(st_s), dateobj(st_e)
    status = "closed"
    if de and de >= TODAY:
        status = "open" if (not ds or ds <= TODAY) else "soon"
    elif not de and ds and ds <= TODAY:
        status = "open"
    RECS.append({
        "id": sid,
        "title": (d.get("title") or base.get("title") or "").strip(),
        "catch": (d.get("subsidy_catch_phrase") or "").strip(),
        "detail": d.get("detail") or "",
        "purpose": d.get("use_purpose") or "",
        "industry": d.get("industry") or "",
        "emp": d.get("target_number_of_employees") or base.get("target_number_of_employees") or "",
        "rate": d.get("subsidy_rate") or "",
        "max": d.get("subsidy_max_limit") or base.get("subsidy_max_limit") or 0,
        "start": st_s, "end": st_e, "status": status,
        "prefs": kpref, "nationwide": nationwide,
        "inst": d.get("institution_name") or base.get("institution_name") or "",
        "url": d.get("front_subsidy_detail_page_url") or f"https://www.jgrants-portal.go.jp/subsidy/{sid}",
        "area_detail": d.get("target_area_detail") or "",
        "code": d.get("name") or base.get("name") or "",
        "multi": d.get("is_enable_multiple_request"),
        "dl": de,
    })

RECS.sort(key=lambda r: (0 if r["status"]=="open" else 1 if r["status"]=="soon" else 2,
                         r["dl"] or datetime.date(2099,1,1), -(r["max"] or 0)))

OPEN  = [r for r in RECS if r["status"]=="open"]
SOON  = [r for r in RECS if r["status"]=="soon"]
N_ALL, N_OPEN = len(RECS), len(OPEN)

# 分類
PURPOSES = collections.Counter()
for r in RECS:
    for p in [x.strip() for x in r["purpose"].split("/") if x.strip()]: PURPOSES[p]+=1
INDUSTRIES = collections.Counter()
for r in RECS:
    for p in [x.strip() for x in r["industry"].split("/") if x.strip()]: INDUSTRIES[p]+=1
EMPS = collections.Counter(r["emp"] for r in RECS if r["emp"])

PURPOSE_LIST = [p for p,_ in PURPOSES.most_common()]
INDUSTRY_LIST = [p for p,_ in INDUSTRIES.most_common()]
P_SLUG = {p: slug(p) for p in PURPOSE_LIST}
I_SLUG = {p: slug(p) for p in INDUSTRY_LIST}

# ---- 自治体サイトから収集した市区町村・県の独自制度 ----
MUNI = _load("municipal.json", [])
for _m in MUNI:
    _m["dl"] = None
    if _m.get("deadline"):
        _mm = re.match(r"令和(\d+|元)年(\d+)月(\d+)日", _m["deadline"])
        if _mm:
            _y = 2018 + (1 if _mm.group(1) == "元" else int(_mm.group(1)))
            try:
                _m["dl"] = datetime.date(_y, int(_mm.group(2)), int(_mm.group(3)))
            except ValueError:
                pass
    _m["status"] = "closed" if (_m["dl"] and _m["dl"] < TODAY) else "open"
MUNI = [m for m in MUNI if m["status"] == "open"]
MUNI.sort(key=lambda m: (m["dl"] or datetime.date(2099, 1, 1), -(m["max"] or 0)))
MUNI_BY_PREF = collections.defaultdict(list)
MUNI_BY_CITY = collections.defaultdict(list)
for _m in MUNI:
    MUNI_BY_PREF[_m["pref"]].append(_m)
    MUNI_BY_CITY[(_m["pref"], _m["muni"])].append(_m)
N_MUNI = len(MUNI)
N_MUNI_CITY = len(MUNI_BY_CITY)
MUNI_ROMAJI = {
 "福岡県":"fukuoka-ken","福岡市":"fukuoka-shi","北九州市":"kitakyushu-shi","久留米市":"kurume-shi",
 "飯塚市":"iizuka-shi","大牟田市":"omuta-shi","糸島市":"itoshima-shi","宗像市":"munakata-shi",
 "佐賀県":"saga-ken","佐賀市":"saga-shi","唐津市":"karatsu-shi","鳥栖市":"tosu-shi",
 "長崎県":"nagasaki-ken","長崎市":"nagasaki-shi","佐世保市":"sasebo-shi","諫早市":"isahaya-shi",
 "熊本県":"kumamoto-ken","熊本市":"kumamoto-shi","八代市":"yatsushiro-shi","天草市":"amakusa-shi",
 "大分県":"oita-ken","大分市":"oita-shi","別府市":"beppu-shi","中津市":"nakatsu-shi",
 "宮崎県":"miyazaki-ken","宮崎市":"miyazaki-shi","都城市":"miyakonojo-shi","延岡市":"nobeoka-shi",
 "鹿児島県":"kagoshima-ken","鹿児島市":"kagoshima-shi","霧島市":"kirishima-shi","鹿屋市":"kanoya-shi",
 "沖縄県":"okinawa-ken","那覇市":"naha-shi","沖縄市":"okinawa-shi","うるま市":"uruma-shi",
 "浦添市":"urasoe-shi","宮古島市":"miyakojima-shi",
}
MUNI_SLUG = {k: MUNI_ROMAJI.get(k[1], slug(k[0] + k[1])) for k in MUNI_BY_CITY}

LOCAL = [r for r in RECS if not r["nationwide"]]
N_LOCAL = len(LOCAL)
def pref_recs(name): return [r for r in RECS if name in r["prefs"]]
def pref_local(name): return [r for r in LOCAL if name in r["prefs"]]
def purpose_recs(p): return [r for r in RECS if p in r["purpose"]]
def industry_recs(p): return [r for r in RECS if p in r["industry"]]

# ---------------------------------------------------------------- レイアウト
BASE = os.environ.get("KH_BASE", "").rstrip("/")   # 例: /kyushu-hojokin
if BASE and BASE_URL.endswith(BASE):       # KH_BASE_URL にパスまで入れられた場合の保険
    BASE_URL = BASE_URL[:-len(BASE)].rstrip("/")
def U(p=""):
    p = p.lstrip("/")
    return (BASE + "/" + p) if p else (BASE + "/")

MARK = ('<svg class="mark" viewBox="0 0 32 32" aria-hidden="true">'
        '<rect x="12" y="1" width="9" height="7" fill="#1A6DB5"/>'
        '<rect x="3" y="9.5" width="9" height="7" fill="#1A6DB5" opacity=".78"/>'
        '<rect x="13" y="9.5" width="9" height="7" fill="#0E9BC4"/>'
        '<rect x="23" y="9.5" width="7" height="7" fill="#1A6DB5" opacity=".55"/>'
        '<rect x="8" y="18" width="9" height="7" fill="#1A6DB5" opacity=".78"/>'
        '<rect x="18" y="18" width="7" height="7" fill="#1A6DB5" opacity=".55"/>'
        '<rect x="1" y="26.5" width="6" height="4.5" fill="#6FBCF0"/>'
        '<rect x="9" y="26.5" width="8" height="4.5" fill="#1A6DB5" opacity=".4"/></svg>')

NAV = [("補助金を探す","search/"),("県から探す","#pref"),("目的から探す","purpose/"),
       ("市区町村","muni/"),("対象者から","audience/"),("制度ガイド","guide/"),
       ("許認可","permit/"),("締切アラート","alerts/"),("AI相談","ai/"),("申請支援","experts/")]

def layout(title, desc, body, path="", extra_head="", extra_js="", data_js=False, schema="", with_ai=True):
    canon = (BASE_URL + U(path)) if BASE_URL else ""
    nav = "".join(f'<a href="{U(h) if not h.startswith("#") else (U()+h)}">{t}</a>' for t,h in NAV)
    top_prefs = "".join(f'<a href="{U("pref/"+s+"/")}">{n}</a>' for s,n,_,_ in PREFS)
    dj = '<script>window.KH_EAGER=' + ("1" if data_js else "0") + ';</script>'
    AI_SLOT = ai_widget() if with_ai else ""
    return f"""<!DOCTYPE html>
<html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{f'<link rel="canonical" href="{canon}">' if canon else ''}
<meta property="og:type" content="website"><meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">
{f'<meta property="og:url" content="{canon}">' if canon else ''}
<meta name="twitter:card" content="summary_large_image">
<meta property="og:image" content="{(BASE_URL or '') + U('assets/og.png')}">
<meta name="twitter:image" content="{(BASE_URL or '') + U('assets/og.png')}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=Noto+Serif+JP:wght@600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{U('assets/style.css')}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%231A6DB5'/%3E%3Crect x='13' y='11' width='8' height='7' fill='%230E9BC4'/%3E%3C/svg%3E">
{schema}{extra_head}
</head><body>
<div class="topbar"><div class="wrap">
  <span>国のオープンデータ（jGrants）を自動収集／最終更新 {TODAY_JP}</span>
  <nav>{top_prefs}</nav>
</div></div>
<header class="site"><div class="wrap">
  <a class="brand" href="{U()}">{MARK}<span><b>{SITE_NAME}</b><small>KYUSHU &amp; OKINAWA GRANTS</small></span></a>
  <nav class="main">{nav}</nav>
  <a class="btn sm" href="{U('search/')}">制度を検索する</a>
  <button class="burger" aria-label="メニュー">MENU</button>
</div></header>
{body}
<footer class="site"><div class="wrap">
  <div class="cols">
    <div>
      <div class="fb">{SITE_NAME}</div>
      <p style="margin:0;font-size:13px;line-height:1.95;opacity:.72">九州・沖縄8県の事業者が使える補助金・助成金を、国のオープンデータから集約。<br>掲載 {N_ALL:,} 件／受付中 {N_OPEN:,} 件（{TODAY_JP}時点）</p>
    </div>
    <div><h4>探す</h4><ul>
      <li><a href="{U('search/')}">全制度を検索</a></li>
      <li><a href="{U('ai/')}">補助金AI相談</a></li>
      <li><a href="{U('alerts/')}">締切アラート</a></li>
      <li><a href="{U('deadline/')}">締切カレンダー</a></li>
      <li><a href="{U('purpose/')}">目的から探す</a></li>
      <li><a href="{U('industry/')}">業種から探す</a></li>
      <li><a href="{U('audience/')}">対象者から探す</a></li>
      <li><a href="{U('muni/')}">市区町村の独自制度</a></li>
    </ul></div>
    <div><h4>県から探す</h4><ul>{''.join(f'<li><a href="{U("pref/"+s+"/")}">{n}の補助金</a></li>' for s,n,_,_ in PREFS[:4])}
      {''.join(f'<li><a href="{U("pref/"+s+"/")}">{n}の補助金</a></li>' for s,n,_,_ in PREFS[4:])}</ul></div>
    <div><h4>サイト情報</h4><ul>
      <li><a href="{U('guide/')}">制度ガイド</a></li>
      <li><a href="{U('permit/')}">許認可・届出ガイド</a></li>
      <li><a href="{U('experts/')}">申請支援（完全成果報酬）</a></li>
      <li><a href="{U('about/')}">運営について</a></li>
      <li><a href="{U('contact/')}">お問い合わせ</a></li>
      <li><a href="{U('privacy/')}">プライバシーポリシー</a></li>
      <li><a href="{U('terms/')}">利用規約</a></li>
    </ul></div>
  </div>
  <div class="cp">
    <span>© {TODAY.year} {SITE_NAME}</span>
    <span>出典：経済産業省 jGrants 補助金電子申請システム 公開API（デジタル庁）</span>
  </div>
</div></footer>
{AI_SLOT}
<script>window.KH_BASE="{BASE}";window.KH_DATA_URL="{U('assets/data.json')}";</script>
{dj}
<script src="{U('assets/app.js')}"></script>{extra_js}
</body></html>"""

def write(path, content):
    fp = os.path.join(OUT, path.lstrip("/"))
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    open(fp,"w",encoding="utf-8").write(content)

# ---------------------------------------------------------------- 部品
def badge(r):
    if r["status"]=="open":
        if r["dl"] and (r["dl"]-TODAY).days <= 30:
            return f'<span class="tag soon">締切まで{(r["dl"]-TODAY).days}日</span>'
        return '<span class="tag open">受付中</span>'
    if r["status"]=="soon": return '<span class="tag soon">受付予定</span>'
    return '<span class="tag closed">受付終了</span>'

def row(r, i):
    metas = badge(r)
    if r["nationwide"]:
        metas += '<span class="tag">全国対象</span>'
    else:
        metas += "".join(f'<span class="tag pref">{p}</span>' for p in r["prefs"][:4])
    fp = (r["purpose"].split("/")[0] or "").strip()
    if fp: metas += f'<span class="tag">{esc(fp)}</span>'
    dl = ""
    if r["end"]:
        left = (r["dl"] - TODAY).days if r["dl"] else None
        tail = f' <b>あと{left}日</b>' if (left is not None and 0 <= left <= 60) else ""
        dl = f'<div class="dl">締切 {jd(r["end"])}{tail}</div>'
    rt = f'<div class="rt">補助率 {esc(r["rate"])}</div>' if r["rate"] else ""
    return (f'<a class="row" href="{U("subsidy/"+r["id"]+"/")}">'
            f'<div class="no">{i:03d}</div>'
            f'<div><h3>{esc(r["title"])}</h3><div class="meta">{metas}</div></div>'
            f'<div class="amt"><small>補助上限</small>{yen(r["max"])}{rt}{dl}</div></a>')

def rows(rs, start=1):
    if not rs: return '<div class="empty">該当する制度は見つかりませんでした。</div>'
    return '<div class="rows">' + "".join(row(r,i) for i,r in enumerate(rs,start)) + '</div>'

def sec_h(en, h2, p="", more=None):
    m = f'<a class="more" href="{more[1]}">{more[0]} →</a>' if more else ""
    return (f'<div class="sec-h"><div><span class="en">{en}</span><h2>{h2}</h2>'
            f'{f"<p>{p}</p>" if p else ""}</div>{m}</div>')

SEIKA = f"""<section class="seika"><div class="wrap">
  <div class="badge-row">
    <span class="bg1"><i></i>着手金・相談料 0円</span>
    <span class="bg2">SUCCESS FEE ONLY</span>
  </div>
  <h2>採択されなければ、<br><em>1円もいただきません。</em></h2>
  <p class="lead">九州・沖縄の補助金申請を、<b>完全成果報酬</b>でお引き受けします。
  制度選びから事業計画の作成、採択後の実績報告まで伴走して、
  <b>採択が決まってはじめて</b>費用が発生します。落ちたときの持ち出しはゼロです。</p>
  <div class="seika-grid">
    <div><div class="n">0<small>円</small></div>
      <div class="k">着手金・相談料<br>制度選びと要件確認まで無料です</div></div>
    <div><div class="n">0<small>円</small></div>
      <div class="k">不採択だった場合<br>報酬は一切発生しません</div></div>
    <div><div class="n">成功報酬<small>のみ</small></div>
      <div class="k">採択が決まってからのお支払い<br>料率は着手前に書面で提示します</div></div>
  </div>
  <div class="cta-row">
    <a class="btn" href="{U('contact/')}">無料で相談する</a>
    <a class="btn ghost" href="{U('experts/')}">支援の中身を見る</a>
  </div>
  <p class="fine">※ 補助金は後払いのため、採択後も設備代の立替が必要です。つなぎ資金のご相談も承ります。<br>
  ※ 一部の制度や、申請期限が極端に迫っている案件はお引き受けできない場合があります。</p>
</div></section>"""

CTA = f"""<div class="cta"><div class="wrap narrow">
<h2>制度は見つかった。次は「通る申請書」をつくる番。</h2>
<p>九州・沖縄の行政書士・中小企業診断士・社労士・税理士と連携し、要件確認から事業計画書の作成・実績報告までを支援します。<strong style="color:#fff">着手金0円の完全成果報酬</strong>なので、まずは無料の相談枠から。</p>
<div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap">
<a class="btn" href="{U('contact/')}">無料で相談する</a>
<a class="btn ghost" href="{U('experts/')}">完全成果報酬の中身を見る</a>
</div></div></div>"""

# ---------------------------------------------------------------- トップページ
def build_index():
    near = sorted([r for r in OPEN if r["dl"]], key=lambda r: r["dl"])[:8]
    big  = sorted(OPEN, key=lambda r: -(r["max"] or 0))[:6]
    purpose_chips = cards([(U("purpose/"+P_SLUG[p]+"/"), pur_icon(p), p.replace("したい","").replace("を行いたい","").replace("がほしい","").replace("を改善","改善"), PURPOSES[p]) for p in PURPOSE_LIST[:12]])
    industry_chips = cards([(U("industry/"+I_SLUG[p]+"/"), ind_icon(p), p.split("、")[0].replace("業（他に分類されないもの）","業"), INDUSTRIES[p]) for p in INDUSTRY_LIST[:12]])
    audience_chips = cards([(U("audience/"+a[0]+"/"), a[3], a[1], len([r for r in RECS if a[5](r)])) for a in AUDIENCES], "c4")
    permit_chips = cards([(U("permit/"+x[0]+"/"), x[3], x[1], len(x[5])) for x in PERMITS], "c4")
    prefcards = "".join(
        f'<a href="{U("pref/"+s+"/")}">{pref_thumb(s)}'
        f'<div><div class="pn">{n}</div><div class="pr">{en}</div>'
        f'<div class="pnum">受付中 {len([r for r in pref_recs(n) if r["status"]=="open"])}<em>件</em>'
        f'　/　掲載 {len(pref_recs(n))}<em>件</em></div></div>'
        f'<div class="pd">{d}</div></a>'
        for s,n,en,d in PREFS)

    muni_cards = cards([(U("muni/"+MUNI_SLUG[k]+"/"), "town", k[1], len(v))
                        for k, v in sorted(MUNI_BY_CITY.items(), key=lambda kv: -len(kv[1]))[:12]], "c4")
    MUNI_SECTION = ("" if not MUNI else
        '<section><div class="wrap">'
        + sec_h("MUNICIPAL", "市区町村・県の独自制度",
                f"国のオープンデータには載らない、自治体が単独で実施している支援です。"
                f"{N_MUNI_CITY}自治体から{N_MUNI:,}件を公式サイトより収集しました。",
                ("すべて見る", U("muni/")))
        + muni_cards + '</div></section>')

    sd_pref = "".join(f'<button data-v="{n}">{n[:-1]}</button>' for _,n,_,_ in PREFS)
    sd_purpose = "".join(f'<button data-v="{esc(p)}">{esc(p.replace("したい","").replace("を行いたい","").replace("がほしい",""))}</button>' for p in PURPOSE_LIST[:8])
    sd_size = "".join(f'<button data-v="{e}">{e}</button>' for e in ["5名以下","20名以下","50名以下","100名以下","300名以下"])

    guides_html = "".join(
        f'<a href="{U("guide/"+g["slug"]+"/")}"><article>{guide_eye(i, i)}<div class="gb">'
        f'<div class="gk">{g["kicker"]}</div>'
        f'<h3>{esc(g["title"])}</h3><p>{esc(g["lead"])}</p></div></article></a>'
        for i, g in enumerate(GUIDES[:6]))

    body = f"""
<div class="hero">{HERO_ART}<div class="wrap">
  <div>
    <span class="hero-badge"><i></i>申請支援は着手金0円・完全成果報酬</span>
    <p class="eyebrow">KYUSHU &amp; OKINAWA / 8 PREFECTURES</p>
    <h1 class="hero-t"><span class="sm">福岡・佐賀・長崎・熊本・大分・宮崎・鹿児島・沖縄</span>
      九州の会社が使える<br>補助金だけを、<span style="white-space:nowrap"><span class="u">まとめて</span>。</span></h1>
    <p class="lead">全国版の検索サイトは情報が多すぎて、自社に関係のない制度ばかり出てきます。{SITE_NAME}は九州・沖縄8県を対象とする制度だけを国のオープンデータから抽出し、受付中かどうか・いくらもらえるか・いつ締め切るかを最初の一画面で示します。</p>
    <div class="hero-cta">
      <a class="btn" href="{U('search/')}">{N_OPEN}件の受付中制度を見る</a>
      <a class="btn ghost" href="{U()}#shindan">30秒で自社向けを絞り込む</a>
    </div>
  </div>
  <div>{kmap()}</div>
</div></div>

<div class="ledger"><div class="wrap">
  <div><div class="n">{N_ALL:,}<em>件</em></div><div class="k">九州・沖縄が対象の制度</div></div>
  <div><div class="n">{N_OPEN:,}<em>件</em></div><div class="k">いま受付中</div></div>
  <div><div class="n">{N_LOCAL:,}<em>件</em></div><div class="k">九州・沖縄に限定された制度</div></div>
  <div><div class="n">{yen(max([r['max'] for r in OPEN] or [0]))}</div><div class="k">受付中の最大補助額</div></div>
</div></div>

{SEIKA}

<section id="shindan" class="shindan"><div class="wrap">
  {sec_h("30 SECONDS","3つ選ぶだけ。自社が使える制度を絞り込む","県・目的・従業員規模を選ぶと、受付中の制度のなかから条件に合うものだけを表示します。メールアドレスの登録は不要です。")}
  <div class="q"><label>1 / 事業所のある県</label><div class="opts" data-key="pref">{sd_pref}</div></div>
  <div class="q"><label>2 / やりたいこと</label><div class="opts" data-key="purpose">{sd_purpose}</div></div>
  <div class="q"><label>3 / 従業員規模</label><div class="opts" data-key="size">{sd_size}</div></div>
  <div id="sd-out"></div>
</div></section>

<section><div class="wrap">
  <div class="sec-h"><div><span class="en">JUST ADDED</span>
    <h2>新着の補助金・助成金</h2>
    <p>公募が始まったばかりの制度です。締切までの期間が長いうちに準備を始めるほど、通る確率は上がります。</p></div>
    {car_nav()}</div>
  {carousel(newest(14))}
  <div style="padding-top:14px"><a class="more" href="{U('alerts/')}">新着をカレンダー・RSSで受け取る →</a></div>
</div></section>

<section class="alt"><div class="wrap">
  {sec_h("CLOSING SOON","締切が近い、受付中の制度","締切日が早い順。申請書の準備には通常2〜4週間かかります。",("締切アラートを設定する",U("alerts/")))}
  {rows(near)}
</div></section>

<section id="pref"><div class="wrap">
  {sec_h("BY PREFECTURE","県から補助金・助成金を探す","国・独立行政法人・県が公募する制度のうち、その県の事業者が対象になるものを集約しています。")}
  <div class="prefgrid">{prefcards}</div>
</div></section>

<section class="alt" id="purpose"><div class="wrap">
  {sec_h("BY PURPOSE","目的から探す","「設備を入れたい」「人を育てたい」など、やりたいことから逆引きします。",("すべて見る",U("purpose/")))}
  <div class="chips">{purpose_chips}</div>
</div></section>

<section id="industry"><div class="wrap">
  {sec_h("BY INDUSTRY","業種から探す","日本標準産業分類ベース。自社の業種が対象に含まれる制度だけを表示します。",("すべて見る",U("industry/")))}
  <div class="chips">{industry_chips}</div>
</div></section>

{MUNI_SECTION}
<section class="alt"><div class="wrap">
  {sec_h("BY AUDIENCE","対象者から探す","自社の形態から、対象になりうる制度を絞り込みます。",("すべて見る",U("audience/")))}
  {audience_chips}
</div></section>

<section><div class="wrap">
  {sec_h("PERMITS","許認可・届出ガイド","補助金の前に、まず事業を始める許可が要ります。業種別にまとめました。",("すべて見る",U("permit/")))}
  {permit_chips}
</div></section>

<section class="alt"><div class="wrap">
  {sec_h("MAX AMOUNT","補助額の大きい、受付中の制度","上限額が大きい順。自己負担と事務負担も同時に大きくなる点には注意してください。")}
  {rows(big)}
</div></section>

<section><div class="wrap">
  {sec_h("GUIDES","制度ガイド","九州・沖縄の事業者がつまずきやすい論点を中心に解説します。",("すべてのガイドを見る",U("guide/")))}
  <div class="guides">{guides_html}</div>
</div></section>

<section class="alt"><div class="wrap">
  {sec_h("EXPERTS","九州・沖縄の専門家が、申請まで伴走します","採択の可否を分けるのは制度選びより事業計画の書き方です。地場の士業と連携し、着手金0円の完全成果報酬で支援しています。",("申請支援を見る",U("experts/")))}
  <div class="experts">{EXPERT_TILES}</div>
</div></section>
{CTA}
"""
    schema = ('<script type="application/ld+json">' + json.dumps({
        "@context":"https://schema.org","@type":"WebSite","name":SITE_NAME,
        "description":SITE_DESC,"inLanguage":"ja",
        **({"url":BASE_URL+U()} if BASE_URL else {})
    }, ensure_ascii=False) + '</script>')
    write("index.html", layout(
        f"九州・沖縄の補助金／助成金を探す【{TODAY.year}年最新・{N_OPEN}件受付中】｜{SITE_NAME}",
        SITE_DESC + f"現在{N_OPEN}件が受付中（{TODAY_JP}時点）。申請支援は着手金0円の完全成果報酬。",
        body, "", data_js=True, schema=schema))

# ---------------------------------------------------------------- 専門家タイル
EXPERT_ROLES = [("行政書士","福岡県"),("中小企業診断士","福岡県"),("社会保険労務士","福岡県"),("税理士","福岡県"),
                ("行政書士","熊本県"),("中小企業診断士","熊本県"),("社会保険労務士","大分県"),("税理士","佐賀県"),
                ("行政書士","長崎県"),("中小企業診断士","宮崎県"),("社会保険労務士","鹿児島県"),("税理士","沖縄県")]
EXPERT_TILES = "".join(f'<div><div class="r">{r}</div><div class="a">{a}</div></div>' for r,a in EXPERT_ROLES)

# ---------------------------------------------------------------- 制度ガイド
GUIDES = [
 {"slug":"jizokuka","kicker":"小規模事業者向け","title":"小規模事業者持続化補助金｜九州の小さな会社が最初に取りに行く一本",
  "lead":"商工会・商工会議所の窓口を通して出す、販路開拓のための補助金。チラシ・ホームページ・店舗改装・展示会出展などが対象になります。",
  "body":"""
<h2>どんな制度か</h2>
<p>従業員数が少ない事業者（商業・サービス業は5人以下、製造業その他は20人以下が目安）が、販路を広げるために使った経費の一部を国が補助する制度です。九州・沖縄では飲食、美容、小売、建設の一人親方まで幅広く使われています。</p>
<h2>九州の事業者がつまずく3点</h2>
<h3>1. 窓口が「商工会」か「商工会議所」かで書式が違う</h3>
<p>市部は商工会議所、町村部は商工会が窓口になるのが一般的です。福岡市・北九州市・熊本市・鹿児島市・那覇市などは商工会議所、周辺町村は商工会。事業支援計画書（様式4）は窓口が発行するもので、これがないと申請できません。締切直前は窓口が混み合うため、<strong>公募締切の2週間前には窓口に相談を入れる</strong>のが実務上の鉄則です。</p>
<h3>2. 「販路開拓」に紐づかない経費は落ちる</h3>
<p>単なる設備更新や、既存顧客向けの経費は対象になりにくい制度です。「誰に・どう届けて・売上がいくら増えるのか」を数字でつなげた計画にする必要があります。</p>
<h3>3. 採択後の実績報告で差し戻される</h3>
<p>補助金は後払いです。発注書・契約書・納品書・請求書・振込控の5点セットが揃わないと精算できません。着手前に相見積を取り、現金払いを避けてください。</p>
<h2>関連する制度を探す</h2>
<p>本サイトの検索では「販路拡大」目的で絞り込むと、持続化補助金以外の県独自の販路支援もあわせて確認できます。</p>
<h2>出典</h2>
<p>全国商工会連合会・日本商工会議所の各公募ページ、および中小企業庁の補助事業ページ。公募回ごとに補助上限・補助率・締切が変わるため、申請前に必ず公式の公募要領で最新の条件をご確認ください。</p>
"""},
 {"slug":"monodukuri","kicker":"設備投資","title":"ものづくり補助金｜熊本の半導体集積で変わった、九州の設備投資支援",
  "lead":"製造業だけの制度ではありません。革新的なサービス開発や生産プロセス改善のための設備投資が対象で、補助上限は枠によって数千万円規模になります。",
  "body":"""
<h2>製造業以外も対象になる</h2>
<p>名称から製造業限定と誤解されがちですが、宿泊・飲食・運輸・卸売・サービス業も申請できます。要件は「革新的な製品・サービス開発」または「生産プロセス・サービス提供方法の改善」であることです。</p>
<h2>九州で申請が増えている背景</h2>
<p>熊本県菊陽町を中心とする半導体関連の集積により、九州全域で部品加工・搬送・クリーンルーム施工・検査装置まわりの受注が動いています。二次・三次のサプライヤーが設備能力を上げる必要に迫られ、設備投資型の補助金へのニーズが高まりました。大分・福岡の自動車関連、北九州の素材産業でも同様の動きがあります。</p>
<h2>申請で見られていること</h2>
<table><tr><th>審査の論点</th><th>実務での対応</th></tr>
<tr><td>その設備でなければならない理由</td><td>現行設備の能力・歩留まり・段取り時間を数値で示し、導入後の差分を出す</td></tr>
<tr><td>市場があるか</td><td>引き合い・内示・取引先の意向書など、外部の裏付けを添える</td></tr>
<tr><td>実行できる体制か</td><td>人員配置、資金調達（自己資金＋借入）の見通しを金融機関と揃えておく</td></tr>
<tr><td>付加価値額・給与支給総額の目標</td><td>申請時に事業計画で約束し、採択後は毎年報告する</td></tr></table>
<h2>資金繰りの注意</h2>
<p>補助金は原則として後払いです。補助率が2/3でも、設備代金は一度全額を支払う必要があります。九州の地銀・信金はつなぎ資金に慣れていますので、採択前の段階で相談しておくと安全です。</p>
<h2>出典</h2>
<p>中小企業庁および全国中小企業団体中央会のものづくり補助金公募ページ。公募回ごとに申請枠・補助上限・補助率・加点要件が改定されます。申請前に必ず最新の公募要領をご確認ください。</p>
"""},
 {"slug":"it-dounyu","kicker":"IT・DX","title":"IT導入補助金｜レジ・会計・予約システムを入れるときの定番",
  "lead":"IT導入支援事業者として登録された業者が扱うツールに限って使える制度。自分で探した好きなソフトが対象になるわけではない点が最大の落とし穴です。",
  "body":"""
<h2>仕組みを先に理解する</h2>
<p>この制度は「事業者が申請する」のではなく、<strong>IT導入支援事業者（ベンダー）と共同で申請する</strong>形を取ります。したがって、①対象ツールを扱う登録ベンダーを探す → ②相談する → ③一緒に申請する、という順番になります。先にツールを決めてから補助金を探すと、そのツールが登録されておらず使えない、という事態が起きます。</p>
<h2>九州の実務で多い使い方</h2>
<ul>
<li>飲食・宿泊：予約管理とPOSレジの入替（インバウンド対応の多言語化とあわせて）</li>
<li>建設：原価管理・工事台帳ソフトの導入</li>
<li>運輸：デジタコ・配車システム</li>
<li>士業・小売：会計ソフトとインボイス・電子帳簿保存法への対応</li>
</ul>
<h2>補助対象になりにくいもの</h2>
<p>パソコン・タブレット等のハードウェアは、対象になる枠と対象外の枠があります。ホームページ制作は、単なる会社案内サイトだと対象外になることが多く、ECや予約機能を伴う場合に限られるのが通例です。汎用的な事務機器、既存ソフトの更新料のみ、といった支出も外れます。</p>
<h2>申請前チェック</h2>
<table><tr><th>項目</th><th>内容</th></tr>
<tr><td>gBizIDプライム</td><td>取得に日数がかかります。最優先で申請してください</td></tr>
<tr><td>SECURITY ACTION</td><td>自己宣言が要件。無料で当日中に可能</td></tr>
<tr><td>みらデジ経営チェック</td><td>公募回により必須。所要15分程度</td></tr>
<tr><td>対象ツールの登録確認</td><td>公式サイトのツール検索で、契約予定のツールが登録されているか確認</td></tr></table>
<h2>出典</h2>
<p>独立行政法人中小企業基盤整備機構・IT導入補助金事務局の公式サイト。補助率・補助額・枠の構成は年度ごとに改定されます。</p>
"""},
 {"slug":"gyomu-kaizen","kicker":"賃上げ","title":"業務改善助成金｜最低賃金を上げると、設備投資費が戻ってくる",
  "lead":"事業場内でいちばん低い時給を一定額以上引き上げ、あわせて生産性向上のための設備投資をした場合に、その設備費用の大部分が助成される制度です。",
  "body":"""
<h2>補助金ではなく「助成金」</h2>
<p>所管は厚生労働省（都道府県労働局）で、経済産業省系の補助金とは別系統です。要件を満たせば原則として支給される性質のため、審査で落ちる競争型の補助金より見通しが立てやすいのが特徴です。</p>
<h2>九州で使いやすい理由</h2>
<p>九州・沖縄は地域別最低賃金が全国平均を下回る県が多く、事業場内最低賃金が対象ラインに収まりやすい地域です。そのため、同じ設備投資でも九州の事業者のほうがこの制度の射程に入りやすいという実務上の傾向があります。</p>
<h2>流れ</h2>
<ol>
<li>現在の事業場内最低賃金を確認する（就業規則・賃金台帳）</li>
<li>引き上げ額のコースを選ぶ</li>
<li><strong>交付申請を出し、交付決定を受けてから</strong>設備を発注する（先に買うと対象外）</li>
<li>賃金を引き上げ、設備を導入する</li>
<li>実績報告 → 支給</li>
</ol>
<div class="note">最大の事故は「交付決定前の発注」です。見積書を取るのは構いませんが、発注書・契約はかならず交付決定通知の日付より後にしてください。</div>
<h2>対象になりやすい設備の例</h2>
<p>POSレジ、自動発注システム、リフト・昇降機、洗浄機、パッケージング機、CAD、配送ルート最適化ソフトなど。「生産性が上がること」を説明できるかが分かれ目です。単なる買い替えは通りません。</p>
<h2>出典</h2>
<p>厚生労働省「業務改善助成金」ページおよび各県労働局。年度ごとに受付期間・コース構成・上限額が変わります。申請前に管轄の労働局へご確認ください。</p>
"""},
 {"slug":"career-up","kicker":"雇用・人材","title":"キャリアアップ助成金｜人手不足の九州で、パートを正社員にするとき",
  "lead":"有期雇用の従業員を正社員に転換した場合などに支給される助成金。就業規則の整備とキャリアアップ計画の事前提出が前提になります。",
  "body":"""
<h2>先に出すものがある</h2>
<p>この助成金でいちばん多い失敗は、<strong>正社員転換をしてから相談に来ること</strong>です。キャリアアップ計画書を転換日より前に労働局へ提出しておく必要があり、後追いでは支給されません。</p>
<h2>九州の現場で効く場面</h2>
<ul>
<li>宿泊・飲食：繁忙期のパートを通年雇用に切り替え、離職率を下げる</li>
<li>介護・医療：有資格者の定着のために処遇を上げる</li>
<li>製造：熊本・大分の半導体／自動車関連で、派遣・有期から直接雇用へ切り替える</li>
</ul>
<h2>前提として必要なもの</h2>
<table><tr><th>要件</th><th>実務</th></tr>
<tr><td>就業規則の整備</td><td>転換制度の規定が必要。10人未満でも作成し労働基準監督署へ届出</td></tr>
<tr><td>雇用保険適用事業所</td><td>適用事業所であること</td></tr>
<tr><td>賃金の引き上げ</td><td>転換前後で所定の率以上の増額が必要</td></tr>
<tr><td>支給申請の期限</td><td>転換後、一定期間の賃金支払いを経てから期限内に申請</td></tr></table>
<h2>社労士に頼むべきか</h2>
<p>就業規則と賃金台帳の整合を取る作業が中心になるため、顧問社労士がいるなら任せたほうが早く、確実です。いない場合も、本サイトの提携士業から地域の社労士に相談できます。</p>
<h2>出典</h2>
<p>厚生労働省「キャリアアップ助成金」ページ。コース構成・支給額・要件は年度ごとに改定されます。最新の支給要領で必ずご確認ください。</p>
"""},
 {"slug":"okinawa","kicker":"沖縄限定","title":"沖縄の事業者だけが使える支援の枠組み｜振興特措法という別ルート",
  "lead":"沖縄には、沖縄振興特別措置法にもとづく独自の制度系統があります。全国共通の補助金と並行して、この別ルートを必ず確認してください。",
  "body":"""
<h2>本土の制度と二重に見る</h2>
<p>沖縄県の事業者は、全国共通の補助金（ものづくり、持続化、IT導入など）に加えて、内閣府沖縄総合事務局および沖縄県が所管する沖縄独自の支援を利用できる場合があります。同じ投資計画でも、どちらのルートで出すかで補助率と上限が変わることがあります。</p>
<h2>沖縄特有の論点</h2>
<h3>離島</h3>
<p>宮古・八重山などの離島は輸送コストと人材確保が構造的な制約です。輸送費や離島の事業継続を対象にした制度が別に用意されることがあります。</p>
<h3>観光の季節変動</h3>
<p>観光需要の波が大きいため、雇用関係の助成金（有期から無期への転換、休業時の教育訓練など）との相性が良い一方、通年の売上計画の説得力が問われます。</p>
<h3>IT・情報通信</h3>
<p>沖縄はIT産業の誘致を長く政策の柱にしてきました。情報通信関連の拠点設置・人材育成の支援は、他県より枠が厚い傾向があります。</p>
<h2>どこを見るか</h2>
<ul>
<li>内閣府 沖縄総合事務局（経済産業部・農林水産部）</li>
<li>沖縄県 商工労働部の各公募</li>
<li>公益財団法人 沖縄県産業振興公社</li>
<li>市町村（那覇市・浦添市・沖縄市など）の独自支援</li>
</ul>
<div class="note">本サイトが収集している国のオープンデータ（jGrants）には、市町村単独の制度は含まれないことがあります。沖縄で申請を検討する際は、上記の窓口も併せてご確認ください。</div>
<h2>出典</h2>
<p>沖縄振興特別措置法および内閣府沖縄総合事務局・沖縄県の各公募ページ。</p>
"""},
 {"slug":"shinsa","kicker":"申請実務","title":"採択される事業計画書は何が違うのか｜審査員が最初に見る3行",
  "lead":"制度選びより、書き方で差がつきます。落ちる計画書に共通する型と、直し方をまとめました。",
  "body":"""
<h2>審査は加点方式ではなく、減点と消去法</h2>
<p>審査員は限られた時間で大量の申請書を読みます。冒頭で「何をする事業か」が掴めない書類は、それだけで後段を精読されません。1枚目の最初の3行に、①誰の②どんな困りごとを③どう解決して売上をいくら作るのか、を数字入りで書いてください。</p>
<h2>落ちる計画書の典型</h2>
<table><tr><th>よくある書き方</th><th>直し方</th></tr>
<tr><td>「地域に貢献します」</td><td>貢献の中身を数字に。雇用○名、地場調達比率○%、取引先○社</td></tr>
<tr><td>「最新の設備を導入します」</td><td>現状の能力（時間あたり○個、歩留まり○%）と導入後の差分を出す</td></tr>
<tr><td>「売上が伸びる見込みです」</td><td>単価×客数×回数に分解し、その各要素の根拠を示す</td></tr>
<tr><td>「他社にはない強みがあります」</td><td>競合を3社名指しで比較表にする</td></tr></table>
<h2>九州の事業者が持っている、書き漏らしやすい強み</h2>
<ul>
<li><strong>アジアとの距離</strong>：福岡・那覇からのアクセスは、販路拡大や輸出の計画で説得力を持ちます</li>
<li><strong>一次産業の原料調達</strong>：宮崎・鹿児島・熊本の畜産／農産の地場調達は、原価と品質の両面で根拠になります</li>
<li><strong>観光の集客導線</strong>：既存の観光流動に自社をどう接続するかは、販路計画として評価されます</li>
<li><strong>人材の定着</strong>：都市圏より離職率が低い点は、体制の実現可能性を裏づけます</li>
</ul>
<h2>提出前の最終チェック</h2>
<ol>
<li>公募要領の審査項目と、自分の見出しが対応しているか</li>
<li>数字の出どころ（決算書・統計・見積書）がすべて明示されているか</li>
<li>写真・図表が1ページに1つ以上入っているか</li>
<li>加点要件（賃上げ表明、経営革新計画、事業継続力強化計画など）を取りこぼしていないか</li>
<li>gBizIDプライムの取得が間に合うか</li>
</ol>
<h2>出典</h2>
<p>各制度の公募要領に記載された審査項目。具体の配点や加点要件は制度・公募回ごとに異なります。</p>
"""},
 {"slug":"gbizid","kicker":"事前準備","title":"gBizIDプライムの取り方｜これがないと、そもそも出せない",
  "lead":"国の補助金の電子申請には、原則としてgBizIDプライムが必要です。発行までに日数がかかるため、制度を探すのと同時に着手してください。",
  "body":"""
<h2>3つの種類</h2>
<table><tr><th>種類</th><th>用途</th></tr>
<tr><td>gBizIDプライム</td><td>代表者本人のアカウント。補助金申請はこれが必要</td></tr>
<tr><td>gBizIDメンバー</td><td>プライムの下に作る従業員用</td></tr>
<tr><td>gBizIDエントリー</td><td>簡易版。補助金申請には使えないことが多い</td></tr></table>
<h2>必要なもの</h2>
<ul>
<li>法人：印鑑証明書（発行から3か月以内）と、登録印で押印した申請書</li>
<li>個人事業主：印鑑登録証明書と、登録印で押印した申請書</li>
<li>スマートフォン（SMS受信用）とメールアドレス</li>
</ul>
<h2>期間の目安</h2>
<p>書類郵送方式の場合、審査完了まで1〜2週間程度を見込んでください。マイナンバーカードを使ったオンライン申請なら短縮できます。<strong>公募締切の直前に着手すると間に合いません。</strong></p>
<div class="note">補助金の公募期間は1〜2か月程度が一般的です。制度を見つけてからgBizIDを取り始めると、それだけで期間の半分を消費します。まだ持っていない九州の事業者は、いま申請してください。</div>
<h2>出典</h2>
<p>デジタル庁 GビズID公式サイト。</p>
"""},
]
GUIDE_BY = {g["slug"]:g for g in GUIDES}

# ---------------------------------------------------------------- 詳細本文の掃除
def clean_rt(h):
    if not h: return ""
    h = re.sub(r"<(script|style|iframe|object|embed)[^>]*>.*?</\1>", "", h, flags=re.S|re.I)
    h = re.sub(r"\son\w+\s*=\s*\"[^\"]*\"", "", h, flags=re.I)
    h = re.sub(r"\son\w+\s*=\s*'[^']*'", "", h, flags=re.I)
    h = re.sub(r"\sstyle\s*=\s*\"[^\"]*\"", "", h, flags=re.I)
    h = re.sub(r"\sstyle\s*=\s*'[^']*'", "", h, flags=re.I)
    h = re.sub(r"<a ", '<a rel="nofollow noopener" target="_blank" ', h, flags=re.I)
    return h

def plain(h, n=150):
    t = re.sub(r"<[^>]+>", "", h or "")
    t = html.unescape(t).replace("　"," ")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:n]

# ---------------------------------------------------------------- 制度詳細
def build_subsidies():
    for r in RECS:
        pr = "".join(f'<a class="tag pref" style="margin-right:5px" href="{U("pref/"+PREF_BY_NAME[p][0]+"/")}">{p}</a>' for p in r["prefs"])
        pu = "".join(f'<a class="tag" style="margin-right:5px" href="{U("purpose/"+P_SLUG[x.strip()]+"/")}">{esc(x.strip())}</a>'
                     for x in r["purpose"].split("/") if x.strip() in P_SLUG)
        ind = "、".join(x.strip() for x in r["industry"].split("/") if x.strip()) or "指定なし"
        rel = [x for x in RECS if x["id"]!=r["id"] and set(x["prefs"])&set(r["prefs"]) and x["status"]!="closed"][:5]
        st_note = ""
        if r["status"]=="closed":
            st_note = '<div class="note"><strong>この公募は受付を終了しています。</strong>後継制度や次回公募が出る場合があります。同じ目的の受付中制度は下部の関連制度からご確認ください。</div>'
        elif r["status"]=="soon":
            st_note = f'<div class="note"><strong>受付開始前です（{jd_long(r["start"])}開始予定）。</strong>公募要領の公開を待って、必要書類とgBizIDの準備を進めてください。</div>'
        elif r["dl"] and (r["dl"]-TODAY).days <= 21:
            st_note = f'<div class="note"><strong>締切まで残り{(r["dl"]-TODAY).days}日です。</strong>申請には通常2〜4週間かかります。急ぐ場合は窓口・専門家へ早めにご相談ください。</div>'
        body = f"""
<div class="wrap narrow">
<div class="crumbs"><a href="{U()}">ホーム</a><span>/</span><a href="{U('search/')}">補助金を探す</a><span>/</span>{esc(r['title'][:34])}…</div>
<div class="detail-h">
  <div style="display:flex;gap:6px;flex-wrap:wrap">{badge(r)}{'<span class="tag">全国対象</span>' if r['nationwide'] else ''}{f'<span class="tag">{esc(r["code"])}</span>' if r['code'] else ''}</div>
  <h1>{esc(r['title'])}</h1>
  <div style="font-size:13px;color:var(--ink-55)">{('実施機関：'+esc(r['inst'])) if r['inst'] else ''}</div>
  <div style="margin-top:14px">{pr}</div>
</div>
{st_note}
<dl class="spec">
  <div><dt>補助上限額</dt><dd>{yen(r['max'])}</dd></div>
  <div><dt>補助率</dt><dd class="s">{esc(r['rate']) or '公募要領による'}</dd></div>
  <div><dt>受付開始</dt><dd class="s">{jd_long(r['start'])}</dd></div>
  <div><dt>受付締切</dt><dd class="s">{jd_long(r['end'])}</dd></div>
  <div><dt>従業員数の要件</dt><dd class="s">{esc(r['emp']) or '—'}</dd></div>
  <div><dt>複数回申請</dt><dd class="s">{'可' if r['multi'] else '不可・要確認'}</dd></div>
</dl>
<h2 style="font-family:var(--serif);font-size:21px;border-bottom:1px solid var(--rule);padding-bottom:12px;letter-spacing:.03em">制度の概要</h2>
<div class="body-rt">{clean_rt(r['detail']) or '<p>詳細は公式ページをご確認ください。</p>'}</div>

<h2 style="font-family:var(--serif);font-size:21px;border-bottom:1px solid var(--rule);padding-bottom:12px;margin-top:48px;letter-spacing:.03em">対象</h2>
<p style="font-size:14px;line-height:2"><strong>対象業種：</strong>{esc(ind)}<br>
<strong>対象地域：</strong>{'全国（九州・沖縄8県を含む）' if r['nationwide'] else '、'.join(r['prefs'])}{('　'+esc(r['area_detail'])) if r['area_detail'] else ''}</p>
<div style="margin:18px 0 6px">{pu}</div>

<div style="margin:44px 0;padding:26px;border:1px solid var(--rule);background:var(--paper-2)">
  <div style="font-size:11px;letter-spacing:.18em;font-weight:700;color:var(--ink-40);margin-bottom:12px">OFFICIAL</div>
  <p style="margin:0 0 16px;font-size:14px;color:var(--ink-70)">公募要領・様式・最新の締切は、かならず公式ページでご確認ください。本ページは国のオープンデータをもとに自動生成しています。</p>
  <a class="btn" href="{esc(r['url'])}" target="_blank" rel="nofollow noopener">jGrantsの公式ページを開く</a>
</div>

<h2 style="font-family:var(--serif);font-size:21px;border-bottom:1px solid var(--rule);padding-bottom:12px;letter-spacing:.03em">同じ地域の、受付中の制度</h2>
{rows(rel)}
</div>
{CTA}"""
        schema = '<script type="application/ld+json">' + json.dumps({
            "@context":"https://schema.org","@type":"GovernmentService","name":r["title"],
            "serviceType":"補助金・助成金","areaServed":[{"@type":"State","name":p} for p in r["prefs"]],
            "provider":{"@type":"GovernmentOrganization","name":r["inst"] or "日本国政府"},
        }, ensure_ascii=False) + '</script>'
        write(f"subsidy/{r['id']}/index.html", layout(
            f"{r['title']}｜{'、'.join(r['prefs'][:3])}の補助金｜{SITE_NAME}",
            f"{r['title']}の補助上限{yen(r['max'])}・補助率{r['rate'] or '要確認'}・締切{jd_long(r['end'])}。" + plain(r['detail'],80),
            body, f"subsidy/{r['id']}/", schema=schema))

# ---------------------------------------------------------------- 県ページ
def build_prefs():
    for s,n,en,d in PREFS:
        rs = pref_recs(n)
        op = [r for r in rs if r["status"]=="open"]
        local = [r for r in op if not r["nationwide"]]
        natl  = [r for r in op if r["nationwide"]]
        pc = collections.Counter()
        for r in rs:
            for p in [x.strip() for x in r["purpose"].split("/") if x.strip()]: pc[p]+=1
        chips = cards([(U("purpose/"+P_SLUG[p]+"/"+s+"/"), pur_icon(p), p.replace("したい","").replace("を行いたい","").replace("がほしい","").replace("を改善","改善"), c) for p,c in pc.most_common(8) if p in P_SLUG], "c4")
        others = "".join(f'<a class="tag pref" style="margin:0 6px 6px 0;padding:8px 14px;font-size:13px" href="{U("pref/"+s2+"/")}">{n2}</a>'
                         for s2,n2,_,_ in PREFS if s2!=s)
        mlist = MUNI_BY_PREF.get(n, [])
        muni_block = ("" if not mlist else
            '<section><div class="wrap">'
            + sec_h("MUNICIPAL", n + "内の自治体が独自に行っている支援",
                    f"国のオープンデータには載らない制度です。{n}の"
                    f"{len([1 for k in MUNI_BY_CITY if k[0]==n])}自治体から{len(mlist)}件を収集しました。",
                    ("市区町村の一覧", U("muni/")))
            + cards([(U("muni/"+MUNI_SLUG[k]+"/"), "town", k[1], len(v))
                     for k, v in MUNI_BY_CITY.items() if k[0] == n], "c4")
            + muni_rows(mlist[:12]) + MUNI_NOTE + '</div></section>')
        body = f"""
<div class="wrap">
<div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>県から探す<span>/</span>{n}</div>
</div>
<div class="hero">{HERO_ART}<div class="wrap">
 <div>
  <p class="eyebrow">{en} / {len(rs)} PROGRAMS</p>
  <h1 class="hero-t">{n}の<br><span class="u">補助金・助成金</span>一覧</h1>
  <p class="lead">{d}<br>{n}の事業者が対象になる制度を、国のオープンデータから{len(rs):,}件収集しました。うち{len(op)}件が現在受付中です（{TODAY_JP}時点）。</p>
  <div class="hero-cta"><a class="btn" href="{U('search/')}?pref={n}">{n}の制度を検索する</a></div>
 </div>
 <div>{kmap(s)}</div>
</div></div>
<div class="ledger"><div class="wrap">
 <div><div class="n">{len(rs):,}<em>件</em></div><div class="k">{n}が対象の制度</div></div>
 <div><div class="n">{len(op):,}<em>件</em></div><div class="k">いま受付中</div></div>
 <div><div class="n">{len(pref_local(n)):,}<em>件</em></div><div class="k">{n}を含む地域限定の制度</div></div>
 <div><div class="n">{yen(max([r['max'] for r in op] or [0]))}</div><div class="k">受付中の最大補助額</div></div>
</div></div>

<section><div class="wrap">
 {sec_h("LOCAL","{}に限定された、受付中の制度".format(n), "全国公募ではなく、地域が限定されている制度です。競争相手が少なく、通りやすい傾向があります。")}
 {rows(local[:20])}
</div></section>

<section class="alt"><div class="wrap">
 <div class="sec-h"><div><span class="en">JUST ADDED</span><h2>{n}の新着</h2>
   <p>公募が始まったばかりの制度です。</p></div>{car_nav()}</div>
 {carousel([r for r in newest(200) if n in r["prefs"]][:12], "car-"+s)}
 <div style="padding-top:12px"><a class="more" href="{U('alerts/')}">{n}の締切カレンダーを購読する →</a></div>
</div></section>

<section><div class="wrap">
 {sec_h("BY PURPOSE","{}で、目的から絞り込む".format(n))}
 {chips}
</div></section>

<section><div class="wrap">
 {sec_h("NATIONWIDE","{}の事業者も使える、全国公募の制度".format(n), "ものづくり補助金・持続化補助金など、全国どこからでも申請できる制度です。")}
 {rows(natl[:15])}
 <div style="padding-top:30px"><a class="more" href="{U('search/')}?pref={n}">{n}の全{len(rs):,}件を検索で見る →</a></div>
</div></section>

{muni_block}
<section class="alt"><div class="wrap">
 {sec_h("OTHER PREFECTURES","ほかの県を見る")}
 <div>{others}</div>
</div></section>
{CTA}"""
        write(f"pref/{s}/index.html", layout(
            f"{n}の補助金・助成金一覧【{TODAY.year}年最新・{len(op)}件受付中】｜{SITE_NAME}",
            f"{n}の事業者が使える補助金・助成金を{len(rs):,}件掲載。受付中{len(op)}件。{d}",
            body, f"pref/{s}/"))

# ---------------------------------------------------------------- 目的/業種
def build_taxonomy():
    chips = cards([(U("purpose/"+P_SLUG[p]+"/"), pur_icon(p), p.replace("したい","").replace("を行いたい","").replace("がほしい","").replace("を改善","改善"), PURPOSES[p]) for p in PURPOSE_LIST], "c4")
    write("purpose/index.html", layout(f"目的から補助金を探す｜{SITE_NAME}",
        "設備投資、人材育成、販路拡大など、やりたいことから九州・沖縄の補助金を逆引きします。",
        f'<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>目的から探す</div></div>'
        f'<section><div class="wrap">{sec_h("BY PURPOSE","目的から補助金・助成金を探す","やりたいことを選ぶと、九州・沖縄8県が対象の制度だけが表示されます。")}'
        f'{chips}</div></section>{CTA}', "purpose/"))
    for p in PURPOSE_LIST:
        rs = purpose_recs(p); op=[r for r in rs if r["status"]=="open"]
        pb = cards([(U("purpose/"+P_SLUG[p]+"/"+s2+"/"), "search", n, len([r for r in rs if n in r["prefs"]])) for s2,n,_,_ in PREFS], "c4")
        body = (f'<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>'
                f'<a href="{U("purpose/")}">目的から探す</a><span>/</span>{esc(p)}</div></div>'
                f'<section><div class="wrap">{sec_h("BY PURPOSE", esc(p)+"ときに使える補助金", f"九州・沖縄8県が対象の{len(rs):,}件から抽出。うち受付中{len(op)}件（{TODAY_JP}時点）。")}'
                f'{rows(op[:30] or rs[:20])}'
                f'<div style="padding-top:34px">{sec_h("BY PREFECTURE","県で絞り込む")}{pb}</div>'
                f'</div></section>{CTA}')
        write(f"purpose/{P_SLUG[p]}/index.html", layout(
            f"{p}｜九州・沖縄の補助金{len(rs)}件【受付中{len(op)}件】｜{SITE_NAME}",
            f"「{p}」に該当する九州・沖縄の補助金・助成金を{len(rs)}件掲載。受付中{len(op)}件。", body, f"purpose/{P_SLUG[p]}/"))

    ichips = cards([(U("industry/"+I_SLUG[p]+"/"), ind_icon(p), p.split("、")[0].replace("業（他に分類されないもの）","業"), INDUSTRIES[p]) for p in INDUSTRY_LIST], "c4")
    write("industry/index.html", layout(f"業種から補助金を探す｜{SITE_NAME}",
        "製造業・建設業・宿泊飲食・農林水産など、業種別に九州・沖縄の補助金を探せます。",
        f'<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>業種から探す</div></div>'
        f'<section><div class="wrap">{sec_h("BY INDUSTRY","業種から補助金・助成金を探す","日本標準産業分類にもとづく区分です。")}'
        f'{ichips}</div></section>{CTA}', "industry/"))
    for p in INDUSTRY_LIST:
        rs = industry_recs(p); op=[r for r in rs if r["status"]=="open"]
        pb = cards([(U("industry/"+I_SLUG[p]+"/"+s2+"/"), "search", n, len([r for r in rs if n in r["prefs"]])) for s2,n,_,_ in PREFS], "c4")
        body = (f'<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>'
                f'<a href="{U("industry/")}">業種から探す</a><span>/</span>{esc(p)}</div></div>'
                f'<section><div class="wrap">{sec_h("BY INDUSTRY", esc(p)+"が使える補助金", f"九州・沖縄8県が対象で、{p}を対象業種に含む制度は{len(rs):,}件。うち受付中{len(op)}件。")}'
                f'{rows(op[:30] or rs[:20])}'
                f'<div style="padding-top:34px">{sec_h("BY PREFECTURE","県で絞り込む")}{pb}</div>'
                f'</div></section>{CTA}')
        write(f"industry/{I_SLUG[p]}/index.html", layout(
            f"{p}の補助金・助成金【九州・沖縄／受付中{len(op)}件】｜{SITE_NAME}",
            f"{p}を対象とする九州・沖縄の補助金・助成金を{len(rs)}件掲載。受付中{len(op)}件。", body, f"industry/{I_SLUG[p]}/"))

# ---------------------------------------------------------------- 検索 / 締切
def build_search():
    o = lambda vs: "".join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in vs)
    body = f"""
<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>補助金を探す</div></div>
<section id="searchpage"><div class="wrap">
 {sec_h("SEARCH","九州・沖縄の補助金・助成金を検索する", f"掲載 {N_ALL:,} 件／受付中 {N_OPEN:,} 件（{TODAY_JP}時点・jGrants公開APIより自動収集）")}
 <div class="filters">
  <div class="fullw"><label>キーワード</label><input id="f-kw" type="search" placeholder="例：設備、観光、DX、人材" autocomplete="off"></div>
  <div><label>都道府県</label><select id="f-pref"><option value="">すべて</option>{o([n for _,n,_,_ in PREFS])}</select></div>
  <div><label>目的</label><select id="f-purpose"><option value="">すべて</option>{o(PURPOSE_LIST)}</select></div>
  <div><label>業種</label><select id="f-industry"><option value="">すべて</option>{o(INDUSTRY_LIST)}</select></div>
  <div><label>受付状況</label><select id="f-status"><option value="open">受付中のみ</option><option value="">すべて</option><option value="closed">受付終了</option></select></div>
  <div class="fullw"><label>並び順</label><select id="f-sort"><option value="deadline">締切が近い順</option><option value="amount">補助額が大きい順</option><option value="new">新着順</option></select></div>
 </div>
 <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px;font-size:14px;color:var(--ink-55)">
   <span>検索結果 <span id="res-count">—</span></span></div>
 <div id="res"></div><div class="pagenav" id="pgn"></div>
</div></section>{CTA}"""
    write("search/index.html", layout(f"九州・沖縄の補助金を検索【{N_ALL:,}件掲載】｜{SITE_NAME}",
        f"福岡・佐賀・長崎・熊本・大分・宮崎・鹿児島・沖縄の補助金・助成金を{N_ALL:,}件から検索。県・目的・業種・受付状況で絞り込めます。",
        body, "search/", data_js=True))

    up = sorted([r for r in OPEN if r["dl"]], key=lambda r: r["dl"])
    months = collections.OrderedDict()
    for r in up: months.setdefault(f"{r['dl'].year}年{r['dl'].month}月", []).append(r)
    secs = ""
    alt = False
    for m, rs in list(months.items())[:8]:
        cls = ' class="alt"' if alt else ''
        alt = not alt
        secs += '<section' + cls + '><div class="wrap">' + sec_h("DEADLINE", m + "に締め切る制度", str(len(rs)) + "件") + rows(rs) + '</div></section>'
    write("deadline/index.html", layout(f"締切カレンダー｜九州・沖縄の補助金｜{SITE_NAME}",
        "受付中の補助金を締切月ごとに整理。申請書の準備期間から逆算して、いま動くべき制度がわかります。",
        f'<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>締切カレンダー</div></div>'
        f'<section><div class="wrap">{sec_h("CALENDAR","締切カレンダー", f"受付中{len(up)}件を締切の早い順に月別で並べました。申請書の作成には通常2〜4週間かかります。")}</div></section>'
        + secs + CTA, "deadline/"))

# ---------------------------------------------------------------- ガイド
def build_guides():
    gcards = "".join(
        f'<a href="{U("guide/"+g["slug"]+"/")}"><article>{guide_eye(i, i)}<div class="gb">'
        f'<div class="gk">{g["kicker"]}</div>'
        f'<h3>{esc(g["title"])}</h3><p>{esc(g["lead"])}</p></div></article></a>'
        for i, g in enumerate(GUIDES))
    write("guide/index.html", layout(f"制度ガイド｜九州・沖縄の補助金の使い方｜{SITE_NAME}",
        "持続化補助金・ものづくり補助金・IT導入補助金など、九州・沖縄の事業者向けに制度の使い方と申請実務を解説します。",
        f'<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>制度ガイド</div></div>'
        f'<section><div class="wrap">{sec_h("GUIDES","制度ガイド","制度そのものの説明よりも、九州・沖縄の事業者が実際につまずく箇所を中心にまとめています。")}'
        f'<div class="guides">{gcards}</div></div></section>{CTA}', "guide/"))
    for i,g in enumerate(GUIDES):
        others = "".join(
            f'<a href="{U("guide/"+x["slug"]+"/")}"><article>{guide_eye(j+i+1, j+i+1)}<div class="gb">'
            f'<div class="gk">{x["kicker"]}</div>'
            f'<h3>{esc(x["title"])}</h3><p>{esc(x["lead"])}</p></div></article></a>'
            for j, x in enumerate((GUIDES[i+1:]+GUIDES[:i])[:3]))
        body = f"""
<div class="wrap narrow">
<div class="crumbs"><a href="{U()}">ホーム</a><span>/</span><a href="{U('guide/')}">制度ガイド</a><span>/</span>{esc(g['kicker'])}</div>
<div class="detail-h">
  <span class="tag" style="border-color:var(--hi);color:var(--hi)">{g['kicker']}</span>
  <h1>{esc(g['title'])}</h1>
  <p style="font-size:15px;color:var(--ink-70);margin:0;line-height:1.95">{esc(g['lead'])}</p>
</div>
<div class="prose">{g['body']}</div>
<div class="note" style="margin-top:44px">本ガイドは制度の一般的な仕組みを解説するものです。補助率・上限額・締切・要件は公募回ごとに改定されます。申請前に必ず各制度の公式の公募要領をご確認ください。個別の判断については、提携の専門家にご相談いただけます。</div>
<div style="margin:36px 0 10px"><a class="btn" href="{U('search/')}">九州・沖縄の受付中制度を検索する</a></div>
</div>
<section class="alt"><div class="wrap">{sec_h("MORE GUIDES","ほかのガイド")}<div class="guides">{others}</div></div></section>
{CTA}"""
        schema = '<script type="application/ld+json">' + json.dumps({
            "@context":"https://schema.org","@type":"Article","headline":g["title"],
            "description":g["lead"],"inLanguage":"ja",
            "publisher":{"@type":"Organization","name":SITE_NAME}}, ensure_ascii=False) + '</script>'
        write(f"guide/{g['slug']}/index.html", layout(f"{g['title']}｜{SITE_NAME}", g["lead"], body, f"guide/{g['slug']}/", schema=schema))

# ---------------------------------------------------------------- 固定ページ
def page(slug, title, desc, inner, crumb):
    body = (f'<div class="wrap narrow"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>{crumb}</div>'
            f'<div class="detail-h"><h1>{esc(title)}</h1></div><div class="prose">{inner}</div>'
            f'<div style="height:60px"></div></div>')
    write(f"{slug}/index.html", layout(f"{title}｜{SITE_NAME}", desc, body, f"{slug}/"))

def build_static():
    exp = "".join(
        f'<div><div class="r">{r}</div><div class="a">{a}</div>'
        f'<div style="font-size:12px;color:var(--ink-55);margin-top:9px;line-height:1.8">{note}</div></div>'
        for r,a,note in [
            ("行政書士","福岡県","許認可とセットの補助金申請。建設業・運送業・飲食の開業まわりに強い。"),
            ("中小企業診断士","福岡県","ものづくり補助金・新事業進出など、事業計画の作り込みが必要な制度。"),
            ("社会保険労務士","福岡県","キャリアアップ助成金、業務改善助成金など厚労省系の助成金全般。"),
            ("税理士","福岡県","資金繰りと補助金の会計処理、圧縮記帳、実績報告の証憑整備。"),
            ("行政書士","熊本県","半導体関連サプライヤーの設備導入と許認可。"),
            ("中小企業診断士","熊本県","製造業の生産性改善と設備投資計画。"),
            ("社会保険労務士","大分県","観光・宿泊業の雇用環境整備と助成金。"),
            ("税理士","佐賀県","農業法人・食品加工の補助金と税務。"),
            ("行政書士","長崎県","水産・造船関連、離島の事業者向け。"),
            ("中小企業診断士","宮崎県","畜産・施設園芸の加工／輸出計画。"),
            ("社会保険労務士","鹿児島県","食品製造の人材定着と処遇改善。"),
            ("税理士","沖縄県","沖縄振興特措法まわりの優遇と観光業の資金繰り。"),
        ])
    page("experts","申請支援（着手金0円・完全成果報酬）",
         "九州・沖縄の補助金申請を着手金0円の完全成果報酬で支援します。採択されなければ費用は発生しません。",
         f"""
<div class="seika" style="margin:0 -9999px 40px;padding:44px 9999px 42px">
  <div class="badge-row"><span class="bg1"><i></i>着手金・相談料 0円</span>
  <span class="bg2">SUCCESS FEE ONLY</span></div>
  <h2 style="font-size:clamp(24px,4vw,40px)">採択されなければ、<em>1円もいただきません。</em></h2>
  <p class="lead" style="margin-bottom:0">制度選びから事業計画の作成、採択後の実績報告まで。
  費用が発生するのは<b>採択が決まってから</b>だけです。</p>
</div>

<p>補助金で結果を分けるのは、制度選びよりも<strong>事業計画の書き方と、期日の管理</strong>です。
九州・沖縄各県の行政書士・中小企業診断士・社会保険労務士・税理士と連携し、
要件の確認から申請書の作成、採択後の実績報告までを一貫して支援します。</p>

<h2>料金の考え方</h2>
<table><tr><th>項目</th><th>費用</th></tr>
<tr><td>初回相談・制度選び・要件確認</td><td><strong>0円</strong></td></tr>
<tr><td>事業計画書の作成・申請代行</td><td><strong>0円</strong>（着手金なし）</td></tr>
<tr><td>不採択だった場合</td><td><strong>0円</strong></td></tr>
<tr><td>採択された場合</td><td>成功報酬のみ（料率は着手前に書面で提示）</td></tr>
<tr><td>交付申請・実績報告の代行</td><td>ご希望に応じて別途お見積り</td></tr></table>
<div class="note">成功報酬の料率は、制度の種類・補助額・作業範囲によって変わります。
<strong>着手前にかならず書面でお見積りを提示し、ご納得いただいてから着手</strong>します。
見積り後にお断りいただいても費用は発生しません。</div>

<h2>ご相談から入金までの流れ</h2>
<div class="flowline">
  <div><div class="s">STEP 1</div><div class="t">無料相談<span class="free">0円</span></div>
    <div class="d">県・業種・やりたいことをうかがい、使えそうな制度と概算スケジュールをご提示します。</div></div>
  <div><div class="s">STEP 2</div><div class="t">要件確認とお見積り<span class="free">0円</span></div>
    <div class="d">申請できるかを精査し、成功報酬の料率を書面で提示します。ここでお断りいただけます。</div></div>
  <div><div class="s">STEP 3</div><div class="t">申請書の作成<span class="free">0円</span></div>
    <div class="d">事業計画書・収支計画を一緒に作ります。加点要件の取得もこの段階で手当てします。</div></div>
  <div><div class="s">STEP 4</div><div class="t">採択・お支払い</div>
    <div class="d">採択が決まった時点で、はじめて成功報酬が発生します。以降の実績報告も支援できます。</div></div>
</div>

<h2>支援できること</h2>
<table><tr><th>段階</th><th>支援内容</th></tr>
<tr><td>制度選び</td><td>自社の投資計画に対して、どの制度が最も有利か。併用の可否</td></tr>
<tr><td>要件確認</td><td>従業員数・業種・資本金・賃上げ要件などの適合判定</td></tr>
<tr><td>申請書作成</td><td>事業計画書、収支計画、加点要件の取得</td></tr>
<tr><td>資金繰り</td><td>後払いを前提としたつなぎ資金、金融機関との調整</td></tr>
<tr><td>採択後</td><td>交付申請、実績報告、証憑整備、事業化状況報告</td></tr></table>

<div class="note warn">補助金は後払いです。採択されても、設備代はいったん自社で立て替える必要があります。
成功報酬のお支払い時期は、補助金の入金時期に合わせてご相談に応じます。</div>

<h2>提携している専門家（分野・エリア）</h2>
<div class="experts" style="margin:24px 0">{exp}</div>
<div class="note">本ページは提携分野の一覧です。個別の事務所名は、ご相談内容をうかがったうえでご案内します。</div>

<p style="margin-top:34px"><a class="btn" href="{U('contact/')}">無料で相談する</a></p>
""","申請支援・完全成果報酬")

    page("about","運営について",
         "九州補助金ナビの運営方針とデータの出どころについて。",
         f"""
<h2>このサイトについて</h2>
<p>{SITE_NAME}は、福岡・佐賀・長崎・熊本・大分・宮崎・鹿児島・沖縄の8県を対象とする補助金・助成金だけを集めた検索サイトです。全国版の情報サイトは掲載数こそ多いものの、九州・沖縄の事業者にとっては関係のない制度が大半を占めます。地域を絞ることで、実際に申請できる制度だけを見られるようにしました。</p>
<h2>データの出どころ</h2>
<p>掲載している制度情報は、デジタル庁が提供する<strong>jGrants（補助金電子申請システム）の公開API</strong>から取得しています。国・独立行政法人・都道府県が jGrants に登録した制度が対象です。取得日は各ページに表示しています（本ビルド：{TODAY_JP}）。</p>
<div class="note">jGrantsに登録されていない市区町村独自の制度は、本サイトには掲載されない場合があります。お住まいの自治体の産業振興課・商工観光課の情報も併せてご確認ください。</div>
<h2>掲載方針</h2>
<ul>
<li>補助率・上限額・締切は、公募回ごとに改定されます。本サイトの表示は取得時点のものです。</li>
<li>申請の可否や採択を保証するものではありません。</li>
<li>各制度の詳細ページから、かならず公式ページへ遷移できるようにしています。</li>
<li>受付が終了した制度も、後継制度を探す手がかりとして残しています。</li>
</ul>
<h2>掲載状況</h2>
<table><tr><th>項目</th><th>件数</th></tr>
<tr><td>九州・沖縄8県が対象の制度（重複なし）</td><td>{N_ALL:,} 件</td></tr>
<tr><td>うち受付中</td><td>{N_OPEN:,} 件</td></tr>
<tr><td>うち九州・沖縄に地域が限定された制度</td><td>{N_LOCAL:,} 件</td></tr>
<tr><td>県ごとに数え上げた延べ件数</td><td>{sum(len(pref_recs(n)) for _,n,_,_ in PREFS):,} 件</td></tr>
<tr><td>最終更新</td><td>{TODAY_JP}</td></tr></table>

<h2>件数の数え方について</h2>
<p>補助金の検索サイトによって、掲載件数の数え方は大きく異なります。本サイトは<strong>制度を重複なく1件と数えています</strong>。
たとえば全国公募のものづくり補助金は、8県すべてで使えても1件です。</p>
<p>これを「県ごとに1件」と数え直すと {sum(len(pref_recs(n)) for _,n,_,_ in PREFS):,} 件になります。
他サイトの表示件数と比べる際は、この数え方の違いをご確認ください。</p>
<div class="note">本サイトの件数が他サイトより少なく見えるのは、主に次の2つが理由です。<br>
① 制度を重複なく数えていること。<br>
② jGrantsに登録されない<strong>市区町村独自の制度と、個人向けの給付金</strong>を掲載していないこと。<br>
なお、jGrantsからの収集自体に取りこぼしはありません。150通りのキーワードで総当たりし、
件数がそれ以上増えないことを確認しています。</div>
""","運営について")

    page("contact","お問い合わせ",
         "九州補助金ナビへのお問い合わせ・補助金の無料相談はこちらから。",
         f"""
<p>補助金の相談、掲載内容の訂正、取材・提携のご依頼はこちらからお願いします。</p>
<div class="note"><strong>申請支援は着手金0円・完全成果報酬です。</strong>
制度選びと要件確認までは無料で、採択されなければ費用は発生しません。
料率は着手前に書面でご提示します。→ <a href="{U('experts/')}">支援の中身と流れ</a></div>
<h2>補助金の無料相談</h2>
<p>以下をお知らせいただくと、回答が早くなります。</p>
<ol><li>事業所のある県・市町村</li><li>業種</li><li>従業員数</li><li>やりたいこと（設備を入れたい／人を採りたい／販路を広げたい　など）</li><li>想定している投資額と時期</li></ol>
<p style="margin-top:28px"><a class="btn" href="mailto:info@avengerz-japan.com?subject=%E8%A3%9C%E5%8A%A9%E9%87%91%E3%81%AE%E7%9B%B8%E8%AB%87">メールで相談する</a></p>
<div class="note">お急ぎの場合は、件名に県名と業種を入れていただけると回答が早くなります。</div>
<h2>掲載内容について</h2>
<p>本サイトの制度情報はjGrants公開APIをもとに自動生成しています。内容に誤りを見つけられた場合、お手数ですが該当ページのURLを添えてご連絡ください。</p>
""","お問い合わせ")

    page("privacy","プライバシーポリシー","九州補助金ナビの個人情報の取扱いについて。", f"""
<h2>1. 取得する情報</h2>
<p>当サイトは、お問い合わせの際にご入力いただく氏名・会社名・メールアドレス・相談内容を取得します。また、サイトの利用状況を把握するためにアクセス解析ツールを使用する場合があります。</p>
<h2>2. 利用目的</h2>
<ul><li>お問い合わせへの回答および専門家のご紹介</li><li>サービスの改善・統計的な分析</li><li>法令にもとづく対応</li></ul>
<h2>3. 第三者提供</h2>
<p>ご本人の同意なく第三者に個人情報を提供することはありません。ただし、専門家の紹介をご希望いただいた場合に限り、必要な範囲で提携する士業へ情報を共有します。</p>
<h2>4. アクセス解析</h2>
<p>当サイトはアクセス解析にCookieを使用する場合があります。Cookieは個人を特定する情報を含みません。ブラウザの設定により無効化できます。</p>
<h2>5. 外部リンク</h2>
<p>当サイトから遷移する外部サイト（jGrants、各府省庁、自治体等）における個人情報の取扱いについては、各サイトのポリシーをご確認ください。</p>
<h2>6. 改定</h2>
<p>本ポリシーは必要に応じて改定します。改定後の内容は当ページに掲載した時点から効力を持ちます。</p>
<p style="color:var(--ink-40);font-size:13px">最終改定：{TODAY_JP}</p>
""","プライバシーポリシー")

    page("terms","利用規約","九州補助金ナビの利用条件について。", f"""
<h2>第1条（適用）</h2>
<p>本規約は、{SITE_NAME}（以下「当サイト」）の利用に関する条件を定めるものです。</p>
<h2>第2条（情報の正確性）</h2>
<p>当サイトに掲載する制度情報は、デジタル庁が提供するjGrants公開APIから取得した情報にもとづき自動生成しています。当サイトは情報の正確性・完全性・最新性について保証するものではありません。申請にあたっては、必ず各制度の公式の公募要領をご確認ください。</p>
<h2>第3条（免責）</h2>
<p>当サイトの情報を利用したことにより利用者に生じた損害について、当サイトは一切の責任を負いません。補助金の採択・不採択、支給・不支給についても同様です。</p>
<h2>第4条（禁止事項）</h2>
<ul><li>当サイトのコンテンツを無断で複製・再配布すること</li><li>過度なアクセスによりサーバに負荷をかける行為</li><li>法令または公序良俗に反する行為</li></ul>
<h2>第5条（著作権）</h2>
<p>当サイトが作成した文章・デザインの著作権は当サイトに帰属します。制度情報の原典は各所管府省庁・自治体に帰属します。</p>
<h2>第6条（改定）</h2>
<p>本規約は予告なく改定される場合があります。</p>
<p style="color:var(--ink-40);font-size:13px">最終改定：{TODAY_JP}</p>
""","利用規約")

    write("404.html", layout("ページが見つかりません｜"+SITE_NAME, "お探しのページは見つかりませんでした。",
        f'<div class="wrap narrow" style="padding:90px 20px;text-align:center">'
        f'<div style="font-family:var(--serif);font-size:62px;font-weight:700;color:var(--hi)">404</div>'
        f'<h1 style="font-family:var(--serif);font-size:24px;margin:16px 0 14px">ページが見つかりませんでした</h1>'
        f'<p style="color:var(--ink-55);margin-bottom:30px">公募の終了などにより、URLが変わった可能性があります。</p>'
        f'<a class="btn" href="{U("search/")}">補助金を検索する</a></div>', "404"))

# ---------------------------------------------------------------- sitemap
def build_meta():
    urls = ["", "search/", "deadline/", "alerts/", "guide/", "purpose/", "industry/", "audience/",
            "permit/", "ai/", "experts/", "about/", "contact/", "privacy/", "terms/"]
    urls += [f"pref/{s}/" for s,_,_,_ in PREFS]
    urls += [f"audience/{a[0]}/" for a in AUDIENCES]
    if MUNI:
        urls += ["muni/"] + [f"muni/{v}/" for v in MUNI_SLUG.values()]
    urls += [f"permit/{x[0]}/" for x in PERMITS]
    urls += [f"purpose/{P_SLUG[p]}/{s2}/" for p in PURPOSE_LIST for s2,n,_,_ in PREFS
             if [r for r in purpose_recs(p) if n in r["prefs"]]]
    urls += [f"industry/{I_SLUG[p]}/{s2}/" for p in INDUSTRY_LIST for s2,n,_,_ in PREFS
             if len([r for r in industry_recs(p) if n in r["prefs"]]) >= 3]
    urls += [f"guide/{g['slug']}/" for g in GUIDES]
    urls += [f"purpose/{P_SLUG[p]}/" for p in PURPOSE_LIST]
    urls += [f"industry/{I_SLUG[p]}/" for p in INDUSTRY_LIST]
    urls += [f"subsidy/{r['id']}/" for r in RECS]
    root = BASE_URL or ""
    body = "".join(f"<url><loc>{root}{U(u)}</loc><lastmod>{TODAY}</lastmod></url>" for u in urls)
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+body+"</urlset>")
    write("robots.txt", f"User-agent: *\nAllow: /\n" + (f"Sitemap: {root}{U('sitemap.xml')}\n" if root else ""))
    write(".nojekyll", "")


# ================================================================ アイコン
_I = {
"factory":"M3 20h18M4 20v-9l5 3v-3l5 3V7l6 4v9M8 20v-3h3v3",
"helmet":"M4 18h16M5 18a7 7 0 0 1 14 0M9.5 5.5A6.9 6.9 0 0 1 12 5c.9 0 1.7.2 2.5.5M12 5V2.6M8 11V7M16 11V7",
"chip":"M8 8h8v8H8zM10 8V4.5M14 8V4.5M10 19.5V16M14 19.5V16M8 10H4.5M8 14H4.5M19.5 10H16M19.5 14H16",
"cart":"M3 4h2l2.3 10.7a2 2 0 0 0 2 1.6h7.5a2 2 0 0 0 2-1.5L21 8H6M10 20.5h.01M18 20.5h.01",
"food":"M5 3v6a2 2 0 0 0 4 0V3M7 11v10M16.5 3c-1.4 1.6-2 3.6-2 5.6 0 1.9 1 3.4 2.5 3.4H19V3h-2.5zM18 12v9",
"heart":"M12 20.3S4.5 15.6 4.5 10.5A3.8 3.8 0 0 1 12 8a3.8 3.8 0 0 1 7.5 2.5c0 5.1-7.5 9.8-7.5 9.8z",
"sprout":"M12 21v-7.5M12 13.5c0-3.2 2.2-5.3 5.3-5.3 0 3.2-2.1 5.3-5.3 5.3zM12 13.5c0-3.2-2.2-5.3-5.3-5.3 0 3.2 2.1 5.3 5.3 5.3zM12 6V3",
"fish":"M3.5 12c3-4.3 6.9-5.5 9.8-5.5 4 0 6.9 2.2 7.7 5.5-.8 3.3-3.7 5.5-7.7 5.5-2.9 0-6.8-1.2-9.8-5.5zM17.5 10.8h.01M3.5 12 1.6 8.2M3.5 12 1.6 15.8",
"truck":"M3 7h11v9.5H3zM14 10.5h4l3 3v3h-7zM7 19.5h.01M18 19.5h.01",
"building":"M4 21V6.5L11 3l7 3.5V21M9.5 21v-4.5h5V21M7.5 10h1.5M14.5 10H16M7.5 14h1.5M14.5 14H16",
"flask":"M9 3h6M10 3v6.2L5.2 18a2 2 0 0 0 1.8 3h10a2 2 0 0 0 1.8-3L14 9.2V3M8 15h8",
"spa":"M12 3.5l1.9 4.6L18.5 10l-4.6 1.9L12 16.5l-1.9-4.6L5.5 10l4.6-1.9zM18.5 16l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z",
"book":"M4 4.5h5.5a2.5 2.5 0 0 1 2.5 2.5v13a2 2 0 0 0-2-2H4zM20 4.5h-5.5A2.5 2.5 0 0 0 12 7v13a2 2 0 0 1 2-2h6z",
"coins":"M4 6.5c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6.5v11c0 1.7 3.6 3 8 3s8-1.3 8-3v-11M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
"bolt":"M13.2 2.5 4.5 14H11l-1 7.5L19.5 10H13z",
"layers":"M12 3 3 7.8l9 4.8 9-4.8zM3 13l9 4.8 9-4.8",
"gear":"M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM12 2.5v2.8M12 18.7v2.8M2.5 12h2.8M18.7 12h2.8M5.2 5.2l2 2M16.8 16.8l2 2M18.8 5.2l-2 2M7.2 16.8l-2 2",
"case":"M3 8h18v12H3zM8.5 8V5h7v3M3 13.5h18M10.5 13.5h3",
"rocket":"M12 2.5s4.2 2.3 4.2 8.2c0 3-1.6 5.2-4.2 7.2-2.6-2-4.2-4.2-4.2-7.2C7.8 4.8 12 2.5 12 2.5zM12 11.2a1.6 1.6 0 1 0 0-3.2 1.6 1.6 0 0 0 0 3.2zM8.2 15.5 6 21l4-2M15.8 15.5 18 21l-4-2",
"monitor":"M3.5 5h17v10.5h-17zM8.5 20h7M12 15.5V20",
"globe":"M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3.3 12h17.4M12 3c2.6 2.8 2.6 15.2 0 18M12 3c-2.6 2.8-2.6 15.2 0 18",
"cap":"M12 4 2.5 8.6 12 13.2l9.5-4.6zM6.3 10.8v4.5c0 1.8 2.6 3.2 5.7 3.2s5.7-1.4 5.7-3.2v-4.5",
"users":"M16 20.5v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 10.5a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 20.5v-2a4 4 0 0 0-3-3.9M16.5 2.7a4 4 0 0 1 0 7.7",
"swap":"M4 8.5h13l-3.4-3.4M20 15.5H7l3.4 3.4",
"yen":"M6.5 4.5 12 12l5.5-7.5M12 12v7.5M8.2 13.8h7.6M8.2 16.6h7.6",
"town":"M2.5 21h19M5 21V9l7-5 7 5v12M10 21v-5h4v5M8 12h1.5M14.5 12H16",
"mega":"M3 11v2.2a1 1 0 0 0 1 1h2.2L11.5 18V6L6.2 9.8H4a1 1 0 0 0-1 1zM15.5 8.5a4.2 4.2 0 0 1 0 7M18.5 5.5a8.2 8.2 0 0 1 0 13",
"shield":"M12 2.5 4.5 5.3v5.9c0 4.8 3.2 9 7.5 10.3 4.3-1.3 7.5-5.5 7.5-10.3V5.3zM9.2 12.2l2 2 3.6-3.8",
"user":"M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
"store":"M4 9.5h16V21H4zM2.8 9.5 4.6 4h14.8l1.8 5.5M9.5 21v-6h5v6",
"towers":"M3 21V8.5h7V21M14 21V3h7v18M6 12h1.5M6 16h1.5M17 7h1.5M17 11.5h1.5M17 16h1.5",
"search":"M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.4-4.4",
"calendar":"M4 5.5h16V21H4zM4 10h16M8.5 3v4M15.5 3v4M8 14h2M14 14h2M8 17.5h2M14 17.5h2",
"doc":"M13 3H6.5v18h11V7.5zM13 3v4.5h4.5M9 12.5h6M9 16h6",
"chat":"M21 12a8 8 0 0 1-8 8H4l2-3.2A8 8 0 1 1 21 12z",
}
def svg_icon(key, cls=""):
    p = _I.get(key, _I["gear"])
    c = ' class="' + cls + '"' if cls else ""
    return '<svg viewBox="0 0 24 24" aria-hidden="true"' + c + '><path d="' + p + '"/></svg>'

_IND_ICON = [("製造","factory"),("建設","helmet"),("情報通信","chip"),("卸売","cart"),("小売","cart"),
 ("宿泊","food"),("飲食","food"),("医療","heart"),("福祉","heart"),("農業","sprout"),("林業","sprout"),
 ("漁業","fish"),("運輸","truck"),("郵便","truck"),("不動産","building"),("物品賃貸","building"),
 ("学術","flask"),("専門","flask"),("技術サービス","flask"),("生活関連","spa"),("娯楽","spa"),
 ("教育","book"),("学習","book"),("金融","coins"),("保険","coins"),("電気","bolt"),("ガス","bolt"),
 ("水道","bolt"),("熱供給","bolt"),("鉱業","layers"),("採石","layers"),("複合サービス","layers"),
 ("公務","case"),("サービス業","gear"),("分類不能","gear")]
_PUR_ICON = [("新たな事業","rocket"),("設備","monitor"),("IT","monitor"),("販路","globe"),("海外","globe"),
 ("人材","cap"),("育成","cap"),("雇用","users"),("職場","users"),("研究","flask"),("実証","flask"),
 ("引き継","swap"),("承継","swap"),("資金","yen"),("まちづくり","town"),("地域","town"),
 ("イベント","mega"),("運営","mega"),("感染","shield"),("環境","sprout"),("省エネ","bolt")]
def icon_for(label, table):
    for k, v in table: 
        if k in label: return v
    return "gear"
def ind_icon(l): return icon_for(l, _IND_ICON)
def pur_icon(l): return icon_for(l, _PUR_ICON)

def cards(items, cls=""):
    """items: [(href, icon_key, 名称, 件数 or "")]"""
    out = []
    for href, ik, nm, c in items:
        cnt = '<span class="c">' + str(c) + '</span>' if c != "" else ""
        out.append('<a href="' + href + '"><span class="ic">' + svg_icon(ik) + '</span>'
                   '<span class="nm">' + esc(nm) + '</span>' + cnt + '</a>')
    k = "cards" + ((" " + cls) if cls else "")
    return '<div class="' + k + '">' + "".join(out) + '</div>'

# ================================================================ 九州・沖縄マップ
KMAP = json.load(open(os.path.join(ROOT, "data", "kyushu_map.json"), encoding="utf-8"))

LABEL_ADJ = {"fukuoka": (12, -10), "saga": (-14, 2), "nagasaki": (-16, 18),
             "kumamoto": (-2, -6), "oita": (2, -2), "miyazaki": (4, 2), "kagoshima": (-4, -6)}
PREF_FILL = {"fukuoka": "#BFE1FB", "saga": "#9ED3F6", "nagasaki": "#D8EDFD", "kumamoto": "#AFDAF8",
             "oita": "#E2F2FE", "miyazaki": "#C9E7FC", "kagoshima": "#A6D6F7", "okinawa": "#BBDFFA"}

def kmap(active=None):
    shapes, labels = [], []
    for s, n, en, _ in PREFS:
        o = len([r for r in pref_recs(n) if r["status"] == "open"])
        sel = ' aria-current="true"' if active == s else ''
        if s == "okinawa":
            continue
        lx, ly = KMAP["labels"][s]
        dx, dy = LABEL_ADJ.get(s, (0, 0)); lx += dx; ly += dy
        shapes.append(f'<a class="pref" href="{U("pref/"+s+"/")}"{sel} aria-label="{n}の補助金 受付中{o}件">'
                      f'<title>{n}／受付中 {o}件</title>'
                      f'<path fill="{PREF_FILL[s]}" d="{KMAP["main"][s]}"/></a>')
        labels.append(f'<text class="lab" x="{lx}" y="{ly}" text-anchor="middle">{n[:-1]}</text>'
                      f'<text class="num" x="{lx}" y="{ly+13}" text-anchor="middle">受付中 {o}件</text>')
    n = "沖縄県"
    o = len([r for r in pref_recs(n) if r["status"] == "open"])
    oki = (f'<a class="pref" href="{U("pref/okinawa/")}" aria-label="沖縄県の補助金 受付中{o}件">'
           f'<title>沖縄県／受付中 {o}件</title>'
           f'<path fill="{PREF_FILL["okinawa"]}" d="{KMAP["okinawa"]["path"]}"/></a>'
           f'<g class="lbl"><text class="lab" x="64" y="32" text-anchor="middle">沖縄</text>'
           f'<text class="num" x="64" y="45" text-anchor="middle">受付中 {o}件</text></g>')
    return (f'<svg class="kmap" viewBox="0 0 322 396" role="img" '
            f'aria-label="九州・沖縄8県の補助金マップ">'
            f'<g transform="translate(21,6)">{"".join(shapes)}'
            f'<g class="lbl">{"".join(labels)}</g></g>'
            f'<g transform="translate(3,258) scale(.86)">'
            f'<rect class="inset" x="0" y="0" width="130" height="96" rx="4"/>{oki}</g>'
            f'<text class="cap" x="318" y="392" text-anchor="end">KYUSHU &amp; OKINAWA</text></svg>')

def pref_thumb(slug):
    return (f'<svg class="th" viewBox="0 0 100 100" aria-hidden="true">'
            f'<path d="{KMAP["thumbs"][slug]}"/></svg>')

# ================================================================ 装飾（生成画像）
HERO_ART = ('<div class="hero-art" aria-hidden="true"><svg viewBox="0 0 600 600" '
            'xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice">'
            '<defs><linearGradient id="hg" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#7CC2F3"/><stop offset="1" stop-color="#E3F1FD"/>'
            '</linearGradient></defs>'
            + "".join(
                f'<circle cx="430" cy="210" r="{r}" fill="none" stroke="url(#hg)" '
                f'stroke-width="1" opacity="{0.55 - i*0.032:.2f}"/>'
                for i, r in enumerate(range(40, 460, 26)))
            + "".join(
                f'<path d="M-40 {y} C 120 {y-34}, 260 {y+30}, 420 {y-12} S 660 {y+22}, 700 {y-6}" '
                f'fill="none" stroke="#6FB8EE" stroke-width="1" opacity="{0.34 - i*0.030:.2f}"/>'
                for i, y in enumerate(range(430, 620, 22)))
            + '</svg></div>')

_EYE_PAL = [("#1A6DB5", "#8FD0F7"), ("#0E9BC4", "#9DE6F2"), ("#2A7FC4", "#B6DFFA"),
            ("#103F6E", "#79C0F2"), ("#1487B5", "#A5DCF6"), ("#2573B8", "#94CFF6")]
def guide_eye(i, motif=0):
    a, b = _EYE_PAL[i % len(_EYE_PAL)]
    m = motif % 4
    if m == 0:
        art = "".join(f'<rect x="{20+j*46}" y="{104-j*13}" width="30" height="{16+j*13}" fill="{b}" opacity="{.35+j*.14:.2f}"/>' for j in range(5))
    elif m == 1:
        art = "".join(f'<circle cx="{46+j*42}" cy="60" r="{8+j*7}" fill="none" stroke="{b}" stroke-width="2.4" opacity="{.8-j*.13:.2f}"/>' for j in range(5))
    elif m == 2:
        art = ('<path d="M0 92 C 60 62, 120 108, 180 76 S 300 52, 360 84" fill="none" stroke="'+b+'" stroke-width="2.6"/>'
               '<path d="M0 110 C 60 82, 120 126, 180 96 S 300 74, 360 104" fill="none" stroke="'+b+'" stroke-width="2" opacity=".6"/>'
               + "".join(f'<circle cx="{40+j*70}" cy="{84-j*4}" r="4.5" fill="{b}"/>' for j in range(5)))
    else:
        art = "".join(f'<path d="M{30+j*60} 100 l22-44 22 44z" fill="{b}" opacity="{.28+j*.16:.2f}"/>' for j in range(4))
    return (f'<svg class="eye" viewBox="0 0 360 120" preserveAspectRatio="xMidYMid slice" aria-hidden="true">'
            f'<rect width="360" height="120" fill="{a}"/>{art}</svg>')

# ================================================================ 対象者から探す
def _emp_le(r, n):
    m = re.match(r"(\d+)名以下", r["emp"] or "")
    return bool(m) and int(m.group(1)) <= n
def _free(r): return "制約なし" in (r["emp"] or "")
def _has(r, *ws):
    t = r["title"] + " " + r["industry"] + " " + r["purpose"]
    return any(w in t for w in ws)

AUDIENCES = [
 ("sme","中小企業","SMALL & MEDIUM BUSINESS","building",
  "資本金・従業員数が中小企業基本法の範囲に収まる法人。九州・沖縄の制度の大半がここを主対象にしています。",
  lambda r: _free(r) or _emp_le(r, 300)),
 ("sole","個人事業主","SOLE PROPRIETOR","user",
  "開業届を出して事業を営む個人。法人でなくても申請できる制度は想像以上に多くあります。",
  lambda r: _free(r) or _emp_le(r, 20)),
 ("micro","小規模事業者","MICRO BUSINESS","store",
  "商業・サービス業は従業員5人以下、製造業その他は20人以下が目安。持続化補助金の主戦場です。",
  lambda r: _emp_le(r, 20)),
 ("startup","創業・起業予定","STARTUP","rocket",
  "これから開業する方、開業して間もない方。創業枠や開業支援の加点が使えます。",
  lambda r: _has(r, "創業", "起業", "スタートアップ", "新規開業", "新たな事業")),
 ("large","大企業","LARGE ENTERPRISE","towers",
  "中小企業の枠を超える規模の事業者。件数は絞られますが、研究開発・脱炭素系で対象になります。",
  lambda r: _free(r) or (not _emp_le(r, 300) and bool(r["emp"]))),
 ("npo","NPO・団体","NPO & ORGANIZATION","users",
  "特定非営利活動法人、組合、協議会など。地域づくり・福祉分野で対象になる制度があります。",
  lambda r: _has(r, "NPO", "非営利", "団体", "組合", "協議会", "まちづくり", "地域")),
 ("women","女性・若者","WOMEN & YOUTH","user",
  "女性活躍や若者の就業・起業を後押しする枠。加点要件として設定されることも多い区分です。",
  lambda r: _has(r, "女性", "若者", "若年", "両立", "育児", "子育て")),
 ("primary","農林漁業者","PRIMARY INDUSTRY","sprout",
  "農業・林業・漁業の事業者。九州・沖縄では一次産業の比重が高く、専用の支援が厚い分野です。",
  lambda r: _has(r, "農業", "林業", "漁業", "畜産", "水産", "園芸")),
]

def build_audience():
    items = []
    for slug, name, en, ic, desc, pred in AUDIENCES:
        rs = [r for r in RECS if pred(r)]
        items.append((U("audience/" + slug + "/"), ic, name, len(rs)))
    body = (f'<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>対象者から探す</div></div>'
            f'<section><div class="wrap">'
            + sec_h("BY AUDIENCE", "対象者から補助金・助成金を探す",
                    "自社の形態や立場から、対象になりうる制度を絞り込みます。区分は本サイトが掲載データをもとに分類したものです。")
            + cards(items, "c4") + '</div></section>' + CTA)
    write("audience/index.html", layout(f"対象者から補助金を探す｜{SITE_NAME}",
        "中小企業・個人事業主・小規模事業者・創業予定者など、立場別に九州・沖縄の補助金を探せます。", body, "audience/"))

    for slug, name, en, ic, desc, pred in AUDIENCES:
        rs = [r for r in RECS if pred(r)]
        op = [r for r in rs if r["status"] == "open"]
        pb = [(U("search/") + "?pref=" + n, "search", n, len([r for r in rs if n in r["prefs"]])) for _, n, _, _ in PREFS]
        others = "".join(f'<a class="tag pref" style="margin:0 6px 6px 0;padding:8px 14px;font-size:13px" '
                         f'href="{U("audience/"+s2+"/")}">{n2}</a>' for s2, n2, _, _, _, _ in AUDIENCES if s2 != slug)
        body = (f'<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>'
                f'<a href="{U("audience/")}">対象者から探す</a><span>/</span>{name}</div></div>'
                f'<section><div class="wrap">'
                + sec_h("BY AUDIENCE", name + "が使える補助金・助成金",
                        desc + f"　該当 {len(rs):,} 件／受付中 {len(op)} 件（{TODAY_JP}時点）")
                + rows(op[:30] or rs[:20])
                + '<div style="padding-top:34px">' + sec_h("BY PREFECTURE", "県で絞り込む") + cards(pb, "c4") + '</div>'
                + '</div></section>'
                f'<section class="alt"><div class="wrap">' + sec_h("OTHER", "ほかの対象者") + others + '</div></section>' + CTA)
        write(f"audience/{slug}/index.html", layout(
            f"{name}向けの補助金・助成金【九州・沖縄／受付中{len(op)}件】｜{SITE_NAME}",
            f"{name}が対象になりうる九州・沖縄の補助金・助成金を{len(rs)}件掲載。受付中{len(op)}件。{desc}",
            body, f"audience/{slug}/"))

# ================================================================ 許認可・届出ガイド
PERMITS = [
 ("construction","建設業","CONSTRUCTION","helmet",
  "建設業で開業・拡大するときに必要になる許可と届出をまとめました。請負金額によって許可の要否が変わります。",
  [("許可","建設業許可（知事許可／大臣許可）","都道府県知事または国土交通大臣","おおむね30〜90日",
    "1件の請負金額が建築一式工事で1,500万円以上（または延べ面積150㎡以上の木造住宅）、その他の工事で500万円以上になる場合に必要です。営業所が1つの都道府県内なら知事許可、複数県にまたがる場合は大臣許可。経営業務の管理責任者と専任技術者の配置、財産的基礎の要件があります。"),
   ("許可","特定建設業許可","都道府県知事または国土交通大臣","おおむね30〜90日",
    "元請として下請に出す金額の合計が一定額以上になる場合に必要な、一般建設業より要件の重い許可です。財産的基礎（資本金・自己資本）と専任技術者の資格要件が厳しくなります。"),
   ("審査","経営事項審査（経審）","都道府県知事または国土交通大臣","決算後、おおむね2〜3か月",
    "公共工事を元請として直接請け負う場合に必須の審査です。経営規模・経営状況・技術力・社会性を点数化します。入札参加資格の申請とセットで考えます。"),
   ("登録","解体工事業登録","都道府県知事","おおむね30日",
    "建設業許可（土木・建築・とび土工）を持たずに解体工事を請け負う場合に必要な登録です。技術管理者の設置が要件。"),
   ("登録","電気工事業者登録／届出","都道府県知事または経済産業大臣","おおむね2〜4週間",
    "一般用電気工作物や自家用電気工作物の電気工事を請け負う場合に必要です。主任電気工事士の設置と、絶縁抵抗計等の器具備付けが求められます。"),
   ("許可","産業廃棄物収集運搬業許可","都道府県知事または政令市長","おおむね1〜2か月",
    "工事で出た廃棄物を自社で他者の現場から運ぶ場合などに必要です。講習会の修了が前提になります。"),
   ("届出","労働保険（労災・雇用）成立届","労働基準監督署・ハローワーク","即日〜数日",
    "人を雇う場合は事業開始から10日以内に手続きします。建設業は元請・下請で労災の扱いが異なる点に注意。")]),
 ("hospitality","宿泊業・飲食サービス業","HOSPITALITY & FOOD","food",
  "飲食店・宿泊施設の開業に必要な許可と届出です。保健所・消防署・警察署と、窓口が分かれます。",
  [("許可","飲食店営業許可","保健所（都道府県知事等）","事前相談から1か月程度",
    "食品衛生法にもとづく許可です。厨房の構造設備が施設基準を満たしていること、食品衛生責任者を置くことが前提。内装工事の着工前に保健所へ図面を持って事前相談するのが実務の鉄則です。"),
   ("届出","食品衛生責任者の設置","保健所","即日",
    "施設ごとに1名以上。調理師・栄養士等の有資格者は講習免除、それ以外は養成講習会（約6時間）を受講します。"),
   ("届出","防火管理者選任届","消防署","即日",
    "収容人員30人以上の飲食店で必要です。延べ面積300㎡以上は甲種、未満は乙種の講習修了が要件。"),
   ("届出","深夜酒類提供飲食店営業開始届出","警察署（公安委員会）","営業開始の10日前まで",
    "深夜0時以降に酒類を提供する場合に必要です。店舗の平面図・求積図の添付が求められ、用途地域による制限もあります。"),
   ("許可","菓子製造業許可","保健所","1〜2週間",
    "パン・ケーキ・和菓子などを製造して販売する場合、飲食店営業許可とは別に必要です。専用の製造区画が求められます。"),
   ("許可","旅館業許可（旅館・ホテル営業／簡易宿所営業）","保健所","事前相談から1〜3か月",
    "宿泊料を受けて人を宿泊させる場合に必要です。建築基準法・消防法の適合、フロント設置や構造設備の基準を満たす必要があります。"),
   ("届出","住宅宿泊事業（民泊）届出","都道府県知事等","2週間〜1か月",
    "年間提供日数180日以内の民泊を行う場合の届出制度です。自治体の条例で区域や期間が上乗せ規制されることがあり、沖縄・福岡では特に確認が必要です。")]),
 ("transport","運輸業・郵便業","TRANSPORT & LOGISTICS","truck",
  "トラック・バス・タクシーなど、運送事業の開業に必要な許可・届出です。",
  [("許可","一般貨物自動車運送事業許可","地方運輸局（九州運輸局・沖縄総合事務局）","3〜5か月",
    "他人の荷物を有償で運ぶ場合に必要です。営業所・車庫・休憩施設の要件、車両5台以上、運行管理者・整備管理者の選任、一定の自己資金が求められます。"),
   ("届出","貨物軽自動車運送事業届出","地方運輸局","即日〜数日",
    "軽自動車・バイクで有償運送を行う場合の届出です。車両1台から開始できます。"),
   ("選任","運行管理者の選任","地方運輸局","届出後すぐ",
    "車両数に応じた人数の運行管理者を選任します。国家試験合格または一定の実務経験＋講習が要件。"),
   ("選任","整備管理者の選任","地方運輸局","届出後すぐ",
    "車両5台以上の営業所ごとに必要です。整備士資格または2年以上の実務経験＋研修修了。"),
   ("許可","一般乗用旅客自動車運送事業許可（タクシー）","地方運輸局","4〜6か月",
    "人を有償で運ぶ事業に必要です。地域によって新規参入が制限されている場合があります。")]),
 ("realestate","不動産業","REAL ESTATE","building",
  "不動産の売買・仲介・管理を行うために必要な免許と登録です。",
  [("免許","宅地建物取引業免許","都道府県知事または国土交通大臣","30〜60日",
    "不動産の売買・交換・仲介を業として行う場合に必要です。事務所ごとに従業者5名に1名以上の専任の宅地建物取引士を設置します。"),
   ("供託等","営業保証金の供託／保証協会への加入","法務局または保証協会","2週間〜1か月",
    "主たる事務所1,000万円・従たる事務所ごと500万円の供託、または保証協会に加入して弁済業務保証金分担金（60万円／30万円）を納付します。実務では保証協会加入が一般的。"),
   ("登録","賃貸住宅管理業登録","国土交通大臣","1〜2か月",
    "管理戸数200戸以上で賃貸住宅の管理受託を行う場合に必要です。業務管理者の配置が要件。"),
   ("届出","サブリース（特定転貸事業者）の規制対応","国土交通省","—",
    "マスターリース契約では重要事項説明と契約書面の交付が義務づけられ、誇大広告・不当勧誘が禁止されています。登録制ではありませんが違反には罰則があります。")]),
 ("medical","医療・福祉","MEDICAL & WELFARE","heart",
  "診療所・介護事業所・障害福祉サービスの開設に必要な手続きです。",
  [("届出／許可","診療所開設届／開設許可","保健所（都道府県知事等）","届出は10日以内・許可は1〜2か月",
    "医師・歯科医師が開設する無床診療所は開設後10日以内の届出、有床診療所や医師以外が開設する場合は事前の開設許可が必要です。"),
   ("指定","保険医療機関の指定","地方厚生局","申請月の翌月1日付",
    "健康保険を扱うために必要です。締切日が月単位で決まっているため、開業日から逆算したスケジュール管理が重要になります。"),
   ("指定","介護保険事業者指定","都道府県または市町村","1〜2か月",
    "訪問介護・通所介護・居宅介護支援などサービス種別ごとに指定を受けます。人員・設備・運営の3基準を満たす必要があります。"),
   ("指定","障害福祉サービス事業者指定","都道府県または市町村","1〜2か月",
    "就労継続支援、生活介護、放課後等デイサービスなど。自治体ごとに事前協議の運用が異なります。"),
   ("届出","医療法人設立認可","都道府県知事","4〜8か月",
    "年2回程度の受付時期が定められていることが多く、スケジュールの制約が大きい手続きです。")]),
 ("beauty","美容業・生活関連サービス","BEAUTY & PERSONAL SERVICE","spa",
  "美容室・理容室・クリーニング店などの開業に必要な届出です。",
  [("届出","美容所開設届","保健所","検査を含めて1〜2週間",
    "開設前に届出を行い、構造設備の検査を受けます。作業室の面積、消毒設備、採光・照明・換気の基準があります。"),
   ("届出","理容所開設届","保健所","検査を含めて1〜2週間",
    "美容所と基準が異なります。美容と理容を同一店舗で行う場合は両方の届出と区画が必要になることがあります。"),
   ("選任","管理美容師・管理理容師の設置","保健所","—",
    "美容師・理容師が常時2名以上いる施設で必要です。実務経験3年以上かつ講習会修了が要件。"),
   ("届出","クリーニング所開設届","保健所","1〜2週間",
    "クリーニング師の設置と、業務従事者の講習受講が求められます。取次店のみの場合も届出が必要です。")]),
 ("food","食品製造・小売","FOOD MANUFACTURING & RETAIL","cart",
  "食品を製造・販売するための営業許可と、酒・中古品などの個別免許です。",
  [("許可","食品衛生法にもとづく営業許可（32業種）","保健所","1〜2週間",
    "菓子製造業、そうざい製造業、麺類製造業、食肉販売業、魚介類販売業など、業種ごとに許可が必要です。どの許可に当たるかは扱う品目と加工の度合いで決まるため、保健所への事前相談が確実です。"),
   ("届出","営業届出（許可業種以外）","保健所","即日",
    "2021年の食品衛生法改正で、許可が不要な食品関係営業にも届出が義務づけられました。"),
   ("体制","HACCPに沿った衛生管理","保健所（監視指導）","—",
    "すべての食品等事業者に義務づけられています。小規模事業者は業界団体の手引書に沿った簡略な運用が認められます。"),
   ("免許","酒類販売業免許","税務署","2か月程度",
    "一般酒類小売業免許、通信販売酒類小売業免許など種別があります。通信販売免許では扱える銘柄に制限がある点に注意。"),
   ("許可","古物商許可","警察署（公安委員会）","40日程度",
    "中古品を仕入れて販売する場合に必要です。リユース・リサイクル、買取を伴う小売で該当します。")]),
 ("it","情報通信業","IT & TELECOM","chip",
  "IT・通信サービスを提供する際に関係する届出と、実務上求められる認証です。",
  [("届出","電気通信事業の届出／登録","総務省","届出は即日〜数週間",
    "他人の通信を媒介するサービス（メッセージング、VPN、一部のクラウド等）を提供する場合に必要です。単なるウェブサイト運営は対象外ですが、判断が難しいため総務省の相談窓口の利用が確実です。"),
   ("許可","古物商許可","警察署（公安委員会）","40日程度",
    "中古PC・スマートフォンの買取販売を行う場合に必要です。"),
   ("届出","労働者派遣事業許可／有料職業紹介事業許可","厚生労働大臣","2〜3か月",
    "エンジニアの派遣や紹介を行う場合に必要です。資産要件（基準資産額・現預金）と派遣元責任者講習の受講が求められます。"),
   ("認証","プライバシーマーク／ISMS（任意）","審査機関","6か月〜1年",
    "法令上の義務ではありませんが、官公庁・大企業との取引で実質的な参加要件になることがあります。")]),
]

def build_permits():
    items = [(U("permit/" + s + "/"), ic, n, len(its)) for s, n, en, ic, d, its in PERMITS]
    body = (f'<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>許認可・届出ガイド</div></div>'
            f'<section><div class="wrap">'
            + sec_h("PERMITS", "許認可・届出ガイド",
                    "開業や新規事業の前に必要な許可・届出を業種別にまとめました。補助金の申請より前に、ここが通らないと事業が始められません。")
            + cards(items, "c4")
            + '<div class="note" style="margin-top:34px">許認可の要件・処理期間は自治体や事案によって変わります。'
              '最終的な判断はかならず管轄窓口、または行政書士にご確認ください。</div>'
            + '</div></section>' + CTA)
    write("permit/index.html", layout(f"許認可・届出ガイド｜業種別に必要な手続き｜{SITE_NAME}",
        "建設業・飲食業・運輸業・不動産業など、業種ごとに開業に必要な許認可と届出、管轄窓口、処理期間をまとめています。",
        body, "permit/"))

    for s, n, en, ic, desc, its in PERMITS:
        lst = "".join(
            f'<article><div class="ph">'
            f'<span class="kind{" todoke" if k in ("届出","選任","体制","供託等") else ""}">{esc(k)}</span>'
            f'<span class="span">処理期間の目安：{esc(sp)}</span></div>'
            f'<h3>{esc(t)}</h3><div class="kan">管轄：{esc(kan)}</div><p>{esc(ds)}</p></article>'
            for k, t, kan, sp, ds in its)
        rel = [r for r in RECS if r["status"] == "open" and n.split("業")[0] in (r["industry"] or "")][:6]
        others = "".join(f'<a class="tag pref" style="margin:0 6px 6px 0;padding:8px 14px;font-size:13px" '
                         f'href="{U("permit/"+s2+"/")}">{n2}</a>' for s2, n2, _, _, _, _ in PERMITS if s2 != s)
        body = (f'<div class="wrap narrow"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>'
                f'<a href="{U("permit/")}">許認可・届出ガイド</a><span>/</span>{n}</div>'
                f'<div class="detail-h"><span class="tag" style="border-color:var(--hi);color:var(--hi)">{en}</span>'
                f'<h1>{n}の開業に必要な許認可・届出</h1>'
                f'<p style="font-size:15px;color:var(--ink-70);margin:0;line-height:1.95">{esc(desc)}</p></div>'
                f'<div class="permits">{lst}</div>'
                f'<div class="note warn" style="margin-top:32px">ここに挙げたのは代表的なものです。'
                f'取り扱う品目・立地・規模によって必要な手続きは増減します。'
                f'着工・内装工事の前に管轄窓口へ事前相談することを強くおすすめします。</div>'
                f'<h2 style="font-family:var(--serif);font-size:21px;border-bottom:1px solid var(--rule);'
                f'padding-bottom:12px;margin-top:48px;letter-spacing:.03em">{n}が使える、受付中の補助金</h2>'
                + rows(rel) + '</div>'
                f'<section class="alt"><div class="wrap">' + sec_h("OTHER", "ほかの業種の許認可") + others + '</div></section>' + CTA)
        write(f"permit/{s}/index.html", layout(
            f"{n}の開業に必要な許認可・届出一覧｜{SITE_NAME}",
            f"{n}を始めるときに必要な許可・届出を、管轄窓口と処理期間の目安つきでまとめました。{desc}",
            body, f"permit/{s}/"))

# ================================================================ クロスページ（目的×県／業種×県）
def build_cross():
    for p in PURPOSE_LIST:
        base = purpose_recs(p)
        for s, n, en, pdesc in PREFS:
            rs = [r for r in base if n in r["prefs"]]
            if not rs: continue
            op = [r for r in rs if r["status"] == "open"]
            loc = [r for r in rs if not r["nationwide"]]
            sib = "".join(f'<a class="tag pref" style="margin:0 6px 6px 0;padding:8px 14px;font-size:13px" '
                          f'href="{U("purpose/"+P_SLUG[p]+"/"+s2+"/")}">{n2}</a>' for s2, n2, _, _ in PREFS if s2 != s)
            body = (f'<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>'
                    f'<a href="{U("purpose/")}">目的から探す</a><span>/</span>'
                    f'<a href="{U("purpose/"+P_SLUG[p]+"/")}">{esc(p)}</a><span>/</span>{n}</div></div>'
                    f'<section><div class="wrap">'
                    + sec_h("PURPOSE × PREFECTURE", n + "で" + esc(p) + "ときの補助金",
                            f"{n}の事業者が対象で、目的が「{p}」に該当する制度は {len(rs):,} 件。"
                            f"うち受付中 {len(op)} 件、{n}など地域が限定されたものが {len(loc)} 件です（{TODAY_JP}時点）。")
                    + rows(op[:25] or rs[:15])
                    + f'<div style="padding-top:30px"><a class="more" href="{U("search/")}?pref={n}&purpose={p}">'
                      f'この条件で検索画面を開く →</a></div>'
                    + '</div></section>'
                    f'<section class="alt"><div class="wrap">' + sec_h("OTHER PREFECTURES", "ほかの県で同じ目的を見る")
                    + sib + f'<div style="margin-top:22px"><a class="more" href="{U("pref/"+s+"/")}">'
                      f'{n}の補助金をすべて見る →</a></div></div></section>' + CTA)
            write(f"purpose/{P_SLUG[p]}/{s}/index.html", layout(
                f"{n}で{p}ときの補助金・助成金【受付中{len(op)}件】｜{SITE_NAME}",
                f"{n}の事業者が「{p}」目的で使える補助金・助成金を{len(rs)}件掲載。受付中{len(op)}件。",
                body, f"purpose/{P_SLUG[p]}/{s}/"))

    for p in INDUSTRY_LIST:
        base = industry_recs(p)
        for s, n, en, pdesc in PREFS:
            rs = [r for r in base if n in r["prefs"]]
            if len(rs) < 3: continue
            op = [r for r in rs if r["status"] == "open"]
            sib = "".join(f'<a class="tag pref" style="margin:0 6px 6px 0;padding:8px 14px;font-size:13px" '
                          f'href="{U("industry/"+I_SLUG[p]+"/"+s2+"/")}">{n2}</a>' for s2, n2, _, _ in PREFS if s2 != s)
            body = (f'<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>'
                    f'<a href="{U("industry/")}">業種から探す</a><span>/</span>'
                    f'<a href="{U("industry/"+I_SLUG[p]+"/")}">{esc(p)}</a><span>/</span>{n}</div></div>'
                    f'<section><div class="wrap">'
                    + sec_h("INDUSTRY × PREFECTURE", n + "の" + esc(p) + "が使える補助金",
                            f"{n}の事業者で、対象業種に「{p}」を含む制度は {len(rs):,} 件。"
                            f"うち受付中 {len(op)} 件です（{TODAY_JP}時点）。")
                    + rows(op[:25] or rs[:15])
                    + f'<div style="padding-top:30px"><a class="more" href="{U("search/")}?pref={n}&industry={p}">'
                      f'この条件で検索画面を開く →</a></div>'
                    + '</div></section>'
                    f'<section class="alt"><div class="wrap">' + sec_h("OTHER PREFECTURES", "ほかの県で同じ業種を見る")
                    + sib + '</div></section>' + CTA)
            write(f"industry/{I_SLUG[p]}/{s}/index.html", layout(
                f"{n}の{p}が使える補助金・助成金【受付中{len(op)}件】｜{SITE_NAME}",
                f"{n}の{p}を対象とする補助金・助成金を{len(rs)}件掲載。受付中{len(op)}件。",
                body, f"industry/{I_SLUG[p]}/{s}/"))

# ================================================================ AI相談
def ai_widget():
    return (f'<button class="ai-fab" id="ai-open" aria-label="補助金AI相談をひらく">'
            f'{svg_icon("chat")}<span class="tx">補助金AI相談<span class="sub">24時間・無料</span></span></button>'
            f'<div class="ai-panel" id="ai-panel" role="dialog" aria-label="補助金AI相談">'
            f'<div class="ai-hd"><div><b>補助金AI相談</b><small>九州・沖縄{N_ALL:,}件から探します</small></div>'
            f'<button id="ai-close" aria-label="閉じる">×</button></div>'
            f'<div class="ai-log" id="ai-log"></div>'
            f'<div class="ai-chips" id="ai-chips"></div>'
            f'<form class="ai-in" id="ai-form"><input id="ai-text" autocomplete="off" '
            f'placeholder="例：熊本の製造業で設備を入れたい"><button type="submit" aria-label="送信">'
            f'<svg viewBox="0 0 24 24"><path d="M4 12h15M13 6l6 6-6 6"/></svg></button></form>'
            f'<div class="ai-note">掲載データにもとづく自動応答です。最終的な可否は公募要領と窓口でご確認ください。</div>'
            f'</div>')

def build_ai():
    ex = ["熊本の製造業で設備を入れたい", "福岡で人を採用したい。使える助成金は？",
          "沖縄の飲食店、締切が近いものを教えて", "補助金はいつお金がもらえる？",
          "gBizIDって必要？", "個人事業主でも申請できる？"]
    chips = "".join(f'<button class="btn ghost sm" data-q="{esc(q)}" style="margin:0 8px 8px 0">{esc(q)}</button>' for q in ex)
    body = (f'<div class="wrap narrow"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>補助金AI相談</div>'
            f'<div class="detail-h"><span class="tag" style="border-color:var(--hi);color:var(--hi)">AI ASSISTANT</span>'
            f'<h1>補助金AI相談</h1>'
            f'<p style="font-size:15px;color:var(--ink-70);margin:0;line-height:1.95">'
            f'県・業種・やりたいことを文章で入れるだけで、九州・沖縄8県の掲載 {N_ALL:,} 件のなかから'
            f'条件に合う制度を探します。会員登録もメールアドレスも不要です。</p></div>'
            f'<h2 style="font-family:var(--serif);font-size:20px;letter-spacing:.03em">こう聞いてください</h2>'
            f'<div style="margin:18px 0 30px" id="ai-examples">{chips}</div>'
            f'<div class="note">右下のボタンからいつでも開けます。制度の詳細ページでは、'
            f'そのページの制度について質問することもできます。</div>'
            f'<h2 style="font-family:var(--serif);font-size:20px;letter-spacing:.03em;margin-top:40px">答えられること</h2>'
            f'<table class="prose" style="width:100%;border-collapse:collapse;font-size:13.5px">'
            f'<tr><th>種類</th><th>例</th></tr>'
            f'<tr><td>制度の絞り込み</td><td>県・業種・目的・従業員規模・締切・金額から候補を提示</td></tr>'
            f'<tr><td>締切の確認</td><td>「今月締切のもの」「あと30日以内」</td></tr>'
            f'<tr><td>申請実務の基本</td><td>後払いの仕組み、交付決定前の発注、gBizID、商工会窓口、必要書類</td></tr>'
            f'<tr><td>制度ガイドの案内</td><td>該当するガイド記事へ誘導</td></tr></table>'
            f'<div class="note warn" style="margin-top:34px">個別の採択可否や、金額の確約はできません。'
            f'要件の最終判断は各制度の公募要領と、所管窓口・専門家にご確認ください。</div>'
            f'<div style="height:50px"></div></div>{CTA}')
    write("ai/index.html", layout(f"補助金AI相談｜九州・沖縄の制度を文章で探す｜{SITE_NAME}",
        f"県・業種・やりたいことを文章で入力すると、九州・沖縄8県の補助金{N_ALL:,}件から条件に合う制度を探します。登録不要・24時間。",
        body, "ai/", data_js=True))

# ================================================================ 新着カルーセル
def newest(n=14):
    """受付開始日が新しい順。開始日が無いものは締切日で代替する。"""
    rs = [r for r in RECS if r["status"] in ("open", "soon")]
    rs.sort(key=lambda r: (r["start"] or r["end"] or ""), reverse=True)
    return rs[:n]

def carousel(rs, cid="car1"):
    cs = []
    for r in rs:
        left = (r["dl"] - TODAY).days if r["dl"] else None
        dl = ""
        if r["end"]:
            dl = f'<div class="cdl">締切 {jd(r["end"])}'
            if left is not None and 0 <= left <= 60:
                dl += f'<b>あと{left}日</b>'
            dl += '</div>'
        tags = badge(r)
        tags += ('<span class="tag">全国対象</span>' if r["nationwide"]
                 else "".join(f'<span class="tag pref">{p}</span>' for p in r["prefs"][:2]))
        cs.append(f'<a href="{U("subsidy/"+r["id"]+"/")}">'
                  f'<div class="cmeta">{tags}</div><h3>{esc(r["title"])}</h3>'
                  f'<div class="cfoot"><div class="camt"><small>補助上限</small>{yen(r["max"])}</div>{dl}</div></a>')
    return (f'<div class="carousel" data-carousel id="{cid}">'
            f'<div class="car-track">{"".join(cs)}</div>'
            f'<div class="car-bar"><i style="width:30%"></i></div></div>')

def car_nav():
    return ('<div class="car-nav">'
            '<button type="button" data-car="prev" aria-label="前へ">'
            '<svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg></button>'
            '<button type="button" data-car="next" aria-label="次へ">'
            '<svg viewBox="0 0 24 24"><path d="M9 5l7 7-7 7"/></svg></button></div>')

# ================================================================ 締切アラート（購読）
ALERT_MAIL = os.environ.get("KH_ALERT_MAIL", "info@avengerz-japan.com")
FEED_BASE = BASE_URL or "https://abengerz.github.io"

def _ics_fold(line):
    """RFC 5545 の 75 オクテット折り返し。マルチバイト文字の途中では折らない。"""
    if len(line.encode("utf-8")) <= 75:
        return line
    parts, buf, blen, cap = [], "", 0, 75
    for ch in line:
        cb = len(ch.encode("utf-8"))
        if blen + cb > cap:
            parts.append(buf)
            buf, blen, cap = ch, cb, 74   # 継続行は先頭の空白1オクテットぶん減る
        else:
            buf += ch
            blen += cb
    if buf:
        parts.append(buf)
    return "\r\n ".join(parts)


def _ics_escape(t):
    return (t or "").replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,").replace("\n", r"\n")

def build_feeds():
    """締切カレンダー(.ics)と新着フィード(.xml)。県別も出す。"""
    def ics(rs, name, title):
        L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//九州補助金ナビ//JP",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             f"X-WR-CALNAME:{_ics_escape(title)}",
             "X-WR-TIMEZONE:Asia/Tokyo",
             f"X-WR-CALDESC:{_ics_escape('九州・沖縄の補助金の締切。' + TODAY_JP + '時点の情報を毎朝更新しています。')}"]
        stamp = TODAY.strftime("%Y%m%dT000000Z")
        for r in rs:
            if not r["dl"]: continue
            d = r["dl"]
            L += ["BEGIN:VEVENT",
                  f"UID:{r['id']}@kyushu-hojokin",
                  f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
                  f"DTEND;VALUE=DATE:{(d + datetime.timedelta(days=1)).strftime('%Y%m%d')}",
                  f"SUMMARY:{_ics_escape('【締切】' + r['title'][:70])}",
                  f"DESCRIPTION:{_ics_escape('補助上限 ' + yen(r['max']) + ' / 補助率 ' + (r['rate'] or '要確認') + chr(10) + '対象：' + '、'.join(r['prefs'][:8]) + chr(10) + FEED_BASE + U('subsidy/' + r['id'] + '/'))}",
                  f"URL:{FEED_BASE}{U('subsidy/' + r['id'] + '/')}",
                  "TRANSP:TRANSPARENT",
                  "BEGIN:VALARM", "TRIGGER:-P14D", "ACTION:DISPLAY",
                  f"DESCRIPTION:{_ics_escape('締切2週間前：' + r['title'][:50])}", "END:VALARM",
                  "BEGIN:VALARM", "TRIGGER:-P3D", "ACTION:DISPLAY",
                  f"DESCRIPTION:{_ics_escape('締切3日前：' + r['title'][:50])}", "END:VALARM",
                  "END:VEVENT"]
        L.append("END:VCALENDAR")
        write(name, "\r\n".join(_ics_fold(x) for x in L) + "\r\n")

    def feed(rs, name, title, link):
        items = []
        for r in rs:
            u = FEED_BASE + U("subsidy/" + r["id"] + "/")
            desc = (f"補助上限 {yen(r['max'])} ／ 補助率 {r['rate'] or '要確認'} ／ "
                    f"締切 {jd_long(r['end'])} ／ 対象 {'、'.join(r['prefs'][:8])}")
            pub = ""
            d = dateobj(r["start"]) or r["dl"]
            if d: pub = f"<pubDate>{d.strftime('%a, %d %b %Y')} 09:00:00 +0900</pubDate>"
            items.append(f"<item><title>{esc(r['title'])}</title><link>{u}</link>"
                         f"<guid isPermaLink=\"true\">{u}</guid>"
                         f"<description>{esc(desc)}</description>{pub}</item>")
        write(name, '<?xml version="1.0" encoding="UTF-8"?>\n'
              '<rss version="2.0"><channel>'
              f'<title>{esc(title)}</title><link>{link}</link>'
              f'<description>{esc(title)}／国のオープンデータ(jGrants)を毎朝収集しています。</description>'
              f'<language>ja</language>'
              f'<lastBuildDate>{TODAY.strftime("%a, %d %b %Y")} 09:00:00 +0900</lastBuildDate>'
              + "".join(items) + "</channel></rss>")

    up = sorted([r for r in RECS if r["status"] in ("open", "soon") and r["dl"]], key=lambda r: r["dl"])
    ics(up, "alerts/deadline.ics", "九州・沖縄の補助金 締切カレンダー")
    feed(newest(50), "alerts/new.xml", "九州補助金ナビ 新着の補助金・助成金", FEED_BASE + U())
    for s2, n, en, _ in PREFS:
        ics([r for r in up if n in r["prefs"]], f"alerts/deadline-{s2}.ics", f"{n}の補助金 締切カレンダー")
        pr = [r for r in newest(200) if n in r["prefs"]][:50]
        feed(pr, f"alerts/new-{s2}.xml", f"{n}の新着補助金・助成金", FEED_BASE + U("pref/" + s2 + "/"))

def build_alerts():
    def webcal(u): return u.replace("https://", "webcal://").replace("http://", "webcal://")
    ics_all = FEED_BASE + U("alerts/deadline.ics")
    rss_all = FEED_BASE + U("alerts/new.xml")
    feeds = "".join(
        f'<a href="{FEED_BASE}{U("alerts/deadline-"+s2+".ics")}">{n}<span>カレンダー / RSS</span></a>'
        for s2, n, _, _ in PREFS)
    rssfeeds = "".join(
        f'<a href="{FEED_BASE}{U("alerts/new-"+s2+".xml")}">{n}<span>新着RSS</span></a>'
        for s2, n, _, _ in PREFS)
    pref_opts = "".join(f'<option value="{n}">{n}</option>' for _, n, _, _ in PREFS)
    pur_opts = "".join(f'<option value="{esc(p)}">{esc(p)}</option>' for p in PURPOSE_LIST)
    ind_opts = "".join(f'<option value="{esc(p)}">{esc(p)}</option>' for p in INDUSTRY_LIST)
    near = sorted([r for r in OPEN if r["dl"]], key=lambda r: r["dl"])[:10]

    body = f"""
<div class="wrap narrow"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>締切アラート</div>
<div class="detail-h">
  <span class="tag" style="border-color:var(--hi);color:var(--hi)">DEADLINE ALERT</span>
  <h1>締切アラート</h1>
  <p style="font-size:15px;color:var(--ink-70);margin:0;line-height:1.95">
  補助金でいちばん多い失敗は「知らないうちに締め切っていた」です。
  九州・沖縄8県の締切を、お使いのカレンダーに直接流し込めるようにしました。
  会員登録もメールアドレスの登録も要りません。実際に Google カレンダーで動作を確認しています。</p>
</div>

<div class="sub-grid">
  <div class="sub-card">
    <div class="sic">{svg_icon("calendar")}</div>
    <span class="badge">おすすめ</span>
    <h3>カレンダーに締切を流し込む</h3>
    <p>GoogleカレンダーやOutlookに購読登録すると、受付中の制度の締切が終日予定として自動で入ります。
    毎朝の自動更新にも追随し、<strong>公募が終わった制度は勝手に消えます</strong>。
    追加のあと一度だけ通知を設定すれば、締切前のリマインドが届きます（手順は下記）。</p>
    <a class="btn" href="{webcal(ics_all)}">カレンダーに追加</a>
    <a class="btn ghost sm" style="margin-left:8px" href="{ics_all}">.icsを直接開く</a>
  </div>
  <div class="sub-card">
    <div class="sic">{svg_icon("mega")}</div>
    <h3>新着をRSSで受け取る</h3>
    <p>新しく公募が始まった制度を配信します。SlackやFeedly、Teamsに流し込めば、
    担当者が見に来なくても新着が届きます。</p>
    <a class="btn ghost" href="{rss_all}">RSSを購読する</a>
  </div>
</div>

<h2 style="font-family:var(--serif);font-size:20px;letter-spacing:.03em;margin-top:44px">県別のカレンダー</h2>
<p style="font-size:13.5px;color:var(--ink-55);margin:10px 0 0">自社の県だけに絞ると、予定表が埋まりません。</p>
<div class="feed-list">{feeds}</div>

<h2 style="font-family:var(--serif);font-size:20px;letter-spacing:.03em;margin-top:40px">県別の新着RSS</h2>
<div class="feed-list">{rssfeeds}</div>

<h2 style="font-family:var(--serif);font-size:20px;letter-spacing:.03em;margin-top:44px">メールで受け取る</h2>
<p style="font-size:14px;color:var(--ink-70);line-height:1.95;margin:10px 0 20px">
条件を選んで送信すると、メールソフトが立ち上がります。そのまま送っていただければ、
新着と締切が近づいたタイミングでご連絡します。無料です。</p>
<form class="mailform" id="alertform">
  <div class="fr">
    <div><label>都道府県</label><select id="a-pref"><option value="">指定しない</option>{pref_opts}</select></div>
    <div><label>業種</label><select id="a-ind"><option value="">指定しない</option>{ind_opts}</select></div>
    <div><label>目的</label><select id="a-pur"><option value="">指定しない</option>{pur_opts}</select></div>
  </div>
  <div class="fr" style="grid-template-columns:1fr 1fr">
    <div><label>会社名・屋号</label><input id="a-co" placeholder="株式会社◯◯"></div>
    <div><label>お名前</label><input id="a-name" placeholder="山田 太郎"></div>
  </div>
  <button class="btn" type="submit">この条件でアラートを申し込む</button>
  <p style="font-size:11.5px;color:var(--ink-40);margin:14px 0 0;line-height:1.7">
  送信先：{ALERT_MAIL}　／　いただいた情報はアラートの配信にのみ使用します。
  配信停止はいつでも同アドレスへのご連絡で承ります。</p>
</form>

<h2 style="font-family:var(--serif);font-size:20px;letter-spacing:.03em;margin-top:48px">
Googleカレンダーでの通知設定（最初の一度だけ）</h2>
<p style="font-size:14px;color:var(--ink-70);line-height:1.95;margin:10px 0 18px">
Googleカレンダーは、購読したカレンダーに埋め込まれたリマインダーを使わない仕様です。
そのため追加した直後は予定が入るだけで通知は鳴りません。次の手順で一度だけ設定してください。2分で終わります。</p>
<ol style="font-size:14.5px;line-height:2.1">
  <li>Googleカレンダーの設定（右上の歯車 →「設定」）を開く</li>
  <li>左側の「他のカレンダーの設定」から<strong>九州・沖縄の補助金 締切カレンダー</strong>を選ぶ</li>
  <li><strong>「終日の予定の通知」</strong>で「通知を追加」→ <strong>2 週間前</strong>を指定</li>
  <li>もう一度「通知を追加」→ <strong>3 日前</strong>を指定</li>
</ol>
<div class="note">締切は終日の予定として登録しています。「予定の通知」ではなく
<strong>「終日の予定の通知」</strong>のほうに設定してください。こちらでないと鳴りません。</div>

<h3 style="font-family:var(--serif);font-size:17px;letter-spacing:.03em;margin-top:34px">
新着をメールで受け取る裏技</h3>
<p style="font-size:14px;color:var(--ink-70);line-height:1.95;margin:10px 0 0">
同じ設定画面の「その他の通知」で<strong>「新しい予定」を「メール」</strong>にしておくと、
本サイトが新しい公募を拾ってカレンダーに足したタイミングで、Googleからメールが届きます。
メールアドレスの登録も、こちらへの申し込みも要りません。<strong>新着メール通知がこれだけで完成します。</strong></p>

<div class="note" style="margin-top:30px">
Apple カレンダー（macOS / iPhone）と Outlook では、購読時に
「2週間前」「3日前」のリマインダーがそのまま効きます。追加の設定は要りません。<br>
なお、購読カレンダーの取り込み間隔はカレンダー側が決めており、
更新が反映されるまで数時間〜1日程度かかることがあります。</div>

<h2 style="font-family:var(--serif);font-size:20px;letter-spacing:.03em;margin-top:48px">いま締切が近いもの</h2>
</div>
<div class="wrap">{rows(near)}</div>
{CTA}"""
    write("alerts/index.html", layout(
        f"締切アラート｜九州・沖縄の補助金の締切をカレンダーに流し込む｜{SITE_NAME}",
        "九州・沖縄8県の補助金の締切を、Googleカレンダー等に購読登録できます。締切前のリマインドと新着メール通知の設定手順つき。新着RSSもご用意。登録不要・無料。",
        body, "alerts/", data_js=True))

# ================================================================ 市区町村の独自制度
def muni_rows(ms, start=1):
    if not ms:
        return ('<div class="empty">この自治体の制度はまだ収集できていません。'
                '公式サイトの案内をご確認ください。</div>')
    out = []
    for i, m in enumerate(ms, start):
        left = (m["dl"] - TODAY).days if m["dl"] else None
        tags = f'<span class="tag pref">{esc(m["muni"])}</span>'
        if m["dl"]:
            tags += (f'<span class="tag soon">締切まで{left}日</span>' if left is not None and left <= 30
                     else '<span class="tag open">受付中</span>')
        tags += '<span class="tag" style="border-color:var(--sky);color:var(--ai-2)">自治体独自</span>'
        if m.get("dept"):
            tags += f'<span class="tag">{esc(m["dept"])}</span>'
        amt = yen(m["max"]) if m["max"] else "公式ページ参照"
        rt = f'<div class="rt">補助率 {esc(m["rate"])}</div>' if m.get("rate") else ""
        dl = ""
        if m.get("deadline"):
            dl = f'<div class="dl">締切 {esc(m["deadline"])}'
            if left is not None and 0 <= left <= 60:
                dl += f' <b>あと{left}日</b>'
            dl += '</div>'
        out.append(f'<a class="row" href="{esc(m["url"])}" target="_blank" rel="nofollow noopener">'
                   f'<div class="no">{i:03d}</div>'
                   f'<div><h3>{esc(m["title"])}</h3><div class="meta">{tags}</div></div>'
                   f'<div class="amt"><small>補助上限</small>'
                   f'<span style="font-size:{"19px" if m["max"] else "13px"}">{amt}</span>{rt}{dl}</div></a>')
    return '<div class="rows">' + "".join(out) + '</div>'


MUNI_NOTE = ('<div class="note">この一覧は各自治体の公式サイトから自動収集したものです。'
             'タイトルをクリックすると公式ページが開きます。'
             '金額・補助率・締切はページ本文から機械的に読み取っているため、'
             '取得できていない項目や、最新でない場合があります。'
             '申請前にかならず公式ページと担当課でご確認ください。</div>')


def build_municipal():
    if not MUNI:
        return
    cities = sorted(MUNI_BY_CITY.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    items = [(U("muni/" + MUNI_SLUG[(p, m)] + "/"), "town", m, len(v)) for (p, m), v in cities]
    body = (f'<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>'
            f'市区町村の独自制度</div></div>'
            f'<section><div class="wrap">'
            + sec_h("MUNICIPAL", "市区町村・県の独自制度",
                    f"国のオープンデータ（jGrants）には登録されない、自治体が単独で行っている支援です。"
                    f"九州・沖縄の {N_MUNI_CITY} 自治体から {N_MUNI:,} 件を収集しました（{TODAY_JP}時点）。")
            + cards(items, "c4") + MUNI_NOTE + '</div></section>'
            f'<section class="alt"><div class="wrap">'
            + sec_h("ALL", "収集した制度（締切が近い順）") + muni_rows(MUNI[:40])
            + '</div></section>' + CTA)
    write("muni/index.html", layout(
        f"市区町村の独自補助金【{N_MUNI_CITY}自治体・{N_MUNI:,}件】｜{SITE_NAME}",
        f"福岡市・北九州市・久留米市・熊本市・那覇市など、九州・沖縄{N_MUNI_CITY}自治体が単独で実施している"
        f"補助金・助成金を{N_MUNI:,}件掲載。国のjGrantsには載らない地元の制度です。",
        body, "muni/"))

    for (pref, name), ms in cities:
        slug = MUNI_SLUG[(pref, name)]
        pslug = PREF_BY_NAME[pref][0]
        others = "".join(
            f'<a class="tag pref" style="margin:0 6px 6px 0;padding:8px 14px;font-size:13px" '
            f'href="{U("muni/" + MUNI_SLUG[(p2, m2)] + "/")}">{m2}</a>'
            for (p2, m2), _ in cities if p2 == pref and m2 != name)
        jg = [r for r in RECS if r["status"] == "open" and name in (r["title"] + r["area_detail"])]
        body = (f'<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>'
                f'<a href="{U("muni/")}">市区町村の独自制度</a><span>/</span>{name}</div></div>'
                f'<section><div class="wrap">'
                + sec_h("MUNICIPAL", name + "の独自補助金・助成金",
                        f"{name}が単独で実施している事業者向けの支援を、公式サイトから {len(ms)} 件収集しました"
                        f"（{TODAY_JP}時点）。国のjGrantsには登録されていない制度が中心です。")
                + muni_rows(ms) + MUNI_NOTE + '</div></section>'
                + (f'<section class="alt"><div class="wrap">'
                   + sec_h("JGRANTS", f"{name}が対象の、国のオープンデータ掲載制度")
                   + rows(jg[:10]) + '</div></section>' if jg else "")
                + ('<section><div class="wrap">' if jg else '<section class="alt"><div class="wrap">')
                + sec_h("NEARBY", f"{pref}のほかの自治体") + (others or "—")
                + f'<div style="margin-top:22px"><a class="more" href="{U("pref/" + pslug + "/")}">'
                  f'{pref}の補助金をすべて見る →</a></div></div></section>' + CTA)
        write(f"muni/{slug}/index.html", layout(
            f"{name}の補助金・助成金【独自制度{len(ms)}件】｜{SITE_NAME}",
            f"{name}が単独で実施している事業者向けの補助金・助成金を{len(ms)}件掲載。"
            f"公式ページへのリンク・担当課・締切つき。",
            body, f"muni/{slug}/"))
# ================================================================ 共有データ / OGP画像
def build_data():
    payload = [{"i":r["id"],"t":r["title"],"p":r["prefs"],"m":r["max"],"r":r["rate"],
                "d":(r["end"] or "")[:10],"s":(r["start"] or "")[:10],"st":r["status"],
                "u":r["purpose"],"g":r["industry"],"e":r["emp"],"n":r["inst"],
                "w":1 if r["nationwide"] else 0} for r in RECS]
    # 市区町村の独自制度も同じ形に揃えて載せる（x=1 は外部リンク）
    for m in MUNI:
        payload.append({"i": "", "t": m["title"], "p": [m["pref"]], "m": m["max"], "r": m.get("rate",""),
                        "d": (m["dl"].isoformat() if m["dl"] else ""), "s": "", "st": m["status"],
                        "u": "", "g": "", "e": "", "n": m["muni"] + (" " + m["dept"] if m.get("dept") else ""),
                        "w": 0, "x": 1, "h": m["url"], "mu": m["muni"]})
    write("assets/data.json", json.dumps(payload, ensure_ascii=False, separators=(",",":")))

_OG_FONTS = ["/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
             "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
             "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
def _parse_path(d, sc, ox, oy):
    polys = []
    for sub in d.split("M"):
        sub = sub.strip().rstrip("Z").strip()
        if not sub: continue
        pts = []
        for seg in sub.replace("L", " ").split():
            pass
        nums = [float(x) for x in re.findall(r"-?\d+\.?\d*", sub)]
        pts = [(nums[i]*sc+ox, nums[i+1]*sc+oy) for i in range(0, len(nums)-1, 2)]
        if len(pts) >= 3: polys.append(pts)
    return polys

def build_og():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        print("[warn] Pillow が無いため OGP 画像はスキップします"); return
    font = None
    for f in _OG_FONTS:
        if os.path.exists(f):
            try: font = f; break
            except Exception: pass
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), "#103F6E")
    dr = ImageDraw.Draw(img)
    for i in range(H):                       # 上から下への淡いグラデーション
        t = i / H
        dr.line([(0, i), (W, i)], fill=(int(16+22*t), int(63+34*t), int(110*1.0+40*t)))
    # 九州のシルエット
    sc = 1.28; ox, oy = 810, 70
    for slug in KMAP["main"]:
        if slug == "viewBox": continue
        for poly in _parse_path(KMAP["main"][slug], sc, ox, oy):
            dr.polygon(poly, fill="#4F9BD8")
    for poly in _parse_path(KMAP["okinawa"]["path"], sc*.8, 790, 500):
        dr.polygon(poly, fill="#4F9BD8")
    dr.rectangle([70, 96, 76, 534], fill="#8FD0F7")
    if font:
        try:
            f1 = ImageFont.truetype(font, 62); f2 = ImageFont.truetype(font, 30)
            f3 = ImageFont.truetype(font, 25); f4 = ImageFont.truetype(font, 21)
            dr.text((112, 128), "九州補助金ナビ", font=f1, fill="#FFFFFF")
            dr.text((114, 214), "KYUSHU & OKINAWA GRANTS", font=f4, fill="#A8D8F8")
            dr.text((112, 290), "九州・沖縄8県の事業者が使える", font=f2, fill="#E6F3FD")
            dr.text((112, 336), "補助金・助成金だけを集めました", font=f2, fill="#E6F3FD")
            dr.text((112, 432), f"掲載 {N_ALL:,} 件 ／ 受付中 {N_OPEN:,} 件", font=f3, fill="#8FD0F7")
            dr.text((112, 476), f"出典：デジタル庁 jGrants 公開API（{TODAY_JP}時点）", font=f4, fill="#8FB9DC")
        except Exception as e:
            print("[warn] OGP 文字描画に失敗:", e)
    else:
        print("[warn] 日本語フォントが見つからないため OGP は図版のみ")
    os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)
    img.save(os.path.join(OUT, "assets", "og.png"), "PNG", optimize=True)
    print("og.png written")

# ---------------------------------------------------------------- main
if __name__ == "__main__":
    if os.path.isdir(OUT): shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(OUT, "assets"))
    build_index(); build_prefs(); build_taxonomy(); build_search()
    build_guides(); build_audience(); build_permits(); build_ai()
    build_static(); build_subsidies(); build_cross()
    build_municipal(); build_alerts(); build_feeds(); build_data(); build_og(); build_meta()
    n = sum(len(f) for _, _, f in os.walk(OUT))
    print(f"built {n} files -> {OUT}")
    print(f"records={N_ALL} open={N_OPEN} local={N_LOCAL} purposes={len(PURPOSE_LIST)} "
          f"industries={len(INDUSTRY_LIST)} audiences={len(AUDIENCES)} permits={len(PERMITS)} "
          f"municipal={N_MUNI}/{N_MUNI_CITY}自治体")
