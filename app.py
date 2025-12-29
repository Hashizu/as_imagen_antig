import streamlit as st
import os
import sys
from datetime import datetime

# パス設定
sys.path.append(os.getcwd())

from src.generator import ImageGenerator
from src.state_manager import StateManager, STATUS_EXCLUDED, STATUS_UNPROCESSED, STATUS_REGISTERED
from src.submission_manager import SubmissionManager
from dotenv import load_dotenv
import pandas as pd

# セットアップ
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")

st.set_page_config(layout="wide", page_title="AS Image Generator GUI")

def main():
    st.title("🎨 AS Image Generator & Gallery")

    if not API_KEY:
        st.error("OPENAI_API_KEY not found in .env")
        return

    # タブ設定
    tab1, tab2 = st.tabs(["🚀 Generate", "🖼️ Gallery & Submit"])

    # --- Tab 1: Generate ---
    with tab1:
        st.header("New Generation")
        
        col1, col2 = st.columns(2)
        with col1:
            keyword = st.text_input("Keyword (Main Theme)", placeholder="e.g. minimalist cat")
            tags = st.text_input("Mandatory Tags", placeholder="comma, separated, tags")
            n_images = st.number_input("Number of Variations", min_value=1, max_value=20, value=5)
        
        with col2:
            model = st.selectbox("Model", ["gpt-image-1.5", "dall-e-3"], index=0)
            
            # スタイル定義を取得して動的に設定
            # インスタンス化しなくても定義自体はimportできるが、クラスメソッドにしたので一旦インスタンスからとるか、
            # あるいは直接importする方が綺麗。ここではgeneratorを通して取得する。
            gen_instance = ImageGenerator(API_KEY)
            styles = gen_instance.get_styles()
            style_keys = list(styles.keys())
            style_labels = [styles[k]["label"] for k in style_keys]
            
            # ラベルで選択させ、キーに変換する
            selected_label = st.selectbox("Style", style_labels, index=0)
            # ラベルからキーを逆引き
            style = next(k for k, v in styles.items() if v["label"] == selected_label)
            
            # スタイルの説明を表示
            st.info(f"Style Prompt: {styles[style]['idea_prompt']}")

            size = st.selectbox("Size", ["1024x1024", "1024x1536", "1536x1024"], index=0)
        
        if st.button("Generate Images", type="primary"):
            if not keyword:
                st.warning("Please enter a keyword.")
            else:
                with st.spinner(f"Generating {n_images} images for '{keyword}'..."):
                    run_generation(keyword, tags, n_images, model, style, size)
                st.success("Generation Complete! Go to Gallery tab to review.")

    # --- Tab 2: Gallery ---
    with tab2:
        st.header("Image Gallery")
        
        # ステータスごとのタブを作成
        gallery_tab1, gallery_tab2, gallery_tab3 = st.tabs(["Unprocessed", "Registered", "Excluded"])
        
        with gallery_tab1:
            render_gallery_content(STATUS_UNPROCESSED)
            
        with gallery_tab2:
            render_gallery_content(STATUS_REGISTERED)
            
        with gallery_tab3:
            render_gallery_content(STATUS_EXCLUDED)


def render_gallery_content(status_filter):
    """ギャラリーのコンテンツを描画するヘルパー関数"""
    state_mgr = StateManager()
    display_images = state_mgr.get_images_by_status(status_filter)
    
    if not display_images:
        st.info(f"No images found in {status_filter}.")
        return

    st.write(f"Found {len(display_images)} images.")
    
    if 'selected_images' not in st.session_state:
        st.session_state.selected_images = []

    # 一括アクションバー
    st.divider()
    
    selected_paths = []
    
    col_act1, col_act2 = st.columns([1, 4])
    
    # ボタンのキーをユニークにするためにstatus_filterを使用
    key_suffix = f"_{status_filter}"
    
    with col_act1:
        if status_filter == STATUS_UNPROCESSED:
            if st.button("📤 Register Selected", key=f"btn_reg{key_suffix}"):
                 process_registration(keyword="batch_submit", status_filter=status_filter)
                 st.rerun()
        else:
            if st.button("↩️ Revert to Unprocessed", key=f"btn_rev{key_suffix}"):
                process_revert(status_filter)
                st.rerun()
                
    with col_act2:
        if status_filter == STATUS_UNPROCESSED:
            if st.button("🗑️ Exclude Selected", key=f"btn_exc{key_suffix}"):
                process_exclusion(status_filter)
                st.rerun()

    st.divider()

    # グリッド表示
    cols = st.columns(4)
    for idx, img in enumerate(display_images):
        file_path = img['path']
        
        with cols[idx % 4]:
            try:
                st.image(file_path, width="stretch")
                
                # keyにstatusを含めることでユニークにする
                unique_key = f"chk_{status_filter}_{file_path}"
                
                # タブ切り替え時はそれぞれのタブでの選択状態を維持したい
                # しかしシンプルにするため、画面遷移（rerun）で選択はクリアされる前提とするか、
                # あるいは `current_selection` を辞書型にして `status` ごとに持つか。
                # ここではシンプルに「現在のタブの選択」のみを扱うようにするが、
                # st.checkboxはkeyが同じなら状態を保持する。
                
                # デフォルト値ロジック
                # Unprocessedタブは選別作業用なので、デフォルトONにしておくと「悪いものを外す」フローになる。
                # Registered/Excludedは確認用なので、デフォルトOFF。
                default_val = (status_filter == STATUS_UNPROCESSED)
                
                # ただしrerun直後のデフォルト値復元を考慮する必要があるが、
                # keyが一意ならStreamlitがstateを覚えてくれるはず。
                
                is_selected = st.checkbox("Select", key=unique_key, value=default_val)
                if is_selected:
                    selected_paths.append(file_path)
                    
                with st.expander("Details"):
                    st.caption(f"Prompt: {img.get('prompt', '')[:100]}...")
                    st.caption(f"Date: {img.get('added_at', '')}")

            except Exception as e:
                st.error(f"Error loading {file_path}")

    # 選択状態をSession Stateに保存 (辞書型で管理したほうが安全だが、今回はシンプルに処理直前に取得する形をとる)
    # process_xxx() 関数内では、st.session_stateのwidget keyから直接値を取るか、
    # あるいはここで保存した値を渡すか。
    # 複数のタブを行き来した場合、 `current_selection` が上書きされるとまずい。
    # よって、 `current_selection` は 「現在アクティブなタブの選択」 ではなく、
    # 「処理実行時に参照するための、各タブごとの選択状態」であるべきだが、
    # Streamlitの仕様上、checkboxの値は常に session_state[unique_key] にある。
    # process関数側で "chk_{status_filter}_" で始まるキーを集計するのが確実。
    
    # 互換性のため、一旦ここに保存するが、キーを分ける
    st.session_state[f'selection_{status_filter}'] = selected_paths


