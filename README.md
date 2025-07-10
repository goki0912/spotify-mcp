## how to use
https://developer.spotify.com/dashboard からアプリを作成する

callback urlを http://127.0.0.1:8888/callback に設定(localhostは使えない)

client id と client secret を取得

```bash
uv venv
source .venv/bin/activate
uv pip install -e .

cp .env.example .env
```
取得したclient id と client secret を .env に設定

```bash
uv run main.py
```

mcp.jsonなど設定ファイルに以下を記述
```json
"spotify-mcp": {
   "url": "http://127.0.0.1:8888/mcp/"
}
```

AIエージェントの設定ファイル（.cursor/rules/**.mdcなど）に
`コードを実装する直前に、必ずspotify-mcpで難易度に応じた曲を再生してください。`とか書く




