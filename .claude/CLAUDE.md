# kanji-grade-language-pack

Minecraft Java 版に、子ども向けの日本語を 7 つ（`ja_kana`、`ja_g1`〜`ja_g6`）足すリソースパックを作るプログラム。
パックは Mojang の `ja_jp.json` からビルドのたびに作る（リポジトリに Mojang の文字列は入れない）。全体の説明・構成・
コマンドの一覧は `README.md`（英語。日本語は `README.ja.md`。2 つは同じ中身に保つ）。

## 作業の決まり

- ビルド・テストは全部 make 経由でコンテナの中で行う。ホストに Python のパッケージなどを入れない
  - `make`（パック）、`make test`（pytest）、`make game-client-tests`（全部の版の Minecraft のクライアントでの確認。
    1 つの版だけなら `make game-client-test MINECRAFT_VERSION=<版>`）
  - 1 つの文字列を 7 言語で見る：`make show-string KEY=<ja_jp.json のキー>`
  - 2 つのパックの違い：`make pack-diff PREVIOUS=<zip> NEW=<zip>`（どちらもリポジトリの中に置く）
- 版はすべて固定する。使うのはその時点の安定版の最新（Fabric API は、その Minecraft の版を表に足す時点の最新。
  後から出たビルドには、テストが求めるときだけ手で上げる）。GitHub Actions はコミットの SHA、ベースイメージは digest、
  Python の依存は `uv.lock`（ハッシュ付き）、Gradle の依存は `game_client_test/gradle/verification-metadata.xml`。
  例外：テスト用のイメージの `apt-get install`（Ubuntu のパッケージ）は版を固定しない（ベースイメージの digest で決まる）
- 対応する Minecraft の版（版ごとの形式・`ja_jp.json` の SHA-1・Java の版・Fabric API）は `minecraft_versions.toml`
  だけに、パック自身の版・Fabric Loader・Loom・アイコンのフォントは `versions.mk` だけに書く（Makefile が CLI と
  Gradle へ渡す）
- ブランチは `main` 1 本（topic ブランチで作業してまとめる）。Minecraft の版ごとのブランチは作らない
- 名前は中身を正確に表すものにする（曖昧な名前を付けない）
- 同じ入力からは同じ zip（バイト単位）になることを保つ。CI が作り直して確かめている
- テストや例に Mojang の文字列（`ja_jp.json` の文）を使わない。自分で書いた文か、一般的な語だけにする
- `docs/` は手元だけのメモで、git に入れない（`.gitignore`）
- README の画面（`screenshots/`）は、ゲームでのテスト（`make game-client-test`）が撮ったものを写す。表示が変わったら
  撮り直す（`game_client_test/run/<版>/screenshots/` の `options_*`・`language_list`・`resource_packs`）
- 出力（パックの中身）が変わる変更をしたら、変わった文字列を確かめる。変更の前の zip を残しておき、
  `make pack-diff` で 7 言語ごとの差分を見る（PR では `build.yml` の `pack-diff` ジョブが、実行のまとめに出す）

## 方針（決めたこと）

- 学年は文部科学省の学年別漢字配当表（2017 年告示・2020 年度から、1026 字）。小学校で習わない漢字はどの学年でもかな
- 字ごとに置き換える（交ぜ書き）：鉄格子 → 3 年は 鉄ごう子。分割 → 分かつ のように読みにくくなる語があっても、
  交ぜ書きのままにする（決めたこと）
- 漢字は、常用漢字表の読み（付表の熟字訓を含む）で使われているときだけ見せる。表に無い読み（当て字、名前、
  Sudachi の読みが表の読みに割り当てられない字）は、どの学年でも常にかな（マークアップの `⟪字|よみ⟫`）
  - 付表の語は、字ごとに表の読みで割り当てられるときは字ごと（友達 → 友だち）、できないときだけ語ごと（今日、手伝う）
- 分かち書き（文節の間の半角スペース）は `ja_kana`・`ja_g1`・`ja_g2`（1・2 年の教科書と同じ）。
  `reading_markup.WITH_SPACES`。区切りの規則は `bunsetsu.starts_bunsetsu`（語の並び全体を見る）
- 数字は数字のまま残す。数字によって変わる読み（1日 ついたち）は追わず、数字によらない読み（にち）にする
- Minecraft 1.21 系以前は対応しない

## 対応する Minecraft の版

