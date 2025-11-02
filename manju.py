import streamlit as st

# Google Gemini APIを使うためのライブラリを読み込む
from google import genai
from google.genai import types
from google.genai import Client

# 画像を扱うためのライブラリ
from PIL import Image

import os


# --- ユーザーに見える画面の設定 ---

# アプリのタイトル
st.title('画像と話せるAIチャット')

# 画像ファイルをアップロードするための機能
input_image = st.file_uploader("🖼️ 画像ファイルを選んでね", type=['png', 'jpg', 'jpeg'])

# ユーザーが質問を入力する場所
# 入力された文字はすべて小文字に変換されます
input_text = st.text_area('💬 質問を入力してね', height = 100).lower()


# --- AI（Gemini）の設定 ---

# Streamlitのシークレット機能を使ってAPIキーを安全に取得
api_from_streamlite = st.secrets["GEMINI_KEY"]

# AIクライアントの準備
client = Client(api_key=api_from_streamlite)

# テキストチャット用のセッションを開始 (gemini-2.0-flashは早くて高性能なAIモデル)
chat = client.chats.create(model="gemini-2.0-flash")


# --- ボタンが押されたときの処理開始 ---
# 「分析・回答する」ボタンがクリックされたら、AIに処理をお願いする

if st.button("✨ 分析・回答する"):
  try:
    response_text = ""

    # (1) 画像と質問の両方がある場合
    if input_image and input_text:
      try:
        # アップロードされた画像をImageオブジェクトとして開く
        image = Image.open(input_image)

        # AIモデルに画像と質問を一緒に送る (gemini-2.5-flashは画像もテキストも処理できるAIモデル)
        response = client.models.generate_content(
          model="gemini-2.5-flash", 
          contents=[image, input_text],
          config=types.GenerateContentConfig(
              temperature=0.1 # 応答の創造性を低めに設定
            ),
        )

        # AIからの応答（テキスト）を取得
        # ストリーミング応答と非ストリーミング応答の両方に対応
        if hasattr(response, '__iter__') and not hasattr(response, 'text'):
          response_text = "".join([part.text for part in response if hasattr(part, 'text')])
        else:
          response_text = response.text if hasattr(response, 'text') else ""
          
        # 不要な文字列を削除して整形
        response_text = response_text.replace('role - user', '').replace('role - model', '').strip()
        
        # AIの回答を画面に表示
        st.markdown(response_text, unsafe_allow_html=True)
      
      except Exception as e:
        # 画像処理中にエラーが発生した場合
        st.error(f"画像処理中にエラーが発生しました: {e}")

    # (2) 質問テキストだけがある場合
    else:
      # 入力テキストが「やめる」ではない場合のみ処理を続ける
      if input_text != 'やめる':
        # テキストチャットとしてAIに質問を送り、応答をストリーミングで受け取る
        response = chat.send_message_stream(input_text)
        
        # 応答のすべての部分をつなげて一つのテキストにする
        response_text = "".join([part.text for part in response if hasattr(part, 'text')])
        
        # 不要な文字列を削除して整形
        response_text = response_text.replace('role - user', '').replace('role - model', '').strip()     
        
        # AIの回答を画面に表示
        st.markdown(response_text, unsafe_allow_html=True)
      
      else:
        # 「やめる」と入力された場合
        print('会話を終了します。またね！')

  except Exception as e:
    # その他の予期せぬエラーが発生した場合
    st.write(f"エラーが発生しました: {e}")
