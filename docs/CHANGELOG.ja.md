[English](../CHANGELOG.md) | [简体中文](CHANGELOG.zh-CN.md) | [日本語](CHANGELOG.ja.md)

---

# 変更履歴

## 未リリース（Mio-2.1）

### Runtime ABI とネイティブツールチェーン

- Runtime ABI 契約 **RA-1**（[docs/runtime-abi.md](runtime-abi.md)、`bunko/kiso/runtime/abi`）：darwin-arm64、linux-amd64、windows-amd64 に共通する保証（正確なルート追跡、オブジェクトの生存期間、メモリ安全性、すべての参照書き込み経路）を規定しました。既存の 2 種類のオブジェクトレイアウトは、それぞれ Darwin の Object ABI v1（世代別 GC）と Linux／Windows の x64-marksweep-v1 というプロファイルとして命名しました。オブジェクトレイアウト自体は変更していません。
- `mio build --gc-stress` はターゲットごとの GC ストレスモードを選択します。
- 契約テスト（`tests/runtime-abi`）と VM／ネイティブの差分テスト群（`tests/native-differential`）を、3 つのターゲットでデフォルト設定と `--gc-stress` 設定の両方でネイティブ実行します。
- 共有のネイティブ型解析で 2 件の問題を修正しました。自己参照する Nullable 構造体が再帰的な型結合の際に null 許容性を失い、`nil` 判定が「非 nil」に最適化されていた問題と、最初に `mu` と判定されたグローバル変数が初回のフィールド参照で解析に失敗する問題です。どちらも全ネイティブバックエンドに影響していました。
- Linux／Windows のランタイムトラップメッセージの長さを修正しました。`nil reference` と `index out of range` は途中で切れ、`invalid call` は長すぎる状態でした。

- **動作変更（darwin-arm64）：** ネイティブプログラムの終了時に、最後のトップレベル式文の値を自動表示しなくなりました。コンパイル済みプログラムが出力するのは、どのターゲットでも明示的な `chant` の内容だけです。参照実装の `mio run` では REPL 風の表示を引き続き利用できます。
- Darwin ランタイム：OS のメモリプレッシャーレベルを毎回の割り当てで問い合わせるのをやめ、最大 256 回の割り当てごと、および各 GC 後に再取得するようにしました。従来は割り当てごとに `sysctlbyname` を呼び出しており、割り当ての多いプログラムでは実行時間の約 3 分の 1 をカーネル内で費やしていました。この変更には未使用だったメタデータワード（オフセット 2880）を使っています。

### CI

- `.github/workflows/native.yml`（Full からも実行）：`ubuntu-24.04`、`macos-15`、`windows-2025` 上で、ネイティブコンパイラと CLI の固定点、ネイティブ `mio test`、Runtime ABI 契約、差分テスト群を確認し、Runner の OS／アーキテクチャ、Stage A の SHA-256、各ステージのハッシュを記録します。Stage A は go-hosted（Go 参照 VM が Mio 製 Linux lowering を実行）で、信頼済み GF4 Native Seed は `NOT_RUN` と記録されます。

### 削除

- Go 製 AOT バックエンドと関連ツール（Go+C の Linux ランタイム blob を含む `internal/aot`、`cmd/mochi-aot`、`cmd/mochi-aot-audit`、`examples/aot_m8..m10` のジェネレーター）、Go M18／BCD スクリプト、アーカイブ済みの Go リリースワークフロー、および CI モジュール `go-aot-reference`、`legacy-bootstrap`、`go-aot-linux-amd64`、`go-linux-native`、`linux-runtime-reference` を削除しました。それらのネイティブ検証は Mio 製ネイティブワークフローに移行しました。Go の参照フロントエンドと VM は、go-hosted Stage A のホストおよび VM の比較対象として残っています。
