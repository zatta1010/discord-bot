import os
import discord
from discord.ext import commands
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import json
import requests  # ファイルダウンロード用
import mimetypes  # ファイルのMIMEタイプ判定用

# ReplitのKeep Alive処理
from flask import Flask
from threading import Thread

app = Flask('')


@app.route('/')
def home():
    return "I'm alive!"


def run_flask():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run_flask)
    t.start()


# --- Google Drive API設定 ---
# サービスアカウントキーはReplitの環境変数から読み込む
# REPLIT_DBなどの別の方法で保存することも可能だが、環境変数が一般的
# または、直接JSONファイルをプロジェクトに置いて相対パスで読み込むことも可能
# 例: 'path/to/your/service_account.json'
# ここでは環境変数から読み込む想定（Replitで設定）
SERVICE_ACCOUNT_KEY_JSON = os.environ.get('GOOGLE_SERVICE_ACCOUNT_KEY')
if SERVICE_ACCOUNT_KEY_JSON:
    SERVICE_ACCOUNT_INFO = json.loads(SERVICE_ACCOUNT_KEY_JSON)
else:
    print("Warning: GOOGLE_SERVICE_ACCOUNT_KEY environment variable not set.")
    SERVICE_ACCOUNT_INFO = None  # 実際にはエラーハンドリングが必要

# アップロード先のGoogle DriveフォルダID
# 環境変数から読み込むか、直接記述
# 例: os.environ.get('GOOGLE_DRIVE_FOLDER_ID', 'your_default_folder_id')
GOOGLE_DRIVE_FOLDER_ID = os.environ.get('GOOGLE_DRIVE_FOLDER_ID')

if not GOOGLE_DRIVE_FOLDER_ID:
    print("Error: GOOGLE_DRIVE_FOLDER_ID environment variable not set.")
    # 環境変数がない場合のデフォルト値を設定するか、プログラムを終了するなどの処理が必要
    exit()  # 動作確認のため、ここでは終了

# Google Drive API 認証
SCOPES = ['https://www.googleapis.com/auth/drive']  # Driveへのフルアクセス
creds = None
if SERVICE_ACCOUNT_INFO:
    try:
        creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO,
                                                      scopes=SCOPES)
        service = build('drive', 'v3', credentials=creds)
        print("Google Drive API認証成功！")
    except Exception as e:
        print(f"Google Drive API認証エラー: {e}")
        service = None  # 認証失敗時はserviceをNoneにする
else:
    service = None

# --- Discord Bot設定 ---
# Discord BotのトークンはReplitの環境変数から読み込む
DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')

# Discord Botのインテント設定
# メッセージ内容を読み取るためにMessage Content Intentを有効にする
intents = discord.Intents.default()
intents.message_content = True  # これが重要！

bot = commands.Bot(command_prefix='!', intents=intents)


# Botが起動した時の処理
@bot.event
async def on_ready():
    print(f'{bot.user} がログインしました！')
    print('Bot準備完了')


# メッセージが送信された時の処理
@bot.event
async def on_message(message):
    # Bot自身のメッセージは無視
    if message.author == bot.user:
        return

    # メッセージに添付ファイルがあるかチェック
    if message.attachments:
        print(
            f"添付ファイル付きメッセージを受信 from {message.author.name} in #{message.channel.name}"
        )
        for attachment in message.attachments:
            try:
                # ファイルをダウンロード
                file_url = attachment.url
                file_name = attachment.filename
                response = requests.get(file_url)
                if response.status_code == 200:
                    temp_file_path = f"./{file_name}"
                    with open(temp_file_path, 'wb') as f:
                        f.write(response.content)
                    print(f"ファイル '{file_name}' を一時的にダウンロードしました。")

                    # MIMEタイプを推定（google-api-python-clientが要求するため）
                    mime_type, _ = mimetypes.guess_type(temp_file_path)
                    if mime_type is None:
                        mime_type = attachment.content_type  # Discordから取得したMIMEタイプを使用

                    if service:
                        # Google Driveにアップロード
                        file_metadata = {
                            'name': file_name,
                            'parents':
                            [GOOGLE_DRIVE_FOLDER_ID]  # アップロード先のフォルダIDを指定
                        }
                        media = MediaFileUpload(temp_file_path,
                                                mimetype=mime_type,
                                                resumable=True)
                        uploaded_file = service.files().create(
                            body=file_metadata,
                            media_body=media,
                            fields='id, webViewLink').execute()
                        print(
                            f"'{file_name}' をGoogle Driveにアップロードしました。ファイルID: {uploaded_file.get('id')}"
                        )
                        await message.channel.send(
                            f"**{file_name}** をGoogle Driveにアップロードしました！\n"
                            f"リンク: {uploaded_file.get('webViewLink')}")
                    else:
                        await message.channel.send(
                            "Google Drive APIが利用できません。認証を確認してください。")

                    # アップロード後、一時ファイルを削除
                    os.remove(temp_file_path)
                    print(f"一時ファイル '{temp_file_path}' を削除しました。")

                else:
                    await message.channel.send(
                        f"ファイル '{file_name}' のダウンロードに失敗しました。")

            except Exception as e:
                print(f"ファイル処理中にエラーが発生しました: {e}")
                await message.channel.send(
                    f"ファイル '{attachment.filename}' のアップロード中にエラーが発生しました。")

    # コマンド処理も忘れずに呼び出す
    await bot.process_commands(message)


# Discord Botの実行
if DISCORD_BOT_TOKEN:
    keep_alive()  # Flaskサーバーを起動
    try:
        bot.run(DISCORD_BOT_TOKEN)
    except discord.errors.LoginFailure as e:
        print(f"Botトークンが無効です。Discord Developers Portalでトークンを確認してください: {e}")
    except Exception as e:
        print(f"Discord Botの起動中に予期せぬエラーが発生しました: {e}")
else:
    print(
        "Error: DISCORD_BOT_TOKEN environment variable not set. Bot will not run."
    )
