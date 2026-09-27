# -*- coding: utf-8 -*-
"""九州補助金ナビ — 静的サイトジェネレータ（jGrants公開APIの実データを使用）"""
import json, os, re, html, shutil, datetime, collections

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(ROOT, "site")
SITE_NAME = "九州補助金ナビ"
SITE_DESC = "福岡・佐賀・長崎・熊本・大分・宮崎・鹿児島・沖縄の補助金／助成金を、国のオープンデータから毎回まとめて検索。"
BASE_URL  = os.environ.get("KH_BASE_URL", "")     # 例: https://abengerz.github.io/kyushu-hojokin
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
idx = json.load(open(os.path.join(ROOT,"data","index.json"),encoding="utf-8"))
det = json.load(open(os.path.join(ROOT,"data","details.json"),encoding="utf-8"))

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

def pref_recs(name): return [r for r in RECS if name in r["prefs"]]
def purpose_recs(p): return [r for r in RECS if p in r["purpose"]]
def industry_recs(p): return [r for r in RECS if p in r["industry"]]

# ---------------------------------------------------------------- レイアウト
BASE = os.environ.get("KH_BASE", "")   # 例: /kyushu-hojokin
def U(p=""):
    p = p.lstrip("/")
    return (BASE + "/" + p) if p else (BASE + "/")

MARK = ('<svg class="mark" viewBox="0 0 32 32" aria-hidden="true">'
        '<rect x="12" y="1" width="9" height="7" fill="#12384F"/>'
        '<rect x="3" y="9.5" width="9" height="7" fill="#12384F" opacity=".78"/>'
        '<rect x="13" y="9.5" width="9" height="7" fill="#C3452B"/>'
        '<rect x="23" y="9.5" width="7" height="7" fill="#12384F" opacity=".55"/>'
        '<rect x="8" y="18" width="9" height="7" fill="#12384F" opacity=".78"/>'
        '<rect x="18" y="18" width="7" height="7" fill="#12384F" opacity=".55"/>'
        '<rect x="1" y="26.5" width="6" height="4.5" fill="#2E7C86"/>'
        '<rect x="9" y="26.5" width="8" height="4.5" fill="#12384F" opacity=".4"/></svg>')

NAV = [("補助金を探す","search/"),("県から探す","#pref"),("目的から探す","#purpose"),
       ("制度ガイド","guide/"),("専門家に相談","experts/")]

def layout(title, desc, body, path="", extra_head="", extra_js="", data_js=False, schema=""):
    canon = (BASE_URL + U(path)) if BASE_URL else ""
    nav = "".join(f'<a href="{U(h) if not h.startswith("#") else (U()+h)}">{t}</a>' for t,h in NAV)
    top_prefs = "".join(f'<a href="{U("pref/"+s+"/")}">{n}</a>' for s,n,_,_ in PREFS)
    dj = ""
    if data_js:
        payload = [{"i":r["id"],"t":r["title"],"p":r["prefs"],"m":r["max"],
                    "d":(r["end"] or "")[:10],"s":(r["start"] or "")[:10],"st":r["status"],
                    "u":r["purpose"],"g":r["industry"],"e":r["emp"],"n":r["inst"]} for r in RECS]
        dj = "<script>window.KH_DATA=" + json.dumps(payload, ensure_ascii=False, separators=(",",":")) + ";</script>"
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
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=Noto+Serif+JP:wght@600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{U('assets/style.css')}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%2312384F'/%3E%3Crect x='13' y='11' width='8' height='7' fill='%23C3452B'/%3E%3C/svg%3E">
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
      <li><a href="{U('deadline/')}">締切カレンダー</a></li>
      <li><a href="{U('purpose/')}">目的から探す</a></li>
      <li><a href="{U('industry/')}">業種から探す</a></li>
    </ul></div>
    <div><h4>県から探す</h4><ul>{''.join(f'<li><a href="{U("pref/"+s+"/")}">{n}の補助金</a></li>' for s,n,_,_ in PREFS[:4])}
      {''.join(f'<li><a href="{U("pref/"+s+"/")}">{n}の補助金</a></li>' for s,n,_,_ in PREFS[4:])}</ul></div>
    <div><h4>サイト情報</h4><ul>
      <li><a href="{U('guide/')}">制度ガイド</a></li>
      <li><a href="{U('experts/')}">専門家に相談</a></li>
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
<script>window.KH_BASE="{BASE}";</script>
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
    dl = f'<div class="dl">締切 {jd(r["end"])}</div>' if r["end"] else ""
    return (f'<a class="row" href="{U("subsidy/"+r["id"]+"/")}">'
            f'<div class="no">{i:03d}</div>'
            f'<div><h3>{esc(r["title"])}</h3><div class="meta">{metas}</div></div>'
            f'<div class="amt"><small>補助上限</small>{yen(r["max"])}{dl}</div></a>')

