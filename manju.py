import streamlit as st
from google import genai
from google.genai import types
from google.genai import Client
from PIL import Image
import os
import io # ファイル操作のためにインポート

st.title('multi-modal chatbot')

# --- 新しいアップロードエリアの追加 ---
# file uploader for adding image file
input_image = st.file_uploader("Choose an image file", type=['png', 'jpg', 'jpeg'])

# file uploader for adding PDF file
input_pdf = st.file_uploader("Choose a PDF file", type=['pdf'])
# -----------------------------------

# Text area for user input
input_text = st.text_area('Please paste the text here', height = 100).lower()

api_from_streamlite = st.secrets["GEMINI_KEY"]

# google gemini api using streamlit secrets
client = Client(api_key=api_from_streamlite)

chat = client.chats.create(model="gemini-2.0-flash")


# Process inputs on button click
if st.button("Analyze"):
    try:
        # --- 分析に必要なコンテンツリストの初期化 ---
        contents_to_send = []
        
        # 1. 画像ファイルをcontentsリストに追加
        if input_image:
            try:
                # PIL Imageオブジェクトとして開く
                image = Image.open(input_image)
                contents_to_send.append(image)
                st.success("画像ファイルを準備しました。")
            except Exception as e:
                st.error(f"画像ファイルの処理中にエラーが発生しました: {e}")
                
        # 2. PDFファイルをcontentsリストに追加
        if input_pdf:
            # StreamlitのUploadedFileオブジェクトを直接渡します
            # Gemini APIのクライアントライブラリが、このファイルを処理します
            # PDFのページはGemini側で自動的に画像として扱われます
            contents_to_send.append(input_pdf)
            st.success("PDFファイルを準備しました。")
        
        # 3. テキスト入力をcontentsリストに追加
        if input_text:
            contents_to_send.append(input_text)
        
        # --- モデルへの送信ロジックの修正 ---
        if contents_to_send:
            try:
                # 画像/PDFとテキストを含むリクエスト
                response = client.models.generate_content(
                    model="gemini-2.5-flash", 
                    contents=contents_to_send, # 画像、PDF、テキストを全て渡す
                    config=types.GenerateContentConfig(
                        temperature=0.1
                    ),
                )

                # 応答テキストの抽出と表示
                response_text = response.text if hasattr(response, 'text') else ""
                response_text = response_text.replace('role - user', '').replace('role - model', '').strip()
                st.markdown(response_text, unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"Gemini APIでの分析中にエラーが発生しました: {e}")

        # --- 画像もPDFもない場合 (通常のチャット) ---
        elif input_text:
            if input_text != 'stop':
                response = chat.send_message_stream(input_text)
                response_text = "".join([part.text for part in response if hasattr(part, 'text')])
                response_text = response_text.replace('role - user', '').replace('role - model', '').strip()
                st.markdown(response_text, unsafe_allow_html=True)
            else:
                st.info('Thank you for your conversation. Have a nice day!')
        
        else:
            st.warning("分析するには、画像、PDF、またはテキストのいずれかを入力してください。")

    except Exception as e:
        st.write(f"予期せぬエラーが発生しました: {e}")
