import streamlit as st

# Google Gemini APIを使うためのライブラリを読み込む
from google import genai
from google.genai import types
from google.genai import Client

# 画像を扱うためのライブラリ
from PIL import Image

import os

# --- 状態管理のためのセッションステート初期化 ---
# アプリの状態を保持するために必須
if 'persona_created' not in st.session_state:
    # ペルソナが作成されたかどうか (Falseで初期状態)
    st.session_state['persona_created'] = False
if 'persona_info' not in st.session_state:
    # 作成されたペルソナ情報 (Markdownテキスト)
    st.session_state['persona_info'] = None
if 'persona_image_url' not in st.session_state:
    # 生成されたペルソナ画像のURL
    st.session_state['persona_image_url'] = None
if 'chat_session' not in st.session_state:
    # ペルソナの性格設定がされたチャットセッション
    st.session_state['chat_session'] = None
if 'messages' not in st.session_state:
    # 会話履歴を格納するリスト
    st.session_state['messages'] = []
if 'file_key' not in st.session_state:
    # 新しいファイルがアップロードされたかチェックするためのキー
    st.session_state['file_key'] = None


# --- AI（Gemini）の設定と初期化 ---

# Streamlitのシークレット機能を使ってAPIキーを安全に取得
api_from_streamlite = st.secrets["GEMINI_KEY"]

# AIクライアントの準備
client = Client(api_key=api_from_streamlite)

# --- プロンプト定義 ---

# 画像ファイルがアップロードされた場合に使うプロンプト
PERSONA_PROMPT = """
あなたは、アップロードされた画像を「人間のような存在」として捉え、その画像を擬人化したキャラクターの「ペルソナ」を作成するAIです。
以下の3つの要素を考え、日本語のMarkdown形式で記述してください。

1. **名前**: このキャラクターの名前（例：サニー、古時計のロジャー）
2. **性格**: このキャラクターの性格と口調。あなたは今後の会話でこの口調を守り通します。
3. **生い立ち/背景**: 画像のオブジェクトに基づいて想像した、簡単な生い立ちや物語。

作成したペルソナ情報のみを出力し、それ以外のコメントや挨拶は一切含めないでください。
"""
# PDFファイルがアップロードされた場合に使うプロンプト
PDF_PERSONA_PROMPT = """
あなたは、アップロードされたPDFファイルを「書類を擬人化した存在」として捉え、そのキャラクターの「ペルソナ」を作成するAIです。
ファイルの内容と性質に基づいて以下の3つの要素を考え、日本語のMarkdown形式で記述してください。

1. **名前**: このキャラクターの名前（例：博士、契約書のジョニー）
2. **性格**: このキャラクターの性格と口調。あなたは今後の会話でこの口調を守り通します。
3. **生い立ち/背景**: PDFファイルの内容に基づいて想像した、簡単な目的や物語、役割。

作成したペルソナ情報のみを出力し、それ以外のコメントや挨拶は一切含めないでください。
"""

# 画像生成AIのためのプロンプトを生成する指示
IMAGE_PROMPT_GENERATION_INSTRUCTION = """
以下のペルソナ情報に基づいて、このキャラクターを表すイラストのプロンプトを英語で生成してください。
プロンプトは画像生成AIが理解しやすいように、詳細かつ具体的に記述し、複数のキーワードや描写を含めてください。
**例:** "A vibrant, cheerful sun character with a warm smile, made of golden light, floating in a clear blue sky, cartoon style, warm colors, gentle rays."
**例:** "An old, wise grandfather clock with a gentle face, wearing a monocle, sitting in a dimly lit antique shop, realistic painting, detailed, nostalgic atmosphere."
生成されたプロンプト以外は一切含めないでください。

ペルソナ情報:
{persona_info}
"""