def run_generation(keyword, tags, n_ideas, model, style, size):
    """メイン生成プロセス (Upscaleなし)"""
    generator = ImageGenerator(API_KEY, model_name=model)
    state_mgr = StateManager()

    # ディレクトリ準備
    timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
    safe_keyword = keyword.replace(" ", "_").replace("/", "")
    base_output_dir = os.path.join("output", f"{timestamp}_{safe_keyword}")
    images_dir = os.path.join(base_output_dir, "generated_images")
    os.makedirs(images_dir, exist_ok=True)

    # アイデア生成
    st.write("Creating ideas...")
    ideas = generator.generate_image_description(keyword, n_ideas=n_ideas, style=style)
    
    csv_data = []
    progress_bar = st.progress(0)

    for i, idea in enumerate(ideas):
        try:
            draw_prompt = generator.generate_drawing_prompt(idea, style=style)
            
            filename = f"img_{i:03d}.png"
            output_path = os.path.join(images_dir, filename)
            
            generator.generate_image(prompt=draw_prompt, output_path=output_path, size=size)
            
            csv_data.append({"filename": filename, "prompt": draw_prompt})
            
            # DBに即時登録 (ファイルパス, プロンプトなど)
            # ステータスはデフォルトでUNPROCESSED
            # StateManagerのscanに頼らず、ここで明示的に同期をとると確実
            # ただしStateManagerは現在pathをkeyにしているため、scanを呼ぶのが楽
            
        except Exception as e:
            st.error(f"Error generating image {i}: {e}")
        
        progress_bar.progress((i + 1) / len(ideas))

    # CSV保存
    if csv_data:
        # 必須タグを全レコードに追加
        for item in csv_data:
            item['tags'] = tags
            
        df = pd.DataFrame(csv_data)
        df.to_csv(os.path.join(images_dir, "prompt.csv"), index=False, encoding='utf-8-sig')

    # 最後にDBスキャンして反映
    state_mgr.scan_and_sync()


def process_registration(keyword, status_filter=STATUS_UNPROCESSED):
    """選択された画像を登録処理へ回す"""
    selected = st.session_state.get(f'selection_{status_filter}', [])
    if not selected:
        st.warning("No images selected.")
        return

    submit_mgr = SubmissionManager(API_KEY)
    state_mgr = StateManager()
    
    # パスから必要なメタデータ辞書を復元（DBから）
    target_images = []
    for path in selected:
        # DB上の情報を取得
        # パスが絶対パスか相対パスか注意
        rel_path = os.path.relpath(path, os.getcwd()).replace("\\", "/")
        if rel_path in state_mgr.db:
            data = state_mgr.db[rel_path].copy()
            data['path'] = rel_path
            target_images.append(data)
    
    with st.spinner(f"Upscaling and Registering {len(target_images)} images..."):
        submit_mgr.process_submission(target_images, keyword=keyword)
    
    st.success("Registration Complete!")


def process_exclusion(status_filter=STATUS_UNPROCESSED):
    """選択された画像を除外ステータスにする"""
    selected = st.session_state.get(f'selection_{status_filter}', [])
    if not selected:
        st.warning("No images selected.")
        return

    state_mgr = StateManager()
    state_mgr.update_status(selected, STATUS_EXCLUDED)
    st.success(f"Excluded {len(selected)} images.")



def process_revert(status_filter):
    """選択された画像を未処理ステータスに戻す"""
    selected = st.session_state.get(f'selection_{status_filter}', [])
    if not selected:
        st.warning("No images selected.")
        return

    state_mgr = StateManager()
    state_mgr.update_status(selected, STATUS_UNPROCESSED)
    st.success(f"Reverted {len(selected)} images to Unprocessed.")


if __name__ == "__main__":
    main()