- `minecraft_versions.toml` に版ごとに書く。同じ `ja_jp.json`（SHA-1）を配られている版どうしは 1 つのパックに
  まとめ、`pack.mcmeta` の `min_format`〜`max_format` をそれらの版の形式の範囲にする（`minecraft_versions.py`）
  - zip の名前とパックの版番号に版の範囲が入る：`kanji-grade-ja-0.1.1+mc26.1-26.3.zip`、`0.1.1+mc26.1-26.3`
  - 1 つのパックは連続した版だけをまとめる（間に別の `ja_jp.json` の版を挟むとビルドが止まる。形式の範囲が
    その版にもかかってしまうため）。起きたら、古い側の版を表から外す
- ゲームでのテストは版ごとに、その版が動く Java（表の `java_version`。Mojang の版の情報の `javaVersion.majorVersion`）
  で行う（CI はマトリクス）。テスト用のイメージは Java の版ごとに `game_client_test/docker/java<N>/Dockerfile`、
  テスト用の MOD もその Java 向けにコンパイルする（`-Pjava_version`）。版ごとに Fabric API が違い、Gradle の依存も
  版ごとに要る

### 新しい Minecraft や Fabric に追従する（検出は自動、追従は人）

方針：予測できる変化には受け皿（表の列、Java の版ごとのイメージ、止まって何をすべきかを示す検査）を用意しておき、
大きな版の変更でコードがどう変わるかという予測できない部分は人が手で直す。スクリプトで無理に自動化しない。

`check-minecraft-versions.yml` が毎日（00:00 UTC）`make update-minecraft-versions` を動かし、見つけたものを実行のまとめに
書く。人がすることがあれば実行を失敗で終わらせる（GitHub から通知が届く）。リポジトリには何も書き込まない。
片づけるまで毎日失敗し続ける（Fabric API を待つ間も）。

`make update-minecraft-versions` がすること（`minecraft_versions_update.py`）：

- 機械的に書き換える（「Changed」）：表の版に配られる `ja_jp.json` が変わった、表の最新より番号の大きいリリースに
  Fabric API がある（形式・`ja_jp.json`・Java・Fabric API を調べて足す）。2 つの README の版の行も合わせる
- 人がすること（「To do by hand」、毎日の実行が失敗する）：新しい `ja_jp.json` の読みの確認（`make ja-jp-changes` の
  引数も出る）、足した版の Java のイメージが無い、古い系列のパッチ（26.3 の後の 26.2.1）、プログラムが読めない名前の
  リリース、Fabric API が無い（読めない）新しいリリース
- 知らせるだけ（「Good to know」）：表の版の Fabric API の新しいビルド、
  Fabric Loader・Loom の新しい版

人がすること（通知を受けたら）：

1. topic ブランチを切り、`make update-minecraft-versions`。出力の「To do by hand」を全部片づける
   - 古い系列のパッチ：表に手で足す（値は下の「手で版を足す」）。まとまりが崩れてビルドが止まったら、古い側の版を外す
   - 読めない名前のリリース：`minecraft_versions.py` の `VERSION` と、版の順（`MinecraftVersion.order`、
     `minecraft_versions_update._order`）を直す
   - Fabric API が無い：Fabric の対応を待つ。https://fabricmc.net/develop にあるのに読めていなければ、名前の形が
     変わっている。`fabric_api_builds` を直す
   - Java のイメージが無い：下の「新しい Java を求める Minecraft が出たとき」
2. `make` と `make test`。止まったら直す
   - 「fixes that match nothing」：`data/reading_fixes.toml` のその規則を見直す（文字列が変わった・消えた、Sudachi の
     切り方が変わった）。要らなければ消す。規則は、どれか 1 つの `ja_jp.json` で当たれば使われているとみなす
   - 「words Sudachi reads as names」：人名と読まれた語（誤読のことが多い）を見て、規則を足す。読みが正しければ、
     Sudachi と同じ読みの規則を書いて「見た」印にする（`小玉`）
   - 「problems, the pack is not written」：出た問題（学年超過の漢字、プレースホルダーの変化、原文に戻らない
     マークアップ、空白の置き方など）を直す
   - 数字と漢字が 1 語になった語（`DigitsInWord`）は、`word_reading` の規則か `string_markup` で読みを与える
   - 「… has no …: Mojang changed the form of its JSON」：Mojang の版の情報の形が変わった。`mojang_assets.py` を直す