def rows(rs, start=1):
    if not rs: return '<div class="empty">該当する制度は見つかりませんでした。</div>'
    return '<div class="rows">' + "".join(row(r,i) for i,r in enumerate(rs,start)) + '</div>'

def sec_h(en, h2, p="", more=None):
    m = f'<a class="more" href="{more[1]}">{more[0]} →</a>' if more else ""
    return (f'<div class="sec-h"><div><span class="en">{en}</span><h2>{h2}</h2>'
            f'{f"<p>{p}</p>" if p else ""}</div>{m}</div>')

CTA = f"""<div class="cta"><div class="wrap narrow">
<h2>制度は見つかった。次は「通る申請書」をつくる番。</h2>
<p>九州・沖縄の行政書士・中小企業診断士・社労士・税理士と連携し、要件確認から事業計画書の作成・実績報告までを支援します。まずは無料の相談枠から。</p>
<div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap">
<a class="btn" href="{U('contact/')}">無料で相談する</a>
<a class="btn ghost" href="{U('experts/')}">提携専門家を見る</a>
</div></div></div>"""

# ---------------------------------------------------------------- タイルマップ
TILE = {"fukuoka":(112,4),"saga":(4,66),"oita":(220,66),
        "nagasaki":(4,128),"kumamoto":(112,128),"miyazaki":(220,128),
        "kagoshima":(112,190),"okinawa":(4,262)}
def tilemap():
    cells = []
    for s,n,en,_ in PREFS:
        x,y = TILE[s]; c = len(pref_recs(n)); o = len([r for r in pref_recs(n) if r["status"]=="open"])
        cells.append(
            f'<a class="cell{" oki" if s=="okinawa" else ""}" href="{U("pref/"+s+"/")}" aria-label="{n}の補助金 {c}件">'
            f'<rect x="{x}" y="{y}" width="100" height="54"/>'
            f'<text class="pn" x="{x+50}" y="{y+25}" text-anchor="middle">{n[:-1]}</text>'
            f'<text class="pc" x="{x+50}" y="{y+42}" text-anchor="middle">{c}件 / 受付中{o}</text></a>')
    return (f'<svg class="tilemap" viewBox="0 0 324 330" role="img" aria-label="九州・沖縄8県マップ">'
            f'<line x1="4" y1="256" x2="320" y2="256" stroke="rgba(23,26,28,.2)" stroke-dasharray="2 4"/>'
            f'<text x="320" y="250" text-anchor="end" font-size="9" letter-spacing="1.5" fill="rgba(23,26,28,.35)" '
            f'font-family="Noto Sans JP" font-weight="700">SOUTHWEST ISLANDS</text>'
            + "".join(cells) + '</svg>')