# --- ペルソナ作成処理関数 ---
def create_persona(client, uploaded_file):
    """ファイルを分析し、ペルソナ情報を作成してチャットセッションを開始する"""
    
    # 渡すコンテンツとプロンプトを準備
    contents_list = []
    
    # ファイルタイプによって処理を分岐
    file_type = uploaded_file.type
    
    if 'image' in file_type:
        # 画像ファイルの場合
        contents_list.append(Image.open(uploaded_file))
        current_persona_prompt = PERSONA_PROMPT
    elif 'pdf' in file_type:
        # PDFファイルの場合、UploadedFileオブジェクトからバイナリデータを取得し、Partとしてラップ
        uploaded_file.seek(0) # ファイルポインタを先頭に戻す
        pdf_bytes = uploaded_file.read()
        
        # Part.from_bytes() を使用してMIMEタイプを明示
        contents_list.append(types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf'))
        current_persona_prompt = PDF_PERSONA_PROMPT
    else:
        raise ValueError("サポートされていないファイル形式です。画像（PNG/JPG/JPEG）またはPDFファイルをアップロードしてください。")

    contents_list.append(current_persona_prompt)
        
    # 1. ペルソナ情報の生成
    response = client.models.generate_content(
        model="gemini-2.5-flash", 
        contents=contents_list,
        config=types.GenerateContentConfig(temperature=0.7),
    )
    
    persona_text = response.text
    st.session_state['persona_info'] = persona_text
    st.session_state['persona_created'] = True
    
    # ★★★ 2. ペルソナ情報に基づいて画像生成プロンプトを作成 ★★★
    # Quota超過エラーを回避するため、画像生成処理を一時的にスキップ（コメントアウト）します。
    # st.toast("ペルソナのイメージ画像を作成中...", icon="🎨")
    # image_prompt_response = client.models.generate_content(
    #     model="gemini-2.5-flash", # プロンプト生成はテキストモデルでOK
    #     contents=[IMAGE_PROMPT_GENERATION_INSTRUCTION.format(persona_info=persona_text)],
    #     config=types.GenerateContentConfig(temperature=0.5),
    # )
    # image_generation_prompt = image_prompt_response.text
    
    # ★★★ 3. 画像生成AIを呼び出し、画像を生成 ★★★
    # image_model_response = client.models.generate_content(
    #     model="gemini-2.5-flash-image-preview", # 画像生成モデル
    #     contents=[image_generation_prompt],
    #     config=types.GenerateContentConfig(temperature=0.7),
    # )
    # # 生成された画像は通常、Imageオブジェクトのリストとして返される
    # if image_model_response.candidates and image_model_response.candidates[0].content.parts:
    #     # 最初に見つかった画像を取得
    #     first_image_part = next((p for p in image_model_response.candidates[0].content.parts if hasattr(p, 'image') and p.image), None)
    #     if first_image_part:
    #         # st.image で表示するためにImageオブジェクトをそのまま保存 (またはbase64エンコードされたURI)
    #         st.session_state['persona_image_url'] = first_image_part.image # Imageオブジェクトを直接保存
    
    # 4. ペルソナ情報を使ったチャットセッションの開始 (既存ロジック)
    system_instruction_text = (
        f"あなたは今、以下のペルソナに基づいて応答するチャットボットです。このペルソナを厳守し、あなたの生い立ちから考えられる知識や感情で応答してください。\n\n"
        f"ペルソナ情報:\n{persona_text}"
    )
    
    st.session_state['chat_session'] = client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=system_instruction_text
        )
    )
    
    # 5. 最初の挨拶を作成し、履歴に追加 (既存ロジック)
    try:
        name = persona_text.split('**名前**:')[-1].splitlines()[0].strip().strip('* ')
    except:
        name = "謎のAI"
        
    initial_greeting = f"やあ！私は{name}だよ。私についての質問はもちろん、なんでも話してくれていいんだよ。"
    
    st.session_state['messages'] = []
    st.session_state['messages'].append({"role": "model", "content": initial_greeting})
    
    return persona_text

