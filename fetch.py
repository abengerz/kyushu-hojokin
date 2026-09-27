import json, time, urllib.parse, urllib.request, os, sys

BASE = "https://api.jgrants-portal.go.jp/exp/v1/public/subsidies"
PREFS = ["福岡県","佐賀県","長崎県","熊本県","大分県","宮崎県","鹿児島県","沖縄県"]
KEYWORDS = ["補助","助成","支援","事業","導入","設備","人材","創業","販路","観光",
            "農業","漁業","林業","育成","雇用","デジタル","環境","省エネ","研究","開発",
            "商品","施設","整備","促進","地域","中小企業","賃上げ","輸出","海外","改善",
            "安全","医療","福祉","子育て","women","女性","起業","店舗","IT","AI",
            "生産性","脱炭素","再生","連携","展示","認証","感染","防災","教育","訓練"]

def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Accept":"application/json","User-Agent":"kyushu-hojokin/1.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if i == tries-1:
                print("ERR", url[:120], e, file=sys.stderr); return None
            time.sleep(1.5*(i+1))

index = {}
for pref in PREFS:
    for kw in KEYWORDS:
        q = urllib.parse.urlencode({"keyword":kw,"sort":"created_date","order":"DESC",
                                    "acceptance":"0","target_area_search":pref})
        d = get(f"{BASE}?{q}")
        if not d: continue
        for r in (d.get("result") or []):
            index.setdefault(r["id"], r)
        time.sleep(0.15)
    print(f"{pref} done, cumulative={len(index)}", flush=True)

print("total unique:", len(index), flush=True)
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)),"data"),exist_ok=True)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)),"data","index.json")
json.dump(index, open(out,"w",encoding="utf-8"), ensure_ascii=False, indent=1)

details = {}
ids = list(index.keys())
for i, sid in enumerate(ids):
    d = get(f"{BASE}/id/{sid}")
    if d and d.get("result"):
        details[sid] = d["result"][0]
    if i % 50 == 0: print(f"detail {i}/{len(ids)}", flush=True)
    time.sleep(0.12)
json.dump(details, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"data","details.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("details:", len(details), flush=True)