# ---------------------------------------------------------------- トップページ
def build_index():
    near = sorted([r for r in OPEN if r["dl"]], key=lambda r: r["dl"])[:8]
    big  = sorted(OPEN, key=lambda r: -(r["max"] or 0))[:6]
    purpose_chips = "".join(
        f'<a href="{U("purpose/"+P_SLUG[p]+"/")}">{esc(p)}<span class="c">{PURPOSES[p]}</span></a>'
        for p in PURPOSE_LIST[:12])
    industry_chips = "".join(
        f'<a href="{U("industry/"+I_SLUG[p]+"/")}">{esc(p)}<span class="c">{INDUSTRIES[p]}</span></a>'
        for p in INDUSTRY_LIST[:12])
    prefcards = "".join(
        f'<a href="{U("pref/"+s+"/")}"><div class="pn">{n}</div><div class="pr">{en}</div>'
        f'<div class="pd">{d}</div>'
        f'<div class="pnum">{len(pref_recs(n))}<em>件</em>　受付中 {len([r for r in pref_recs(n) if r["status"]=="open"])}<em>件</em></div></a>'
        for s,n,en,d in PREFS)

    sd_pref = "".join(f'<button data-v="{n}">{n[:-1]}</button>' for _,n,_,_ in PREFS)
    sd_purpose = "".join(f'<button data-v="{esc(p)}">{esc(p.replace("したい","").replace("を行いたい","").replace("がほしい",""))}</button>' for p in PURPOSE_LIST[:8])
    sd_size = "".join(f'<button data-v="{e}">{e}</button>' for e in ["5名以下","20名以下","50名以下","100名以下","300名以下"])

    guides_html = "".join(
        f'<a href="{U("guide/"+g["slug"]+"/")}"><article><div class="gk">{g["kicker"]}</div>'
        f'<h3>{esc(g["title"])}</h3><p>{esc(g["lead"])}</p></article></a>' for g in GUIDES[:6])

    body = f"""
<div class="hero"><div class="wrap">
  <div>
    <p class="eyebrow">KYUSHU &amp; OKINAWA / 8 PREFECTURES</p>
    <h1 class="hero-t"><span class="sm">福岡・佐賀・長崎・熊本・大分・宮崎・鹿児島・沖縄</span>
      九州の会社が使える<br>補助金だけを、<span class="u">まとめて</span>。</h1>
    <p class="lead">全国版の検索サイトは情報が多すぎて、自社に関係のない制度ばかり出てきます。{SITE_NAME}は九州・沖縄8県を対象とする制度だけを国のオープンデータから抽出し、受付中かどうか・いくらもらえるか・いつ締め切るかを最初の一画面で示します。</p>
    <div class="hero-cta">
      <a class="btn" href="{U('search/')}">{N_OPEN}件の受付中制度を見る</a>
      <a class="btn ghost" href="{U()}#shindan">30秒で自社向けを絞り込む</a>
    </div>
  </div>
  <div>{tilemap()}</div>
</div></div>

<div class="ledger"><div class="wrap">
  <div><div class="n">{N_ALL:,}<em>件</em></div><div class="k">九州・沖縄が対象の制度</div></div>
  <div><div class="n">{N_OPEN:,}<em>件</em></div><div class="k">いま受付中</div></div>
  <div><div class="n">8<em>県</em></div><div class="k">対応エリア</div></div>
  <div><div class="n">{yen(max([r['max'] for r in OPEN] or [0]))}</div><div class="k">受付中の最大補助額</div></div>
</div></div>

<section id="shindan" class="shindan"><div class="wrap">
  {sec_h("30 SECONDS","3つ選ぶだけ。自社が使える制度を絞り込む","県・目的・従業員規模を選ぶと、受付中の制度のなかから条件に合うものだけを表示します。メールアドレスの登録は不要です。")}
  <div class="q"><label>1 / 事業所のある県</label><div class="opts" data-key="pref">{sd_pref}</div></div>
  <div class="q"><label>2 / やりたいこと</label><div class="opts" data-key="purpose">{sd_purpose}</div></div>
  <div class="q"><label>3 / 従業員規模</label><div class="opts" data-key="size">{sd_size}</div></div>
  <div id="sd-out"></div>
</div></section>

<section><div class="wrap">
  {sec_h("CLOSING SOON","締切が近い、受付中の制度","締切日が早い順。申請書の準備には通常2〜4週間かかります。",("締切カレンダーを見る",U("deadline/")))}
  {rows(near)}
</div></section>

<section class="alt" id="pref"><div class="wrap">
  {sec_h("BY PREFECTURE","県から補助金・助成金を探す","国・独立行政法人・県が公募する制度のうち、その県の事業者が対象になるものを集約しています。")}
  <div class="prefgrid">{prefcards}</div>
</div></section>

<section id="purpose"><div class="wrap">
  {sec_h("BY PURPOSE","目的から探す","「設備を入れたい」「人を育てたい」など、やりたいことから逆引きします。",("すべて見る",U("purpose/")))}
  <div class="chips">{purpose_chips}</div>
</div></section>

<section class="alt" id="industry"><div class="wrap">
  {sec_h("BY INDUSTRY","業種から探す","日本標準産業分類ベース。自社の業種が対象に含まれる制度だけを表示します。",("すべて見る",U("industry/")))}
  <div class="chips">{industry_chips}</div>
</div></section>

<section><div class="wrap">
  {sec_h("MAX AMOUNT","補助額の大きい、受付中の制度","上限額が大きい順。自己負担と事務負担も同時に大きくなる点には注意してください。")}
  {rows(big)}
</div></section>

<section class="alt"><div class="wrap">
  {sec_h("GUIDES","制度ガイド","九州・沖縄の事業者がつまずきやすい論点を中心に解説します。",("すべてのガイドを見る",U("guide/")))}
  <div class="guides">{guides_html}</div>
</div></section>

<section><div class="wrap">
  {sec_h("EXPERTS","九州・沖縄の専門家が、申請まで伴走します","採択の可否を分けるのは制度選びより事業計画の書き方です。地場の士業と連携しています。",("専門家を見る",U("experts/")))}
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
        SITE_DESC + f"現在{N_OPEN}件が受付中（{TODAY_JP}時点）。",
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
        chips = "".join(f'<a href="{U("search/")}?pref={n}&purpose={p}">{esc(p)}<span class="c">{c}</span></a>' for p,c in pc.most_common(8))
        others = "".join(f'<a class="tag pref" style="margin:0 6px 6px 0;padding:8px 14px;font-size:13px" href="{U("pref/"+s2+"/")}">{n2}</a>'
                         for s2,n2,_,_ in PREFS if s2!=s)
        body = f"""
