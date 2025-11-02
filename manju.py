import streamlit as st
from google import genai
from google.genai import types
from google.genai import Client
from PIL import Image
# PDFを画像に変換するためのライブラリをインポート
from pdf2image import convert_from_bytes 
import os
import io

st.title('multi-modal chatbot')

# file uploader for adding image file
input_image = st.file_uploader("Choose an image file", type=['png', 'jpg', 'jpeg'])

# file uploader for adding PDF file
input_pdf = st.file_uploader("Choose a PDF file", type=['pdf'])

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
                
        # 2. PDFファイルを画像に変換してcontentsリストに追加 (重要: 修正箇所)
        if input_pdf:
            st.info("PDFを画像に変換中...")
            try:
                # アップロードされたファイルをバイトデータとして読み込む
                pdf_bytes = input_pdf.getvalue()
                
                # pdf2imageを使用して、バイトデータからPIL Imageオブジェクトのリストに変換
                # ページ数が多い場合、ここで時間がかかります
                images = convert_from_bytes(pdf_bytes)
                
                # 変換された画像をcontentsリストに追加
                # PDFの全ページが、それぞれ独立した画像としてモデルに送られます
                contents_to_send.extend(images) 
                
                st.success(f"PDF ({len(images)}ページ) の画像変換が完了しました。")
                
            except Exception as e:
                st.error(f"PDFの画像変換中にエラーが発生しました。: {e}")
                st.warning("ヒント: 'pdf2image'と、その前提となる'Poppler'が正しくインストールされているか確認してください。")
                
        # 3. テキスト入力をcontentsリストに追加
        if input_text:
            contents_to_send.append(input_text)
        
        
        # --- モデルへの送信ロジック ---
        if contents_to_send:
            try:
                # 画像/PDF画像とテキストを含むリクエスト
                # PDFが画像として扱われるため、ファイルのアップロード/削除処理は不要になりました
                response = client.models.generate_content(
                    model="gemini-2.5-flash", 
                    contents=contents_to_send, # 画像、PDF画像、テキストを全て渡す
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
            
            # 💡 以前のコードで必要だった file upload/delete 処理は不要になりました
            
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
