# 九州補助金ナビ

福岡・佐賀・長崎・熊本・大分・宮崎・鹿児島・沖縄の 8 県を対象とする補助金・助成金だけを集めた検索サイト。

- **データ**: デジタル庁 jGrants 補助金電子申請システムの公開 API
- **生成**: Python だけで動く静的サイトジェネレータ（依存パッケージなし）
- **公開**: GitHub Pages（GitHub Actions で毎日 JST 6:00 にデータを再取得して自動再公開）

## 構成

```
fetch.py          jGrants 公開 API から 8 県分の制度を収集 → data/*.json
build.py          data/*.json から site/ 以下に静的サイトを生成
assets/           CSS / JS（生成時に site/assets へコピー）
data/             収集済みデータ（Actions が毎日更新してコミット）
site/             生成物（gitignore 済み。CI では artifact として Pages に渡す）
```

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
| `KH_BASE_URL` | canonical / OGP / sitemap 用の絶対 URL | `https://<user>.github.io/kyushu-hojokin` |

独自ドメインをルートで使う場合は `KH_BASE` を空にする。

## 出典・免責

制度情報の原典は各所管府省庁・自治体。補助率・上限額・締切は公募回ごとに改定されるため、申請前に必ず公式の公募要領を確認すること。