3. 新しい `ja_jp.json` が出たときは、`make ja-jp-changes PREVIOUS_SHA1=… NEW_SHA1=…`（`build/ja_jp_changes.md`）の
   `ja_kana`・`ja_g1` の列で、増えた・変わった文字列の読みと区切りを全部見る。誤りは `data/reading_fixes.toml` に規則を
   足して直し、`make show-string KEY=…` で確かめる
4. `make gradle-verification-metadata GRADLE_CACHE_VOLUME=<新しい名前>` と `make game-client-tests`
   - 新しい版だけで失敗する：まず `versions.mk` の Fabric Loader と Loom をその版に対応した版に上げる。それでもだめなら、
     テストのコードがその版の API に合っていない。版の差を吸収する（26.1 と 26.2 で読み込み画面の API が変わったので、
     どの版にもある読み込みの完了を待っている）
   - パックが使えない・言語が出ない：`pack.mcmeta` の形（`min_format`・`max_format`・`language`）か言語ファイルの場所
     （`language_pack.language_file`）が変わった。`language_pack.build_pack` とテストの MOD を直す。古い版と両立しない
     形なら、古い版を表から外す（版ごとに切り替える仕組みは作らない）
5. PR を出す。`build.yml`（ゲームでのテスト）と `pack-diff`（7 言語の差分）が動く。依存のハッシュの差分は、新しい
   Fabric API の分が足されているだけかを見る（`<trust>` や `also-trust` が増えていたら危険）
   パックの中身が変わるときは、同じ PR で `PACK_VERSION` も上げる（マージでリリースされる。下）

手で版を足す・外すとき：`minecraft_versions.toml` を書き換え（値は `make -s resource-pack-format
MINECRAFT_VERSION=…`・`make -s served-ja-jp-sha1 MINECRAFT_VERSION=…`・`make -s java-version MINECRAFT_VERSION=…`・
https://fabricmc.net/develop）、その Java のイメージ（`docker/java<N>/`）があることを確かめ、`README.md`・
`README.ja.md` の版の行を直し、上の 2・4・5。

### 新しい Java を求める Minecraft が出たとき

`make update-minecraft-versions` が「no image」と出す（`make game-client-test-image` も、足すべきファイルを示して
止まる。`make test` も止まる）。人がすること：

1. `game_client_test/docker/java25/` を `docker/java<N>/` に写し、`FROM` をその Java の Temurin のイメージ（タグと
   digest）にする。`FROM` の行は書き換えずにそのまま書く（Dependabot が Java の版ごとに、メジャー版の中で上げる）。
   タグの Ubuntu（`noble` など）が変わったら、`apt-get install` のパッケージ名がその Ubuntu にあるか確かめる
2. Gradle も、そのイメージの Java で動く。Gradle がその Java に対応していなければ、Gradle の版を上げる
   （`game_client_test/gradle/wrapper/`、公式の配布物から作り、SHA-256 を確かめる）。Loom・Fabric Loader も、その
   Minecraft に対応した版が要る（`versions.mk`）
3. `make gradle-verification-metadata GRADLE_CACHE_VOLUME=<新しい名前>`、`make test`、`make game-client-tests`
4. Java 25 の版を表から外すまでは、`docker/java25/` も残す（古い版のテストに要る）

### 古い版を外す

- Loom・Fabric Loader（全部の版で共通）が古い版を受け持たなくなったら、その版を表から外す
- 外した版のパックは、過去の GitHub Releases と Modrinth の版に残る
- 外した後は、依存のハッシュを空のキャッシュから記録し直すと、使わなくなった項目が消える。
  `verification-metadata.xml` の `<components>` の中身だけを消し（`<configuration>` は残す）、
  `make gradle-verification-metadata GRADLE_CACHE_VOLUME=<新しい名前>`

## リリース

- リリースするには、PR で `versions.mk` の `PACK_VERSION` を上げてマージする。タグは手で打たない
  - `release.yml` は `main` への push のたびに動き、`v<PACK_VERSION>`（`make -s print-RELEASE_TAG`）のタグがまだ
    無ければリリースする：全部の版でテストし（テストの側で作り直した zip がリリースする zip と同じバイト列かも確かめる）、
    environment `release` の承認の後に、push されたコミットにタグを作り、GitHub Release に全部の zip を付ける。タグが
    もうあれば何もしない
  - タグは `release.yml` が Release と一緒に作る（`GITHUB_TOKEN` で push したタグでは、ほかのワークフローが動かない
    ため）。GitHub の画面の「Create a new release」でタグや Release を作らない（同じ名前が先にできて失敗する）
  - PR の `pack-diff` のまとめの先頭に、マージでリリースされるか（`PACK_VERSION` が変わったか）が出る
