import streamlit as st
import json # JSONを扱うために必要

# Google Gemini APIを使うためのライブラリを読み込む
from google import genai
from google.genai import types
from google.genai import Client

# 画像を扱うためのライブラリ
from PIL import Image

import os
import io # PDFファイルを扱うために必要

# --- 状態管理のためのセッションステート初期化 ---
# アプリの状態を保持するために必須
if 'persona_created' not in st.session_state:
    # ペルソナが作成されたかどうか (Falseで初期状態)
    st.session_state['persona_created'] = False
if 'persona_info' not in st.session_state:
    # 作成されたペルソナ情報 (Markdownテキスト)
    st.session_state['persona_info'] = None
if 'persona_image_cropped' not in st.session_state:
    # トリミングされたペルソナ画像 (PIL.Imageオブジェクト)
    st.session_state['persona_image_cropped'] = None
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

# 画像/PDFファイル共通のペルソナ作成プロンプト
COMMON_PERSONA_PROMPT = """
あなたは、アップロードされたファイル（画像またはPDF）を「人間のような存在」として捉え、そのキャラクターの「ペルソナ」を作成するAIです。
ファイルの内容と性質に基づいて以下の3つの要素を考え、日本語のMarkdown形式で記述してください。

1. **名前**: このキャラクターの名前（例：サニー、古時計のロジャー、博士）
2. **性格**: このキャラクターの性格と口調。あなたは今後の会話でこの口調を守り通します。
3. **生い立ち/背景**: ファイルのオブジェクトまたは内容に基づいて想像した、簡単な生い立ちや物語。

作成したペルソナ情報のみを出力し、それ以外のコメントや挨拶は一切含めないでください。
"""

# 画像からトリミング領域（バウンディングボックス）を抽出するためのプロンプト
# JSON形式での出力を厳密に指示
TRIMMING_PROMPT = """
あなたは、画像から最も特徴的または主要なオブジェクトを特定し、その領域をトリミングするための座標をJSON形式で提供するAIです。
他のテキストは一切含めず、以下の形式のJSONのみを出力してください。

JSON形式:
{
  "x": (トリミング領域の左上のx座標。0から1000の範囲で、画像左端が0、右端が1000),
  "y": (トリミング領域の左上のy座標。0から1000の範囲で、画像上端が0、下端が1000),
  "width": (トリミング領域の幅。0から1000の範囲),
  "height": (トリミング領域の高さ。0から1000の範囲)
}

トリミングする領域は、画像全体の50%以上のサイズとし、主要な被写体が中央にくるように調整してください。
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
        image = Image.open(uploaded_file)
        contents_list.append(image)
        contents_list.append(COMMON_PERSONA_PROMPT)
    elif 'pdf' in file_type:
        # PDFファイルの場合
        uploaded_file.seek(0)
        pdf_bytes = uploaded_file.read()
        contents_list.append(types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf'))
        contents_list.append(COMMON_PERSONA_PROMPT)
    else:
        raise ValueError("サポートされていないファイル形式です。画像（PNG/JPG/JPEG）またはPDFファイルをアップロードしてください。")

    # 1. ペルソナ情報の生成
    response = client.models.generate_content(
        model="gemini-2.5-flash", 
        contents=contents_list,
        config=types.GenerateContentConfig(temperature=0.7),
    )
    
    persona_text = response.text
    st.session_state['persona_info'] = persona_text
    st.session_state['persona_created'] = True
    
    # ★★★ 2. 画像ファイルの場合のみ、トリミング処理を行う ★★★
    st.session_state['persona_image_cropped'] = None # まずリセット
    if 'image' in file_type:
        st.toast("画像の特徴的な部分を分析中です...", icon="✂️")
        
        # 2-1. トリミング座標の取得
        trim_response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[image, TRIMMING_PROMPT],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "x": {"type": "INTEGER"},
                        "y": {"type": "INTEGER"},
                        "width": {"type": "INTEGER"},
                        "height": {"type": "INTEGER"}
                    }
                }
            )
        )
        
        try:
            # 2-2. JSON応答をパース
            trim_data = json.loads(trim_response.text)
            
            # 画像の実際のサイズを取得
            img_width, img_height = image.size
            
            # 2-3. 座標を実際のピクセル値に変換し、トリミング（0-1000スケールからの変換）
            # クロップ領域を (left, upper, right, lower) 形式で定義
            x = int(trim_data.get("x", 0) * img_width / 1000)
            y = int(trim_data.get("y", 0) * img_height / 1000)
            w = int(trim_data.get("width", 1000) * img_width / 1000)
            h = int(trim_data.get("height", 1000) * img_height / 1000)
            
            # 領域が画像サイズを超えないように調整
            right = min(x + w, img_width)
            bottom = min(y + h, img_height)

            # トリミングを実行
            cropped_image = image.crop((x, y, right, bottom))
            st.session_state['persona_image_cropped'] = cropped_image
            
        except Exception as e:
            st.warning(f"トリミング座標の解析に失敗しました。画像全体を表示します。エラー: {e}")
            st.session_state['persona_image_cropped'] = image # 失敗時は全体を表示

    # 3. ペルソナ情報を使ったチャットセッションの開始
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
    
    # 4. 最初の挨拶を作成し、履歴に追加
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
    st.session_state['persona_image_cropped'] = None # トリミング画像もリセット
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

    # ★★★ トリミングされたペルソナ画像を表示 ★★★
    if st.session_state['persona_image_cropped']:
        st.image(st.session_state['persona_image_cropped'], caption="トリミングされた特徴的な部分", width=300)
    elif 'pdf' in input_file.type:
        st.info("PDFファイルはトリミング画像を作成できません。")
    
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