<div class="wrap">
<div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>県から探す<span>/</span>{n}</div>
</div>
<div class="hero"><div class="wrap">
 <div>
  <p class="eyebrow">{en} / {len(rs)} PROGRAMS</p>
  <h1 class="hero-t">{n}の<br><span class="u">補助金・助成金</span>一覧</h1>
  <p class="lead">{d}<br>{n}の事業者が対象になる制度を、国のオープンデータから{len(rs):,}件収集しました。うち{len(op)}件が現在受付中です（{TODAY_JP}時点）。</p>
  <div class="hero-cta"><a class="btn" href="{U('search/')}?pref={n}">{n}の制度を検索する</a></div>
 </div>
 <div>{tilemap()}</div>
</div></div>
<div class="ledger"><div class="wrap">
 <div><div class="n">{len(rs):,}<em>件</em></div><div class="k">{n}が対象の制度</div></div>
 <div><div class="n">{len(op):,}<em>件</em></div><div class="k">いま受付中</div></div>
 <div><div class="n">{len(local):,}<em>件</em></div><div class="k">地域限定の制度</div></div>
 <div><div class="n">{yen(max([r['max'] for r in op] or [0]))}</div><div class="k">受付中の最大補助額</div></div>
</div></div>

<section><div class="wrap">
 {sec_h("LOCAL","{}に限定された、受付中の制度".format(n), "全国公募ではなく、地域が限定されている制度です。競争相手が少なく、通りやすい傾向があります。")}
 {rows(local[:20])}
</div></section>

<section class="alt"><div class="wrap">
 {sec_h("BY PURPOSE","{}で、目的から絞り込む".format(n))}
 <div class="chips">{chips}</div>
</div></section>

<section><div class="wrap">
 {sec_h("NATIONWIDE","{}の事業者も使える、全国公募の制度".format(n), "ものづくり補助金・持続化補助金など、全国どこからでも申請できる制度です。")}
 {rows(natl[:15])}
 <div style="padding-top:30px"><a class="more" href="{U('search/')}?pref={n}">{n}の全{len(rs):,}件を検索で見る →</a></div>
