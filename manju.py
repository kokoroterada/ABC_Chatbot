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
if 'chat_session' not in st.session_state:
    # ペルソナの性格設定がされたチャットセッション
    st.session_state['chat_session'] = None
if 'messages' not in st.session_state:
    # 会話履歴を格納するリスト
    st.session_state['messages'] = []
if 'image_key' not in st.session_state:
    # 新しい画像がアップロードされたかチェックするためのキー
    st.session_state['image_key'] = None


# --- AI（Gemini）の設定と初期化 ---

# Streamlitのシークレット機能を使ってAPIキーを安全に取得
api_from_streamlite = st.secrets["GEMINI_KEY"]

# AIクライアントの準備
client = Client(api_key=api_from_streamlite)

# --- ペルソナ生成のためのプロンプト ---
PERSONA_PROMPT = """
あなたは、アップロードされた画像を「人間のような存在」として捉え、その画像を擬人化したキャラクターの「ペルソナ」を作成するAIです。
以下の3つの要素を考え、日本語のMarkdown形式で記述してください。

1. **名前**: このキャラクターの名前（例：サニー、古時計のロジャー）
2. **性格**: このキャラクターの性格と口調。あなたは今後の会話でこの口調を守り通します。
3. **生い立ち/背景**: 画像のオブジェクトに基づいて想像した、簡単な生い立ちや物語。

作成したペルソナ情報のみを出力し、それ以外のコメントや挨拶は一切含めないでください。
"""

# --- ペルソナ作成処理関数 ---
def create_persona(client, image):
    """画像を分析し、ペルソナ情報を作成してチャットセッションを開始する"""
    
    # 1. ペルソナ情報の生成
    response = client.models.generate_content(
        model="gemini-2.5-flash", 
        contents=[image, PERSONA_PROMPT],
        config=types.GenerateContentConfig(temperature=0.7),
    )
    
    persona_text = response.text
    st.session_state['persona_info'] = persona_text
    st.session_state['persona_created'] = True
    
    # 2. ペルソナ情報を使ったチャットセッションの開始
    # ペルソナ情報を「システム指示」として設定し、AIにキャラクターになりきらせる
    system_instruction_text = (
        f"あなたは今、以下のペルソナに基づいて応答するチャットボットです。このペルソナを厳守し、あなたの生い立ちから考えられる知識や感情で応答してください。\n\n"
        f"ペルソナ情報:\n{persona_text}"
    )
    
    # 新しいチャットセッションを作成
    st.session_state['chat_session'] = client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=system_instruction_text
        )
    )
    
    # 3. 最初の挨拶を作成し、履歴に追加
    try:
        # ペルソナ情報から名前を抽出して挨拶に使う
        name = persona_text.split('**名前**:')[-1].splitlines()[0].strip().strip('* ')
    except:
        name = "謎のAI" # 抽出失敗時のフォールバック
        
    initial_greeting = f"やあ！私は{name}だよ。私についての質問はもちろん、なんでも話してくれていいんだよ。"
    
    # 会話履歴の初期化と最初のメッセージ追加
    st.session_state['messages'] = []
    st.session_state['messages'].append({"role": "model", "content": initial_greeting})
    
    return persona_text

# --- 画面のレイアウトとUI ---

st.title('🤖 画像のペルソナと会話するチャットボット')
st.markdown("画像をアップロードして「ペルソナ作成」ボタンを押すと、画像が擬人化されてあなたとお話します！")
st.markdown("---")

# 1. 画像アップローダー
input_image = st.file_uploader("🖼️ 画像ファイルを選んでね", type=['png', 'jpg', 'jpeg'])

# 画像が新しくアップロードされたかチェックし、リセットが必要なら実行
if input_image and st.session_state['image_key'] != input_image.name:
    # 新しい画像なので、ペルソナ作成状態をリセット
    st.session_state['image_key'] = input_image.name
    st.session_state['persona_created'] = False
    st.session_state['persona_info'] = None
    st.session_state['chat_session'] = None
    st.session_state['messages'] = []
    st.toast("新しい画像がアップロードされました。ペルソナを作成しましょう！", icon="🖼️")


# 2. ペルソナ作成フェーズ (初期状態)
if not st.session_state['persona_created']:
    
    # 1点目の要望: 画像がないとボタンを押せないようにする
    is_disabled = input_image is None
    button_label = "✨ 画像からAIのペルソナを作成する"
    
    if st.button(button_label, disabled=is_disabled, help="画像をアップロードすると押せるようになります。"):
        if input_image:
            # ペルソナ生成ロジックの実行
            try:
                with st.spinner('AIが画像を分析し、ペルソナを作成中です...'):
                    image = Image.open(input_image)
                    create_persona(client, image)
                    st.success("ペルソナの作成が完了しました！チャットを開始してください。")
                    
                # 画面を再実行してチャットUIを表示させる
                st.rerun() 
            except Exception as e:
                st.error(f"ペルソナ作成中にエラーが発生しました: {e}")
                print(f"Error during persona creation: {e}")
                
# 3. チャットフェーズ (ペルソナ作成済み状態)
else:
    # ペルソナ情報の表示
    st.subheader("🤖 あなたのチャット相手のペルソナ情報")
    st.markdown(st.session_state['persona_info'])
    st.markdown("---")

    # チャット履歴の表示
    for message in st.session_state['messages']:
        # st.chat_messageを使って、roleに応じてアイコンを自動で表示
        with st.chat_message(message["role"] if message["role"] != "model" else "assistant"):
            st.markdown(message["content"])

    # 新しい質問の入力
    prompt = st.chat_input("ペルソナに話しかけてみよう！")
    
    if prompt:
        # ユーザーの質問を履歴に追加
        st.session_state['messages'].append({"role": "user", "content": prompt})
        
        # ユーザーのメッセージを画面に表示
        with st.chat_message("user"):
            st.markdown(prompt)

        # AIの応答生成
        with st.chat_message("assistant"):
            with st.spinner('ペルソナが考え中です...'):
                chat_session = st.session_state['chat_session']
                
                # ストリーミングで応答を受け取る
                response = chat_session.send_message_stream(prompt)
                
                # ストリームを処理し、画面に表示
                full_response = st.write_stream(response)
                
                # 履歴にAIの応答を追加
                st.session_state['messages'].append({"role": "model", "content": full_response})