- `PACK_VERSION` の上げ方：読みや表記が変わった（新しい `ja_jp.json` を含む）ときはマイナー、直しだけならパッチ。
  対応する版を足しただけでも zip の名前が変わるので、パッチを上げて出す。上げ忘れは `build.yml` が `main` で警告する
  （最後のリリースのタグから `data/`・`src/`・表が変わったのに `PACK_VERSION` が同じとき。そのマージではリリースされない）
- 1.0.0 までは 0.x で出す（0.1.0 は使えない。初めは 0.1.1）
- Release は変えられない設定（immutable releases）にしている。一度 Release に使ったタグの名前は、Release やタグを
  消しても、リポジトリを消して同じ名前で作り直しても、二度と使えない（GitHub の決まり）。試しのリリースでも版の番号を
  使い切るので、出す前に確かめる
- リリースが途中で失敗したとき：タグを作る前（テストや承認の前）なら、直して `main` に入れれば次の push でまたリリース
  を試みる。タグと Release を作った後（Modrinth で失敗など）は、直さない（タグは消さない）。`PACK_VERSION` のパッチを
  上げて出し直す（公開したリリースは変えられない設定にしている）

### Modrinth

`release.yml` は、リポジトリの変数 `MODRINTH_PROJECT_ID` と、environment `release` のシークレット `MODRINTH_TOKEN`
があると、パックごとに Modrinth の版を作る（mc-publish。`loaders: minecraft`、`game-versions` は表の版を 1 行に 1 つ、
古いパックから 1 つずつ）。設定するまでは何もしない。初めての公開：

1. Modrinth でプロジェクトを手で作る。説明文は自分で書く（Modrinth の規則で、AI の書いた説明文は使えない）。
   「AI-generated content」の表示を付ける。ライセンスは MIT（パックの中の文字列は Mojang のもの）
2. Modrinth の個人のアクセストークン（版を作れる範囲だけ）を作る。期限があるので、切れる前に作り直す
3. `gh variable set MODRINTH_PROJECT_ID --body <プロジェクトの ID>`、`gh secret set MODRINTH_TOKEN --env release`
4. プロジェクトを下書きのまま、次のリリース（`PACK_VERSION` を上げる PR のマージ）で公開を試す（mc-publish が
   `loaders: minecraft` と 26 系の版名を通すか）。うまくいったら審査に出す

## GitHub の設定

- リポジトリの設定は `.github/apply-repository-settings.sh` にあり、`make github-settings` で当てる。リポジトリを
  作り直したときに実行する（何度実行してもよい）。ワークフローの形（リリースの起動、使うアクション、environment）を
  変えたら、このスクリプトも合わせる
- `main` へは PR で入れる（`build` の成功が要る）

## 読みの直し（data/reading_fixes.toml）

- 書き方はファイルの先頭と `src/kanji_grade_language_pack/reading_fixes.py` の docstring。値の型も確かめる
  （語の並びを文字列で書くとビルドが止まる）
- `[[word_reading]]` は、語（Sudachi が切った 1 語）と Sudachi の読みに、条件（`key`、`previous_word_in`、
  `next_word_in`、`after`）を付けて正しい読みを与える。条件の多い規則が勝つ。文字列ごと（`key`）より、前後の語で
  書ける規則を優先する（同じ誤りがほかの文字列にも当たる）
- `unsplit_words` は表に無い読みの語（当て字・名前）で、常にかなになる。付表の語はここに書かない（付表から自動）
- `extra_kanji_readings` は語の中で音が変わる形だけ（来る き・こ、反応 のう）。表に無い読みを足して漢字を見せる
  ためには使わない
- `[string_markup]` は、Sudachi の切り方そのものが誤っていて、規則では直せない文字列だけ（当分の間村から）
- どの語にも当たらない規則があるとビルドが止まる。Sudachi や `ja_jp.json` が変わったら、見直して直すか消す

## 依存の更新

