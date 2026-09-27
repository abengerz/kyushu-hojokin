# -*- coding: utf-8 -*-
"""締切アラートの日次ダイジェスト。

data/index.json と data/details.json を読み、前回実行時からの
  ・新しく公募が始まった制度
  ・締切が 14 日以内に迫っている受付中の制度
を検出してメールで送る。

環境変数
  RESEND_API_KEY  … 設定されていれば Resend 経由で送信。無ければ本文を標準出力に出すだけ。
  ALERT_TO        … 宛先（既定 info@avengerz-japan.com）
  ALERT_FROM      … 差出人（既定 onboarding@resend.dev。独自ドメインは Resend 側で要認証）
  KH_BASE / KH_BASE_URL … リンクの組み立てに使用（build.py と同じ）
"""
import datetime, json, os, re, sys, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("KH_BASE", "").rstrip("/")
ORIGIN = os.environ.get("KH_BASE_URL", "https://abengerz.github.io").rstrip("/")
if BASE and ORIGIN.endswith(BASE):
    ORIGIN = ORIGIN[:-len(BASE)].rstrip("/")
SITE = ORIGIN + BASE + "/"
TO = os.environ.get("ALERT_TO", "info@avengerz-japan.com")
FROM = os.environ.get("ALERT_FROM", "九州補助金ナビ <onboarding@resend.dev>")
SOON_DAYS = int(os.environ.get("ALERT_SOON_DAYS", "14"))
TODAY = datetime.date.today()
PREFS = ["福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"]


def dateobj(s):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s or "")
    return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def yen(v):
    if not v:
        return "—"
    v = int(v)
    if v >= 100000000:
        return f"{v/100000000:.1f}".rstrip("0").rstrip(".") + "億円"
    if v >= 10000:
        return f"{round(v/10000):,}万円"
    return f"{v:,}円"


def load():
    idx = json.load(open(os.path.join(ROOT, "data", "index.json"), encoding="utf-8"))
    dp = os.path.join(ROOT, "data", "details.json")
    det = json.load(open(dp, encoding="utf-8")) if os.path.exists(dp) else {}
    recs = []
    for sid, b in idx.items():
        d = det.get(sid, {})
        areas = [a.strip() for a in (d.get("target_area_search") or b.get("target_area_search") or "").split("/") if a.strip()]
        kp = [a for a in areas if a in PREFS]
        if not kp:
            continue
        st = d.get("acceptance_start_datetime") or b.get("acceptance_start_datetime")
        en = d.get("acceptance_end_datetime") or b.get("acceptance_end_datetime")
        ds, de = dateobj(st), dateobj(en)
        status = "closed"
        if de and de >= TODAY:
            status = "open" if (not ds or ds <= TODAY) else "soon"
        elif not de and ds and ds <= TODAY:
            status = "open"
        recs.append({
            "id": sid,
            "title": (d.get("title") or b.get("title") or "").strip(),
            "prefs": kp,
            "nationwide": len([a for a in areas if a.endswith(("県", "府", "都", "道"))]) >= 40,
            "max": d.get("subsidy_max_limit") or b.get("subsidy_max_limit") or 0,
            "rate": d.get("subsidy_rate") or "",
            "dl": de, "start": ds, "status": status,
        })
    return recs