# --- 会話リセット関数 ---
def reset_conversation():
    """会話履歴のみをリセットする"""
    if st.session_state['persona_created']:
        st.session_state['messages'] = []
        # 新しいチャットセッションを作成し直す必要はないが、最初の挨拶を再度追加する
        try:
            name = st.session_state['persona_info'].split('**名前**:')[-1].splitlines()[0].strip().strip('* ')
        except:
            name = "謎のAI"
        initial_greeting = f"やあ！私は{name}だよ。もう一度、私に話しかけてみてね。"
        st.session_state['messages'].append({"role": "model", "content": initial_greeting})
        st.toast("会話履歴をリセットしました！", icon="🗑️")


# --- 画面のレイアウトとUI ---

st.title('🤖 画像・PDFのペルソナと会話するチャットボット')
st.markdown("画像またはPDFをアップロードして「ペルソナ作成」ボタンを押すと、ファイルが擬人化されてあなたとお話します！")
st.markdown("---")

# 1. ファイルアップローダー
input_file = st.file_uploader("🖼️ ファイルを選んでね", type=['png', 'jpg', 'jpeg', 'pdf'])

# ファイルが新しくアップロードされたかチェックし、リセットが必要なら実行
if input_file and st.session_state['file_key'] != input_file.name:
    # 新しいファイルなので、ペルソナ作成状態をリセット
    st.session_state['file_key'] = input_file.name
    st.session_state['persona_created'] = False
    st.session_state['persona_info'] = None
    st.session_state['persona_image_url'] = None # 画像URLもリセット
    st.session_state['chat_session'] = None
    st.session_state['messages'] = []
    st.toast("新しいファイルがアップロードされました。ペルソナを作成しましょう！", icon="🖼️")


# 2. ペルソナ作成フェーズ (初期状態)
if not st.session_state['persona_created']:
    
    # ファイルがないとボタンを押せないようにする
    is_disabled = input_file is None
    button_label = "✨ ファイルからAIのペルソナを作成する"
    
    if st.button(button_label, disabled=is_disabled, help="画像またはPDFをアップロードすると押せるようになります。"):
        if input_file:
            try:
                with st.spinner('AIがファイルを分析し、ペルソナを作成中です...'):
                    create_persona(client, input_file)
                    # 画像生成をスキップしたため、メッセージを調整
                    st.success("ペルソナの作成が完了しました！チャットを開始してください。") 
                    
                st.rerun() # 画面を再実行してチャットUIを表示させる
            except Exception as e:
                st.error(f"ペルソナ作成中にエラーが発生しました: {e}")
                print(f"Error during persona creation: {e}")
                
# 3. チャットフェーズ (ペルソナ作成済み状態)
else:
    # ペルソナ情報の表示
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("🤖 あなたのチャット相手のペルソナ情報")
    with col2:
        st.button("🗑️ 会話をリセット", on_click=reset_conversation)

    # ★★★ 生成されたペルソナ画像を表示 ★★★
    # 画像生成がスキップされているため、画像は表示されません。
    if st.session_state['persona_image_url']:
        st.image(st.session_state['persona_image_url'], caption="AIが生成したペルソナのイメージ画像", width=300)
    
    st.markdown(st.session_state['persona_info'])
    st.markdown("---")

    # チャット履歴の表示
    for message in st.session_state['messages']:
        with st.chat_message(message["role"] if message["role"] != "model" else "assistant"):
            st.markdown(message["content"])

    # 新しい質問の入力
    prompt = st.chat_input("ペルソナに話しかけてみよう！")
    
    if prompt:
        st.session_state['messages'].append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner('ペルソナが考え中です...'):
                chat_session = st.session_state['chat_session']
                
                response_stream = chat_session.send_message_stream(prompt)
                
                full_response = ""
                response_container = st.empty()
                
                for chunk in response_stream:
                    if hasattr(chunk, 'text'):
                        full_response += chunk.text
                        response_container.markdown(full_response)
                        
                st.session_state['messages'].append({"role": "model", "content": full_response})