- Dependabot が GitHub Actions・ベースイメージ（ビルド用、uv、Java の版ごとのテスト用）・`uv.lock`・Gradle の
  ラッパーの更新を PR にする。出てから 7 日待って取り込む（`cooldown`）。Minecraft・Fabric API・Fabric Loader・Loom は
  手で上げる（`check-minecraft-versions.yml` が新しいものを知らせる）。アイコンのフォントも手で上げる
- Dependabot は Python のイメージをパッチ版だけ（`pyproject.toml` が 3.15 を求めるため。3.16 などへは
  `requires-python` を変えて `make lock` で手で上げる。アルファ版も来なくなる）、Temurin のイメージを Java の版ごとの
  メジャー版の中だけで上げる（`.github/dependabot.yml` の `ignore`）
- ワークフローの `runs-on: ubuntu-24.04` は Dependabot が上げない。GitHub が廃止を告知したら手で上げる
- SudachiDict を上げると、検査は通っても読みや切り方が変わる（26-10 の版では 3 文が悪くなった）。Dependabot の PR では、
  `build.yml` の `pack-diff` のまとめで変わった文字列を全部見て、悪くなった読みは規則で直してからマージする
- `pyproject.toml` を変えたら `make lock`。Fabric や Gradle の版を変えたら `make gradle-verification-metadata`
  （空の Gradle のキャッシュから記録しないと、CI で足りないハッシュが出る：`GRADLE_CACHE_VOLUME=<新しい名前>` を付ける）
- 学年の漢字と付表（`data/grade_kanji_readings.json`、`data/joyo_appendix_words.json`）は、国の PDF から
  `make fetch-kanji-data` で作り直せる。PDF は URL と SHA-256 を `src/kanji_grade_language_pack/grade_kanji_pdf.py`
  に固定している。URL が切れたら新しい URL を探し、中身が同じ（SHA-256 が同じ）なら URL だけ直す

## セキュリティ

- コンテナは権限を最小にする。ネットワークのあるコンテナには、要るディレクトリだけを書き込ませる。この形を崩さない
  （Makefile の `DOCKER_RUN`・`DOCKER_RUN_ONLINE`・`OFFLINE`・`ONLINE`。新しいターゲットもこれを使う）
- ダウンロードは必ずハッシュで確かめる（`download.py`）。Mojang の値は SHA-1 の形と、URL が Mojang のホストかも
  確かめてから使う
- ワークフローは権限を最小にし（既定は `permissions: {}` か `contents: read`）、checkout は `persist-credentials: false`。
  書き込みの権限が要るジョブ（リリース・Modrinth）では、ビルドのコードを動かさない。リリースと Modrinth は
  environment `release` で動く
- `run:` の中に `${{ }}` を直接書かない（`env:` を通す）
- 使うアクションを増やすときは、`.github/apply-repository-settings.sh` の許可にも足す

## 落とし穴

- Gradle は値の変わらないタスクを飛ばすので、`prodClientGameTest` は `outputs.upToDateWhen { false }` で毎回動かす
- Fabric の client GameTest は、タイトル画面で終わらないと失敗する
- Loom が手元で作る Minecraft の jar は環境ごとにバイト列が違うので、Gradle の依存の検証では別の扱いにしている
  （`verification-metadata.xml` の `<configuration>`。記録し直すときも消さない）
- ゲームは言語ファイルを読んだ後に、使わなくなったキーを消し、名前の変わったキーを移す
  （`DeprecatedTranslationsInfo`）。テストの期待値も同じ処理を通している
- Sudachi は `%s`・`%1$s` を `%`・数字・`$`・`s` に分け、`%` の品詞も揃わない。文節の判定ではプレースホルダーを
  1 つの名詞として扱っている（`bunsetsu.words`）。「まもなく」も ま|も|なく に分けるので 1 語にまとめている
  （`JOINED_WORDS`）。「スポーン」「ムズムズ」は副詞と読む。中に「の・に・が」を挟む長い固有名詞（灰色の花模様）は、
  短い単位で分け直している
- 「ヶ」は、かなに直す前に判定しないと「ゖ」になって当たらない（`_kana_match`）
- `make clean` は `build/` と、このプログラムが作る `dist/kanji-grade-ja-*.zip` だけを消す。`dist/` の
  ほかのファイルには触らない
- `make pack-diff` に渡す zip は、リポジトリの中に置く（コンテナからはリポジトリしか見えない）
