# 九州補助金ナビ

福岡・佐賀・長崎・熊本・大分・宮崎・鹿児島・沖縄の 8 県を対象とする補助金・助成金だけを集めた検索サイト。

- **データ**: デジタル庁 jGrants 補助金電子申請システムの公開 API
- **生成**: Python だけで動く静的サイトジェネレータ（依存パッケージなし）
- **公開**: GitHub Pages（GitHub Actions で毎日 JST 6:00 にデータを再取得して自動再公開）
- **地図**: 国土数値情報由来の県境ポリゴンを Douglas–Peucker で簡略化した実形状 SVG
- **AI相談**: 掲載データを引いて答えるクライアントサイド実装（外部APIキー不要）
- **締切アラート**: 締切カレンダー(.ics)・新着RSS を県別に自動生成。メール版は `alert.py` が日次で差分を検出して送信

## 構成

```
fetch.py          jGrants 公開 API から 8 県分の制度を収集 → data/*.json
alert.py          前回実行からの新着と締切間近を検出してメール送信（data/seen.json で差分管理）
make_map.py       国土のGeoJSONから九州・沖縄8県の簡略SVGパスを生成 → data/kyushu_map.json
                  （生成物をコミットしているので通常のビルドでは不要）
build.py          data/*.json から site/ 以下に静的サイトを生成
assets/           CSS / JS（生成時に site/assets へコピー）
data/             収集済みデータ（Actions が毎日更新してコミット）
site/             生成物（gitignore 済み。CI では artifact として Pages に渡す）
```

## ページ構成

| パス | 内容 | 件数 |
|---|---|---|
| `/` | トップ（実地図・30秒診断・締切・各分類） | 1 |
| `/search/` | 全制度検索（クライアントサイド） | 1 |
| `/ai/` | 補助金AI相談の説明。ウィジェットは全ページ右下に常駐 | 1 |
| `/deadline/` | 締切カレンダー（月別） | 1 |
| `/alerts/` | 締切アラート（.ics購読・RSS・メール申込） | 1 |
| `/alerts/*.ics` `*.xml` | 締切カレンダー／新着RSS（全体＋県別） | 18 |
| `/pref/<県>/` | 県別 | 8 |
| `/purpose/<目的>/` `<目的>/<県>/` | 目的別・目的×県 | 15 + 約120 |
| `/industry/<業種>/` `<業種>/<県>/` | 業種別・業種×県 | 20 + 約160 |
| `/audience/<対象者>/` | 対象者別 | 8 |
| `/permit/<業種>/` | 許認可・届出ガイド | 8 |
| `/guide/<記事>/` | 制度ガイド | 8 |
| `/subsidy/<id>/` | 制度詳細 | 808 |

## データの完全性について

jGrants 公開 API はキーワード検索しか提供していないため、150 語 × 8 県で総当たりして和集合を取っている。
50 語で 808 件を収集した後、重複しない 100 語を追加投入して**新規 0 件**を確認済み（`fetch.py` の KEYWORDS を増やしても件数は変わらない）。

ただし jGrants に登録されるのは国・独立行政法人・都道府県の制度に限られる。
**市区町村独自の制度と、個人向けの給付金は含まれない。**件数だけを他サイトと比較しても意味がない点に注意。

## ローカルで動かす

```bash
python3 fetch.py                 # データ取得（数分）
KH_BASE=/kyushu-hojokin python3 build.py
python3 -m http.server -d site 8080
```

環境変数

| 変数 | 用途 | 例 |
|---|---|---|
| `KH_BASE` | 公開パス。GitHub Pages のプロジェクトページで必須 | `/kyushu-hojokin` |
| `KH_BASE_URL` | canonical / OGP / sitemap 用のオリジン（パスは含めない） | `https://<user>.github.io` |

独自ドメインをルートで使う場合は `KH_BASE` を空にする。

## 出典・免責

制度情報の原典は各所管府省庁・自治体。補助率・上限額・締切は公募回ごとに改定されるため、申請前に必ず公式の公募要領を確認すること。


## 締切アラート

### 利用者側（バックエンド不要で動く）

- `alerts/deadline.ics` … 受付中の制度の締切を VEVENT 化。**2週間前と3日前に VALARM** を仕込んであるので、Google カレンダー等に購読登録するだけで通知が飛ぶ。県別版もある。
- `alerts/new.xml` … 新着の RSS。Slack / Teams / Feedly に流し込める。県別版もある。
- `/alerts/` のフォームは mailto で `info@avengerz-japan.com` 宛に申込メールを組み立てる。

いずれも毎朝のビルドで作り直されるため、公募終了分は自動的に消える。

### 運用側（日次ダイジェストのメール）

`alert.py` が `data/seen.json` と突き合わせて「新着」と「締切14日以内」を検出し、HTML メールを送る。
GitHub Actions の scheduled 実行に組み込み済みで、**`RESEND_API_KEY` が未設定なら送信せずログに出すだけ**。

有効化の手順:

1. [Resend](https://resend.com) でアカウントを作り API キーを発行する
2. リポジトリの Secrets に `RESEND_API_KEY` を登録
3. （任意）独自ドメインを Resend で認証し、変数 `ALERT_FROM` に `九州補助金ナビ <alert@avengerz-japan.com>` を設定

| 変数 | 既定値 | 種別 |
|---|---|---|
| `RESEND_API_KEY` | なし（未設定なら送信しない） | Secret |
| `ALERT_TO` | `info@avengerz-japan.com` | Variable（設定済み） |
| `ALERT_FROM` | `onboarding@resend.dev` | Variable |
| `ALERT_SOON_DAYS` | `14` | Variable |

購読者ごとの配信をやる場合、購読者リストは**公開リポジトリに置けない**。
Resend の Audience か外部ストアに持たせて `alert.py` の宛先解決だけ差し替えること。
