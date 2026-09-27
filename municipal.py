# -*- coding: utf-8 -*-
"""九州・沖縄の自治体サイトから、事業者向けの補助金・助成金ページを収集する。

jGrants には市区町村の独自制度がほとんど登録されていないため、一次情報である
自治体サイトを直接巡回する。やっていることは検索エンジンと同じで、

  ・ページのタイトル
  ・金額／補助率／締切などの事実データ
  ・公式ページへのリンク

だけを取得する。本文の複製はしない。robots.txt を尊重し、1ホストあたり
1秒に1リクエスト以下に抑える。取得済みURLはキャッシュするので再実行は軽い。

使い方:
    python3 municipal.py              # 全自治体
    python3 municipal.py 久留米市 都城市   # 指定した自治体だけ
"""
import datetime, gzip, html, json, os, re, sys, threading, time
import urllib.error, urllib.parse, urllib.request

CACHE_LOCK = threading.Lock()


def save_json(path, obj, indent=None):
    """書き込み途中で落ちてもファイルを壊さないよう、一時ファイル経由で置き換える。"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        if indent:
            json.dump(obj, f, ensure_ascii=False, indent=indent)
        else:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)

ROOT = os.path.dirname(os.path.abspath(__file__))
UA = ("Mozilla/5.0 (compatible; kyushu-hojokin-bot/1.0; "
      "+https://abengerz.github.io/kyushu-hojokin/)")
DELAY = float(os.environ.get("MUNI_DELAY", "0.8"))     # 1ホストあたりの待ち時間（秒）
MAX_PAGES = int(os.environ.get("MUNI_MAX_PAGES", "320"))  # 1自治体あたりの上限
MAX_DEPTH = int(os.environ.get("MUNI_MAX_DEPTH", "2"))

# ---- 対象自治体（トップページだけ指定すれば、事業者向けセクションは自動発見する）----
PREF_SITES = [
 ("福岡県", "福岡県", "https://www.pref.fukuoka.lg.jp/"),
 ("佐賀県", "佐賀県", "https://www.pref.saga.lg.jp/"),
 ("長崎県", "長崎県", "https://www.pref.nagasaki.jp/"),
 ("熊本県", "熊本県", "https://www.pref.kumamoto.jp/"),
 ("大分県", "大分県", "https://www.pref.oita.jp/"),
 ("宮崎県", "宮崎県", "https://www.pref.miyazaki.lg.jp/"),
 ("鹿児島県", "鹿児島県", "https://www.pref.kagoshima.jp/"),
 ("沖縄県", "沖縄県", "https://www.pref.okinawa.jp/"),
]


# Wikidata の登録URLが英語版サイト等で使えないもの
SITE_OVERRIDE = {
    "平戸市": "https://www.city.hirado.nagasaki.jp/",
}


def load_sites():
    """data/municipalities.json（Wikidata由来・九州沖縄276市町村）＋8県。"""
    fp = os.path.join(ROOT, "data", "municipalities.json")
    sites = list(PREF_SITES)
    if os.path.exists(fp):
        for m in json.load(open(fp, encoding="utf-8")):
            url = SITE_OVERRIDE.get(m["muni"], m.get("site"))
            if url:
                sites.append((m["pref"], m["muni"], url))
    return sites


SITES = load_sites()

ENTRY_RE = re.compile(r"事業者|産業|ビジネス|商工|企業|しごと|仕事|農林|水産|観光|創業|起業|雇用|就労")
HIT_RE = re.compile(r"補助金|助成金|支援金|奨励金|給付金|利子補給|補助事業|支援事業|補助制度|助成制度|支援制度")
# 制度そのものではないページ（結果発表・入札・お知らせ）や、終了済みのものは除く
DROP_RE = re.compile(
    r"公募を終了|募集を終了|受付を終了|受付終了|募集終了|申請受付は終了|終了しました|"
    r"採択結果|選定結果|審査結果|交付決定|結果について|結果の公表|一次公募の結果|"
    r"企画提案|プロポーザル|業務委託|入札|見積(?:合わせ|依頼)|指名competitive|"
    r"要望調査|意向調査|アンケート|説明会|セミナー|研修会の開催|相談会|"
    r"法の改正|法改正|改正されました|創設されました|お知らせ$|ご案内$|について$|"
    r"報告記事|質問と回答|Ｑ＆Ａ|Q&A|よくある質問|見直し|交付要綱|実施要領|取扱要領|"
    r"様式|記入例|手引き|過去の|平成\d+年度|一覧表|実績|検証|評価結果|"
    r"ガイドライン|適正化|交付規則|条例|規程|基本方針|パブリックコメント")

# 事業者向けでないもの（個人・世帯向けの福祉／医療）は除く
NG_RE = re.compile(r"予防接種|健診|検診|医療費|不妊|妊婦|乳幼児|就学|奨学|入学|通学|介護保険料|後期高齢|"
                   r"生活保護|障害年金|ひとり親|児童扶養|保育料|療育|自立支援|住宅リフォーム|住まい|"
                   r"アスリート|スポーツ少年|結婚新生活|移住支援金|生活困窮|高齢者|敬老|"
                   r"出産|子育て応援|医療的ケア|訪問介護|看護小規模|居宅介護|認知症|"
                   r"マンション|浄化槽|生垣|ブロック塀|チャイルドシート|不登校|"
                   r"障害者|障がい|相談支援事業所|移動支援|日中一時|放課後等デイ|"
                   r"予防接種|健康診査|がん検診|骨髄|献血|ワクチン")
SKIP_EXT = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|zip|jpe?g|png|gif|svg|mp4|csv)(\?|$)", re.I)


def fetch(url, timeout=25, tries=3):
    """並列実行では一時的な接続失敗が起きるので、少し待って retry する。"""
    for i in range(tries):
        try:
            return _fetch_once(url, timeout)
        except urllib.error.HTTPError:
            raise                      # 404 等は retry しない
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(1.2 * (i + 1))


def _fetch_once(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(1_500_000)
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        ct = r.headers.get("Content-Type", "")
        enc = None
        m = re.search(r"charset=([\w-]+)", ct, re.I)
        if m: enc = m.group(1)
        if not enc:
            m = re.search(rb'charset=["\']?([\w-]+)', raw[:3000], re.I)
            if m: enc = m.group(1).decode("ascii", "ignore")
        for e in filter(None, [enc, "utf-8", "cp932", "euc-jp"]):
            try:
                return r.geturl(), raw.decode(e)
            except (UnicodeDecodeError, LookupError):
                continue
        return r.geturl(), raw.decode("utf-8", "ignore")


def robots_disallow(base):
    try:
        _, t = fetch(urllib.parse.urljoin(base, "/robots.txt"), 15)
        if "<html" in t[:400].lower():
            return []
        rules, active = [], False
        for line in t.splitlines():
            line = line.split("#")[0].strip()
            if not line: continue
            k, _, v = line.partition(":")
            k, v = k.strip().lower(), v.strip()
            if k == "user-agent":
                active = v == "*"
            elif k == "disallow" and active and v:
                rules.append(v)
        return rules
    except Exception:
        return []


def blocked(path, rules):
    return any(path.startswith(r) for r in rules)


def text_of(h):
    h = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", h, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def page_h1(h):
    m = re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S | re.I)
    if not m: return ""
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1)))).strip()[:120]


def page_title(h):
    """<title> から制度名らしい部分を取り出す。

    自治体サイトは「久留米市：制度名」と「鹿児島県／制度名」の両方があり、
    区切りの先頭を採ると自治体名だけになってしまう。最も長い断片を採る。
    """
    m = re.search(r"<title[^>]*>(.*?)</title>", h, re.S | re.I)
    if not m: return ""
    t = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1)))).strip()
    parts = [x.strip() for x in re.split(r"\s*[|｜/／：:–—]\s*|\s+-\s+", t) if x.strip()]
    if len(parts) <= 1:
        return t
    return max(parts, key=len)


Z2H = str.maketrans("０１２３４５６７８９．，", "0123456789.,")
UNIT = {"億円": 100_000_000, "万円": 10_000, "千円": 1_000, "円": 1}

# 金額：キーワードが前に来る書き方と、後ろに来る書き方の両方を拾う
A_PRE = re.compile(r"(?:上限|限度額|補助上限|助成上限|補助額|助成額|交付額|給付額|奨励金額|"
                   r"補助金額|助成金額|支給額|最大)[^。\n]{0,16}?"
                   r"([0-9０-９][0-9０-９,，]*(?:\.[0-9]+)?)\s*(億円|万円|千円|円)")
A_POST = re.compile(r"([0-9０-９][0-9０-９,，]*(?:\.[0-9]+)?)\s*(億円|万円|千円|円)"
                    r"[^。\n]{0,8}?(?:を上限|が上限|を限度|以内|まで)")
# 「100万円以上の経費」のような下限・条件は金額として採らない
A_BAD = re.compile(r"(?:以上|超|未満|収入|売上|所得|資本金|人口|世帯)")

RATE = re.compile(r"(?:補助率|助成率|補助割合|交付率)[^。\n]{0,12}?"
                  r"([0-9０-９]{1,2}\s*/\s*[0-9０-９]{1,2}|[0-9０-９]{1,3}分の[0-9０-９]{1,3}|"
                  r"[0-9０-９]{1,3}\s*[%％]|定額|全額)")
RATE2 = re.compile(r"(?:経費の|費用の|額の|対象経費に)\s*"
                   r"([0-9０-９]{1,3}分の[0-9０-９]{1,3}|[0-9０-９]{1,2}\s*/\s*[0-9０-９]{1,2}|"
                   r"[0-9０-９]{1,3}\s*[%％])")
RATE3 = re.compile(r"([0-9０-９]{1,3}分の[0-9０-９]{1,3}|[0-9０-９]{1,2}\s*/\s*[0-9０-９]{1,2}|"
                   r"[0-9０-９]{1,3}\s*[%％])\s*(?:以内|相当|を補助|を助成|を交付)")

_D_WA = r"令和\s*([0-9０-９元]{1,2})\s*年\s*([0-9０-９]{1,2})\s*月\s*([0-9０-９]{1,2})\s*日"
_D_AD = r"(20[0-9０-９]{2})\s*年\s*([0-9０-９]{1,2})\s*月\s*([0-9０-９]{1,2})\s*日"
_AFTER = r"[^。\n]{0,16}?(?:まで|必着|締切|締め切|消印|期限)"
_BEFORE = r"(?:締切|締め切|申請期限|提出期限|受付期限|応募期限|期限|まで)[^。\n]{0,12}?"
DEAD_PATS = [(re.compile(_D_WA + _AFTER), True), (re.compile(_D_AD + _AFTER), False),
             (re.compile(_BEFORE + "(?:" + _D_WA + ")"), True),
             (re.compile(_BEFORE + "(?:" + _D_AD + ")"), False)]
# 「令和8年4月1日から令和9年3月31日まで」は後ろの日付が締切
DEAD_RANGE = re.compile(_D_WA + r"[^。\n]{0,4}?から[^。\n]{0,4}?" + _D_WA)

CONTACT = re.compile(r"(?:お問い合わせ|問い合わせ|問合せ|担当)[^。\n]{0,6}?"
                     r"([一-龥ぁ-んァ-ヶ]{2,12}(?:課|室|部|センター|局|係))")


def to_yen(num, unit):
    try:
        v = float(str(num).translate(Z2H).replace(",", ""))
    except ValueError:
        return 0
    return int(v * UNIT[unit])


def find_amount(t):
    """キーワードに紐づく最初の金額を採る。最大値を採ると対象経費の下限を拾ってしまう。"""
    m = A_PRE.search(t)
    if m:
        v = to_yen(m.group(1), m.group(2))
        if v: return v
    for m in A_POST.finditer(t):
        if A_BAD.search(t[max(0, m.start() - 18):m.start()]): continue
        v = to_yen(m.group(1), m.group(2))
        if v: return v
    return 0


def find_rate(t):
    m = RATE.search(t) or RATE2.search(t) or RATE3.search(t)
    return re.sub(r"\s+", "", m.group(1).translate(Z2H)) if m else ""


def _mk_date(y, mo, da, wareki):
    y = str(y).translate(Z2H)
    y = 2018 + (1 if y == "元" else int(y)) if wareki else int(y)
    try:
        d = datetime.date(y, int(str(mo).translate(Z2H)), int(str(da).translate(Z2H)))
    except ValueError:
        return ""
    return f"令和{d.year - 2018}年{d.month}月{d.day}日"


def find_deadline(t):
    m = DEAD_RANGE.search(t)
    if m:
        s2 = _mk_date(m.group(4), m.group(5), m.group(6), True)
        if s2: return s2
    for pat, wareki in DEAD_PATS:
        m = pat.search(t)
        if m:
            s2 = _mk_date(m.group(1), m.group(2), m.group(3), wareki)
            if s2: return s2
    return ""


HUB_TITLES = {"支援制度", "補助金", "助成金", "補助金・助成金", "各種支援制度", "支援策",
              "補助金一覧", "助成制度", "支援制度一覧", "補助制度", "事業者向け支援", "支援事業",
              "中小企業支援", "補助金等", "補助金・助成金一覧", "支援金", "給付金",
              "補助金を受けたい", "助成金を受けたい", "支援制度を知りたい"}
# 一覧・目次ページ、および国の制度をそのまま転載しているだけのページは除く
HUB_RE = re.compile(r"一覧|の紹介$|各種支援|まとめ$|リンク集")
RELAY_RE = re.compile(r"【(厚生労働省|経済産業省|中小企業庁|国土交通省|農林水産省|環境省|内閣府)】|"
                      r"^国の(補助金|支援)")

def clean_title(t, muni):
    """「久留米市：〜」「福岡市 〜」のような自治体名の接頭辞・接尾辞を落とす。"""
    t = t.replace("\u3000", " ").strip()
    for name in (muni, muni + "役所", muni + "ホームページ"):
        t = re.sub(r"^\s*" + re.escape(name) + r"\s*[：:｜|／/、　\-–—]*\s*", "", t).strip()
        t = re.sub(r"\s*[｜|／/・]\s*" + re.escape(name) + r"\s*$", "", t).strip()
    t = re.sub(r"\s{2,}", " ", t)
    # 「大分市への企業立地…」から接頭辞を剥がすと「への企業立地…」になってしまう
    if re.match(r"^[へにをはがのでとも、。]", t):
        return ""
    return t


def is_hub(t):
    return (t in HUB_TITLES or len(t) < 8 or bool(HUB_RE.search(t))
            or bool(RELAY_RE.search(t)) or bool(DROP_RE.search(t)))


def extract(url, h):
    body = text_of(h)
    rec = {"url": url, "title": page_title(h), "max": 0, "rate": "", "deadline": "", "dept": "",
           "excerpt": ""}
    rec["max"] = find_amount(body)
    rec["rate"] = find_rate(body)
    rec["deadline"] = find_deadline(body)
    m = CONTACT.search(body)
    if m: rec["dept"] = m.group(1)
    # 事実の要約だけを短く保持する（本文の複製はしない）
    for m in re.finditer(r"(?:目的|概要|趣旨|対象)[^。]{6,90}。", body):
        rec["excerpt"] = m.group(0)[:110]
        break
    if not rec["excerpt"]:
        rec["excerpt"] = body[:110]
    return rec


def harvest(pref, name, base, cache):
    host = urllib.parse.urlparse(base).netloc
    rules = robots_disallow(base)
    try:
        start, home = fetch(base, 30)
    except Exception as e:
        print(f"  ! {name}: トップ取得失敗 {type(e).__name__}", flush=True)
        return []

    def links(src_url, h):
        out = []
        for m in re.finditer(r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', h, re.S | re.I):
            href, txt = m.group(1), html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2)))).strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")): continue
            u = urllib.parse.urljoin(src_url, href).split("#")[0]
            p = urllib.parse.urlparse(u)
            if p.netloc != host or p.scheme not in ("http", "https"): continue
            if SKIP_EXT.search(p.path) or blocked(p.path, rules): continue
            out.append((u, txt))
        return out

    all_links = links(start, home)
    seeds = [u for u, t in all_links if ENTRY_RE.search(t) and len(t) <= 30]
    # リンク文字が画像のみのサイト向けに、title / alt 属性も拾う
    if len(seeds) < 2:
        for m in re.finditer(r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>', home, re.I):
            tag = m.group(0)
            at = " ".join(re.findall(r'(?:title|alt|aria-label)=["\']([^"\']{2,30})["\']', tag, re.I))
            if at and ENTRY_RE.search(at):
                u2 = urllib.parse.urljoin(start, m.group(1)).split("#")[0]
                if urllib.parse.urlparse(u2).netloc == host:
                    seeds.append(u2)
    seeds = list(dict.fromkeys(seeds))
    # 入口が少ない小規模自治体は、事業者向けの区画が浅く名前も揃っていない。
    # 2件以下ならサイト全体を対象にする（タイトルで絞るので精度は保てる）。
    whole_site = len(seeds) < 3
    if not seeds:
        seeds = [start]
    if whole_site and start not in seeds:
        seeds = [start] + seeds
    # 巡回はシード配下に限定する。これをしないと住宅・福祉など無関係な区画へ流れ出す
    prefixes = []
    for u in seeds:
        path = urllib.parse.urlparse(u).path
        prefixes.append(path if path.endswith("/") else path.rsplit("/", 1)[0] + "/")
    prefixes = sorted(set(p for p in prefixes if len(p) > 1))
    if whole_site or not prefixes:
        prefixes = ["/"]

    def in_scope(u):
        p = urllib.parse.urlparse(u).path
        return any(p.startswith(x) for x in prefixes)

    seen, queue, found, fetched = set([start]), [], [], 0
    for u in seeds:
        queue.append((u, 0)); seen.add(u)
    print(f"  {name}: 入口 {len(queue)}件 / 巡回範囲 {len(prefixes)}区画", flush=True)

    while queue and fetched < MAX_PAGES:
        u, d = queue.pop(0)
        with CACHE_LOCK:
            cached = cache.get(u)
        h = None
        if cached is not None and "l" in cached:
            title = cached.get("t", "")
            outlinks = [tuple(x) for x in cached.get("l", [])]
        else:
            try:
                fin, h = fetch(u, 20)
                fetched += 1
                time.sleep(DELAY)
            except Exception:
                with CACHE_LOCK:
                    cache[u] = {"t": ""}
                continue
            title = page_title(h)
            h1 = page_h1(h)
            # <title> が「鹿児島県」のようにサイト名だけのサイトが実在する。
            # その場合と、見出しのほうが制度名を表している場合は h1 を採る。
            if h1 and (title in ("", name) or len(title) <= max(4, len(name))
                       or (not HIT_RE.search(title) and HIT_RE.search(h1))):
                title = h1
            outlinks = links(u, h)
            # 巡回に使うリンクを保存しておく（再実行を軽くするため）
            cache[u] = {"t": title,
                        "l": [[nu, tx[:16]] for nu, tx in outlinks
                              if in_scope(nu) or HIT_RE.search(tx)][:60]}

        if title and HIT_RE.search(title) and not NG_RE.search(title):
            if h is None:
                try:
                    _, h = fetch(u, 20); fetched += 1; time.sleep(DELAY)
                except Exception:
                    h = None
            if h is not None:
                rec = extract(u, h)
                rec["title"] = clean_title(rec["title"], name)
                if not is_hub(rec["title"]) and HIT_RE.search(rec["title"]) and not NG_RE.search(rec["title"]):
                    rec.update({"pref": pref, "muni": name})
                    found.append(rec)

        # 「補助金・支援」のような一覧ページに当たったら、深さ予算を戻して必ず配下へ降りる
        hub_of_interest = bool(title) and HIT_RE.search(title) and is_hub(clean_title(title, name))
        nd = 1 if hub_of_interest else d + 1
        if d < MAX_DEPTH or hub_of_interest:
            for nu, txt in outlinks:
                # 自治体サイトは一覧(/business/)と実体(/soshiki/)でパスが分かれることが多い。
                # 補助金らしいリンクテキストなら区画の外でも追いかける。
                if nu in seen or not (in_scope(nu) or HIT_RE.search(txt)): continue
                seen.add(nu)
                if HIT_RE.search(txt):
                    queue.insert(0, (nu, nd))
                else:
                    queue.append((nu, nd))

    # 同じ制度が複数URLで拾えることがあるので、情報量の多いほうを残す
    best = {}
    for r in found:
        k = r["title"]
        score = (r["max"] > 0) + bool(r["rate"]) + bool(r["deadline"]) + bool(r["dept"])
        if k not in best or score > best[k][0]:
            best[k] = (score, r)
    found = [v[1] for v in best.values()]
    print(f"  {name}: {fetched}ページ取得 → 制度 {len(found)}件", flush=True)
    return found


def main():
    only = set(sys.argv[1:])
    cpath = os.path.join(ROOT, "data", "muni_cache.json")
    cache = json.load(open(cpath, encoding="utf-8")) if os.path.exists(cpath) else {}
    opath = os.path.join(ROOT, "data", "municipal.json")
    all_recs = json.load(open(opath, encoding="utf-8")) if os.path.exists(opath) else []
    by_muni = {}
    for r in all_recs:
        by_muni.setdefault(r["muni"], []).append(r)

    targets = [s for s in SITES if not only or s[1] in only]
    workers = int(os.environ.get("MUNI_WORKERS", "4"))
    print(f"対象 {len(targets)} 自治体（{workers}並列 / 1サイトあたり{DELAY}秒間隔）", flush=True)
    import concurrent.futures as cf
    lock = threading.Lock()

    def run(site):
        pref, name, base = site
        try:
            return name, harvest(pref, name, base, cache)
        except Exception as e:
            print(f"  ! {name}: {type(e).__name__} {e}", flush=True)
            return name, []

    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for name, recs in ex.map(run, targets):
            with lock:
                if recs: by_muni[name] = recs
                out = [r for v in by_muni.values() for r in v]
                try:
                    save_json(opath, out, indent=1)
                    with CACHE_LOCK:
                        snapshot = dict(cache)
                    save_json(cpath, snapshot)
                except Exception as e:
                    print(f"  ! 保存に失敗: {type(e).__name__} {e}", flush=True)
    out = [r for v in by_muni.values() for r in v]
    print(f"\n合計 {len(out)}件 / {len(by_muni)}自治体 → data/municipal.json")


if __name__ == "__main__":
    main()