def main():
    recs = load()
    seen_path = os.path.join(ROOT, "data", "seen.json")
    first_run = not os.path.exists(seen_path)
    seen = set(json.load(open(seen_path, encoding="utf-8"))) if not first_run else set()

    live = [r for r in recs if r["status"] in ("open", "soon")]
    fresh = [r for r in live if r["id"] not in seen]
    near = sorted([r for r in recs if r["status"] == "open" and r["dl"]
                   and 0 <= (r["dl"] - TODAY).days <= SOON_DAYS],
                  key=lambda r: r["dl"])

    json.dump(sorted({r["id"] for r in recs}), open(seen_path, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))

    if first_run:
        print(f"[alert] 初回実行のため通知はスキップしました（{len(recs)}件を記録）")
        return 0
    if not fresh and not near:
        print("[alert] 新着・締切間近ともにありません。送信しません。")
        return 0

    def block(title, rs, note):
        if not rs:
            return ""
        h = (f'<h2 style="font:700 16px/1.6 sans-serif;color:#1A6DB5;margin:30px 0 4px">{title}'
             f'<span style="font-size:13px;color:#64748b"> （{len(rs)}件）</span></h2>'
             f'<p style="font:400 12px/1.7 sans-serif;color:#64748b;margin:0 0 14px">{note}</p>')
        for r in rs[:20]:
            left = (r["dl"] - TODAY).days if r["dl"] else None
            meta = ("全国対象" if r["nationwide"] else "・".join(r["prefs"][:4]))
            dl = ""
            if r["dl"]:
                dl = f'締切 {r["dl"].year}.{r["dl"].month:02d}.{r["dl"].day:02d}'
                if left is not None:
                    dl += f'（あと{left}日）' if left <= 30 else ""
            h += (f'<a href="{SITE}subsidy/{r["id"]}/" style="display:block;text-decoration:none;'
                  f'border:1px solid #e2e8f0;border-radius:8px;padding:13px 15px;margin-bottom:9px;background:#fff">'
                  f'<span style="font:700 14px/1.6 sans-serif;color:#0d1b2a;display:block;margin-bottom:6px">{r["title"]}</span>'
                  f'<span style="font:400 12px/1.6 sans-serif;color:#64748b">{meta}　補助上限 {yen(r["max"])}'
                  + (f'　補助率 {r["rate"]}' if r["rate"] else "") + (f'　{dl}' if dl else "") + '</span></a>')
        if len(rs) > 20:
            h += f'<p style="font:400 12px sans-serif;color:#64748b">ほか {len(rs)-20} 件</p>'
        return h

    subject = "【九州補助金ナビ】"
    bits = []
    if fresh: bits.append(f"新着{len(fresh)}件")
    if near: bits.append(f"締切{SOON_DAYS}日以内{len(near)}件")
    subject += "／".join(bits) + f"（{TODAY.month}月{TODAY.day}日）"

    html = ('<meta charset="utf-8">'
            f'<div style="background:#f4f9fe;padding:26px">'
            f'<div style="max-width:620px;margin:0 auto;background:#fff;border-radius:12px;padding:28px 26px 34px">'
            f'<div style="font:700 19px/1.4 serif;color:#1A6DB5">九州補助金ナビ</div>'
            f'<div style="font:600 10px/1.4 sans-serif;color:#94a3b8;letter-spacing:.2em;margin-top:5px">'
            f'DEADLINE ALERT / {TODAY.year}.{TODAY.month:02d}.{TODAY.day:02d}</div>'
            + block("新しく公募が始まった制度", fresh, "前回の確認以降に追加されたものです。準備期間が長いうちに着手できます。")
            + block(f"締切が{SOON_DAYS}日以内に迫っている制度", near, "申請書の作成には通常2〜4週間かかります。")
            + f'<p style="font:400 12px/1.8 sans-serif;color:#64748b;margin-top:28px;'
              f'border-top:1px solid #e2e8f0;padding-top:16px">'
              f'出典：デジタル庁 jGrants 公開API。補助率・上限額・締切は公募回ごとに改定されます。'
              f'申請前に必ず公式の公募要領をご確認ください。<br>'
              f'<a href="{SITE}alerts/" style="color:#2A7FC4">締切カレンダーを購読する</a>　'
              f'<a href="{SITE}search/" style="color:#2A7FC4">全制度を検索する</a></p>'
            f'</div></div>')

    key = os.environ.get("RESEND_API_KEY")
    if not key:
        print("[alert] RESEND_API_KEY が未設定のため送信しません。件名:", subject)
        print(f"[alert] 新着 {len(fresh)}件 / 締切間近 {len(near)}件")
        open(os.path.join(ROOT, "data", "last_digest.html"), "w", encoding="utf-8").write(html)
        return 0

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps({"from": FROM, "to": [TO], "subject": subject, "html": html}).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print("[alert] 送信しました:", r.status, subject)
    except Exception as e:
        body = getattr(e, "read", lambda: b"")()
        print("[alert] 送信に失敗しました:", e, body[:300], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
