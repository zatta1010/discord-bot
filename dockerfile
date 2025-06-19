# ベースイメージとしてPythonの公式イメージを使用
# Python 3.11を推奨。alpine版は軽量だが、一部ライブラリで問題が出る可能性もあるので、まずは通常版を試す。
FROM python:3.11-slim-bookworm

# 作業ディレクトリを設定
WORKDIR /app

# requirements.txt をコピーし、依存関係をインストール
# requirements.txt が変更されたときのみpip installが再実行されるように、先にコピー
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# その他のアプリケーションコードをコピー
COPY . .

# ボットを起動するコマンド
# FlaskなどWebサーバーを兼ねる場合はCMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000"] のようになるが、
# Discord Botの場合は python main.py
CMD ["python", "main.py"]