</div></section>

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
    chips = "".join(f'<a href="{U("purpose/"+P_SLUG[p]+"/")}">{esc(p)}<span class="c">{PURPOSES[p]}</span></a>' for p in PURPOSE_LIST)
    write("purpose/index.html", layout(f"目的から補助金を探す｜{SITE_NAME}",
        "設備投資、人材育成、販路拡大など、やりたいことから九州・沖縄の補助金を逆引きします。",
        f'<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>目的から探す</div></div>'
        f'<section><div class="wrap">{sec_h("BY PURPOSE","目的から補助金・助成金を探す","やりたいことを選ぶと、九州・沖縄8県が対象の制度だけが表示されます。")}'
        f'<div class="chips">{chips}</div></div></section>{CTA}', "purpose/"))
    for p in PURPOSE_LIST:
        rs = purpose_recs(p); op=[r for r in rs if r["status"]=="open"]
        pb = "".join(f'<a href="{U("search/")}?purpose={p}&pref={n}">{n}<span class="c">{len([r for r in rs if n in r["prefs"]])}</span></a>' for _,n,_,_ in PREFS)
        body = (f'<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>'
                f'<a href="{U("purpose/")}">目的から探す</a><span>/</span>{esc(p)}</div></div>'
                f'<section><div class="wrap">{sec_h("BY PURPOSE", esc(p)+"ときに使える補助金", f"九州・沖縄8県が対象の{len(rs):,}件から抽出。うち受付中{len(op)}件（{TODAY_JP}時点）。")}'
                f'{rows(op[:30] or rs[:20])}'
                f'<div style="padding-top:34px">{sec_h("BY PREFECTURE","県で絞り込む")}<div class="chips">{pb}</div></div>'
                f'</div></section>{CTA}')
        write(f"purpose/{P_SLUG[p]}/index.html", layout(
            f"{p}｜九州・沖縄の補助金{len(rs)}件【受付中{len(op)}件】｜{SITE_NAME}",
            f"「{p}」に該当する九州・沖縄の補助金・助成金を{len(rs)}件掲載。受付中{len(op)}件。", body, f"purpose/{P_SLUG[p]}/"))

    ichips = "".join(f'<a href="{U("industry/"+I_SLUG[p]+"/")}">{esc(p)}<span class="c">{INDUSTRIES[p]}</span></a>' for p in INDUSTRY_LIST)
    write("industry/index.html", layout(f"業種から補助金を探す｜{SITE_NAME}",
        "製造業・建設業・宿泊飲食・農林水産など、業種別に九州・沖縄の補助金を探せます。",
        f'<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>業種から探す</div></div>'
        f'<section><div class="wrap">{sec_h("BY INDUSTRY","業種から補助金・助成金を探す","日本標準産業分類にもとづく区分です。")}'
        f'<div class="chips">{ichips}</div></div></section>{CTA}', "industry/"))
    for p in INDUSTRY_LIST:
        rs = industry_recs(p); op=[r for r in rs if r["status"]=="open"]
        pb = "".join(f'<a href="{U("search/")}?industry={p}&pref={n}">{n}<span class="c">{len([r for r in rs if n in r["prefs"]])}</span></a>' for _,n,_,_ in PREFS)
        body = (f'<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>'
                f'<a href="{U("industry/")}">業種から探す</a><span>/</span>{esc(p)}</div></div>'
                f'<section><div class="wrap">{sec_h("BY INDUSTRY", esc(p)+"が使える補助金", f"九州・沖縄8県が対象で、{p}を対象業種に含む制度は{len(rs):,}件。うち受付中{len(op)}件。")}'
                f'{rows(op[:30] or rs[:20])}'
                f'<div style="padding-top:34px">{sec_h("BY PREFECTURE","県で絞り込む")}<div class="chips">{pb}</div></div>'
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
    cards = "".join(
        f'<a href="{U("guide/"+g["slug"]+"/")}"><article><div class="gk">{g["kicker"]}</div>'
        f'<h3>{esc(g["title"])}</h3><p>{esc(g["lead"])}</p></article></a>' for g in GUIDES)
    write("guide/index.html", layout(f"制度ガイド｜九州・沖縄の補助金の使い方｜{SITE_NAME}",
        "持続化補助金・ものづくり補助金・IT導入補助金など、九州・沖縄の事業者向けに制度の使い方と申請実務を解説します。",
        f'<div class="wrap"><div class="crumbs"><a href="{U()}">ホーム</a><span>/</span>制度ガイド</div></div>'
        f'<section><div class="wrap">{sec_h("GUIDES","制度ガイド","制度そのものの説明よりも、九州・沖縄の事業者が実際につまずく箇所を中心にまとめています。")}'
        f'<div class="guides">{cards}</div></div></section>{CTA}', "guide/"))
    for i,g in enumerate(GUIDES):
        others = "".join(
            f'<a href="{U("guide/"+x["slug"]+"/")}"><article><div class="gk">{x["kicker"]}</div>'
            f'<h3>{esc(x["title"])}</h3><p>{esc(x["lead"])}</p></article></a>'
            for x in (GUIDES[i+1:]+GUIDES[:i])[:3])
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
    page("experts","専門家に相談する",
         "九州・沖縄の行政書士・中小企業診断士・社会保険労務士・税理士と連携し、補助金の申請を支援します。",
         f"""
<p>補助金で結果を分けるのは、制度選びよりも<strong>事業計画の書き方と、期日の管理</strong>です。{SITE_NAME}では、九州・沖縄各県の士業と連携し、要件の確認から申請書の作成、採択後の実績報告までを支援しています。</p>
<h2>相談できること</h2>
<table><tr><th>段階</th><th>支援内容</th></tr>
<tr><td>制度選び</td><td>自社の投資計画に対して、どの制度が最も有利か。併用の可否</td></tr>
<tr><td>要件確認</td><td>従業員数・業種・資本金・賃上げ要件などの適合判定</td></tr>
<tr><td>申請書作成</td><td>事業計画書、収支計画、加点要件の取得</td></tr>
<tr><td>資金繰り</td><td>後払いを前提としたつなぎ資金、金融機関との調整</td></tr>
<tr><td>採択後</td><td>交付申請、実績報告、証憑整備、事業化状況報告</td></tr></table>
<h2>提携している専門家（分野・エリア）</h2>
<div class="experts" style="margin:24px 0">{exp}</div>
<div class="note">本ページは提携分野の一覧です。個別の事務所名・料金は、ご相談内容をうかがったうえでご案内します。着手金が発生する場合は、必ず事前にお見積りを提示します。</div>
<h2>相談の流れ</h2>
<ol><li>お問い合わせフォームから、県・業種・やりたいことを送信</li>
<li>2営業日以内に、候補となる制度と概算のスケジュールを返信</li>
<li>必要に応じて、担当する専門家をご紹介</li></ol>
<p><a class="btn" href="{U('contact/')}">無料で相談する</a></p>
""","専門家に相談")

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
<tr><td>九州・沖縄8県が対象の制度</td><td>{N_ALL:,} 件</td></tr>
<tr><td>うち受付中</td><td>{N_OPEN:,} 件</td></tr>
<tr><td>最終更新</td><td>{TODAY_JP}</td></tr></table>
""","運営について")

    page("contact","お問い合わせ",
         "九州補助金ナビへのお問い合わせ・補助金の無料相談はこちらから。",
         f"""
<p>補助金の相談、掲載内容の訂正、取材・提携のご依頼はこちらからお願いします。</p>
<h2>補助金の無料相談</h2>
<p>以下をお知らせいただくと、回答が早くなります。</p>
<ol><li>事業所のある県・市町村</li><li>業種</li><li>従業員数</li><li>やりたいこと（設備を入れたい／人を採りたい／販路を広げたい　など）</li><li>想定している投資額と時期</li></ol>
<p style="margin-top:28px"><a class="btn" href="mailto:info@example.com?subject=%E8%A3%9C%E5%8A%A9%E9%87%91%E3%81%AE%E7%9B%B8%E8%AB%87">メールで相談する</a></p>
<div class="note">※ 公開デモのため、送信先メールアドレスは仮置きです。本番運用時に実際の連絡先／フォームへ差し替えてください。</div>
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
    urls = ["", "search/", "deadline/", "guide/", "purpose/", "industry/", "experts/", "about/", "contact/", "privacy/", "terms/"]
    urls += [f"pref/{s}/" for s,_,_,_ in PREFS]
    urls += [f"guide/{g['slug']}/" for g in GUIDES]
    urls += [f"purpose/{P_SLUG[p]}/" for p in PURPOSE_LIST]
    urls += [f"industry/{I_SLUG[p]}/" for p in INDUSTRY_LIST]
    urls += [f"subsidy/{r['id']}/" for r in RECS]
    root = BASE_URL or ""
    body = "".join(f"<url><loc>{root}{U(u)}</loc><lastmod>{TODAY}</lastmod></url>" for u in urls)
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+body+"</urlset>")
    write("robots.txt", f"User-agent: *\nAllow: /\n" + (f"Sitemap: {root}{U('sitemap.xml')}\n" if root else ""))
    write(".nojekyll", "")

# ---------------------------------------------------------------- main
if __name__ == "__main__":
    if os.path.isdir(OUT): shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copytree(os.path.join(ROOT,"assets"), os.path.join(OUT,"assets"))
    build_index(); build_prefs(); build_taxonomy(); build_search()
    build_guides(); build_static(); build_subsidies(); build_meta()
    n = sum(len(f) for _,_,f in os.walk(OUT))
    print(f"built {n} files -> {OUT}")
    print(f"records={N_ALL} open={N_OPEN} purposes={len(PURPOSE_LIST)} industries={len(INDUSTRY_LIST)}")
