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
            style = st.selectbox("Style", ["japanese_simple", "photorealistic"], index=0)
            size = st.selectbox("Size", ["1024x1024", "1024x1792"], index=0)
        
        if st.button("Generate Images", type="primary"):
            if not keyword:
                st.warning("Please enter a keyword.")
            else:
                with st.spinner(f"Generating {n_images} images for '{keyword}'..."):
                    run_generation(keyword, tags, n_images, model, style, size)
                st.success("Generation Complete! Go to Gallery tab to review.")

    # --- Tab 2: Gallery ---
    with tab2:
        col_head, col_filter = st.columns([2, 1])
        with col_head:
            st.header("Image Gallery")
        with col_filter:
            # ステータスフィルター
            status_filter = st.selectbox(
                "Filter by Status", 
                [STATUS_UNPROCESSED, STATUS_REGISTERED, STATUS_EXCLUDED],
                index=0
            )
        
        state_mgr = StateManager()
        # 選択されたステータスの画像を取得
        display_images = state_mgr.get_images_by_status(status_filter)
        
        if not display_images:
            st.info(f"No images found with status: {status_filter}")
        else:
            st.write(f"Found {len(display_images)} images.")
            
            # 選択用ステート管理
            # フィルター切り替え時に選択状態をクリアしないとID衝突などが起きる可能性があるが、
            # ID(キー)はパスベースなのでユニーク。ただし選択したまま別画面に行くと混乱するかも。
            # 一旦セッションはクリアしないが、ボタン押下時にフィルタと整合性を取る。
            
            if 'selected_images' not in st.session_state:
                st.session_state.selected_images = []

            # 一括アクションバー (フィルタによって出し分け)
            st.divider()
            
            # 選択された画像のパスを保持するリスト
            selected_paths = []
            
            # グリッド描画と選択収集
            # アクションボタンをグリッドの上に置くか下に置くか。上に置く場合、selected_pathsがまだ空。
            # Streamlitのフロー上、ボタン押下時のcallbackでsession_state['current_selection']を見る形なら上に置ける。
            
            col_act1, col_act2 = st.columns([1, 4])
            
            with col_act1:
                if status_filter == STATUS_UNPROCESSED:
                    if st.button("📤 Register Selected"):
                         process_registration(keyword="batch_submit")
                         st.rerun()
                else:
                    # 登録済 or 除外 の場合は「元に戻す」
                    if st.button("↩️ Revert to Unprocessed"):
                        process_revert()
                        st.rerun()
                        
            with col_act2:
                if status_filter == STATUS_UNPROCESSED:
                    if st.button("🗑️ Exclude Selected"):
                        process_exclusion()
                        st.rerun()
                # 他のステータスの時は除外ボタンは不要（Revertしてからやり直せば良い）

            st.divider()

            # グリッド表示
            cols = st.columns(4)
            for idx, img in enumerate(display_images):
                file_path = img['path']
                
                with cols[idx % 4]:
                    try:
                        st.image(file_path, use_container_width=True)
                        
                        # フィルタ切り替えでrerunすると前のcheckboxのstateが残る場合がある。
                        # keyにstatusを含めることでユニークにする
                        unique_key = f"chk_{status_filter}_{file_path}"
                        
                        # デフォルト選択状態: 未処理ならON、それ以外はOFFが自然か？
                        # 全部ONだと「除外したのを戻したい」時に全部チェック外すのが面倒。
                        # 未処理画面=選別フロー(基本Keep) -> Default ON
                        # 履歴画面=検索フロー(基本View) -> Default OFF
                        default_val = (status_filter == STATUS_UNPROCESSED)
                        
                        is_selected = st.checkbox("Select", key=unique_key, value=default_val)
                        if is_selected:
                            selected_paths.append(file_path)
                            
                        with st.expander("Details"):
                            st.caption(f"Prompt: {img.get('prompt', '')[:100]}...")
                            st.caption(f"Date: {img.get('added_at', '')}")

                    except Exception as e:
                        st.error(f"Error loading {file_path}")

            # 選択状態をSession Stateに保存
            st.session_state.current_selection = selected_paths


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
            draw_prompt = generator.generate_drawing_prompt(idea)
            
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
        df = pd.DataFrame(csv_data)
        df.to_csv(os.path.join(images_dir, "prompt.csv"), index=False, encoding='utf-8-sig')

    # 最後にDBスキャンして反映
    state_mgr.scan_and_sync()


def process_registration(keyword):
    """選択された画像を登録処理へ回す"""
    selected = st.session_state.get('current_selection', [])
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


def process_exclusion():
    """選択された画像を除外ステータスにする"""
    selected = st.session_state.get('current_selection', [])
    if not selected:
        st.warning("No images selected.")
        return

    state_mgr = StateManager()
    state_mgr.update_status(selected, STATUS_EXCLUDED)
    st.success(f"Excluded {len(selected)} images.")



def process_revert():
    """選択された画像を未処理ステータスに戻す"""
    selected = st.session_state.get('current_selection', [])
    if not selected:
        st.warning("No images selected.")
        return

    state_mgr = StateManager()
    state_mgr.update_status(selected, STATUS_UNPROCESSED)
    st.success(f"Reverted {len(selected)} images to Unprocessed.")


if __name__ == "__main__":
    main()
