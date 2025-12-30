"""
Streamlit application for Adobe Stock Image Generator.
Handles UI, image generation, gallery viewing, and state management.
"""
import sys
import os
from datetime import datetime
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# パス設定
sys.path.append(os.getcwd())

# pylint: disable=wrong-import-position
from src.generator import ImageGenerator
from src.state_manager import (
    StateManager, STATUS_EXCLUDED, STATUS_UNPROCESSED, STATUS_REGISTERED
)
from src.submission_manager import SubmissionManager
from src.storage import S3Manager

# セットアップ
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")

if "keyword_input" not in st.session_state:
    st.session_state.keyword_input = ""
if "tags_input" not in st.session_state:
    st.session_state.tags_input = ""

@st.dialog("Image Details")
def view_image_details(image_path, prompt, tags, keyword):
    """
    Show image details in a modal dialog.
    """
    st.image(image_path, width="stretch")
    st.caption(f"Prompt: {prompt}")
    st.caption(f"Tags: {tags}")
    if keyword:
        st.caption(f"Keyword: {keyword}")

    if st.button("✨ Use Settings for Generation", type="primary"):
        # キーワードがあればそれを使う。なければプロンプトで代用。
        if keyword:
            st.session_state.keyword_input = keyword
        else:
            st.session_state.keyword_input = prompt

        st.session_state.tags_input = tags
        
        # Navigationの強制変更
        st.session_state.navigation_mode = "🚀 Generate"
        
        st.toast("Settings loaded! Switching to Generate tab...", icon="✅")
        st.rerun()

def main():
    """
    Main application entry point.
    """
    st.set_page_config(layout="wide", page_title="AS画像屋さん")
    st.title("🎨 AS画像屋さん")

    if not API_KEY:
        st.error("OPENAI_API_KEY not found in .env")
        return

    # サイドバーナビゲーション
    if "navigation_mode" not in st.session_state:
        st.session_state.navigation_mode = "🚀 Generate"

    # ModeもPillsにして統一感を出す
    mode = st.sidebar.pills(
        "Navigation",
        ["🚀 Generate", "🖼️ Gallery"],
        key="navigation_mode"
    )
    if not mode:
        mode = "🚀 Generate"
    st.sidebar.divider()

    # --- Mode: Generate ---
    if mode == "🚀 Generate":
        render_generate_tab()

    # --- Mode: Gallery ---
    elif mode == "🖼️ Gallery":
        render_gallery_tab()


def render_generate_tab():
    """
    Render elements for the Generation tab.
    """
    st.header("New Generation")

    # keyを指定してsession_stateと紐付ける
    keyword = st.text_input(
        "Keyword (Main Theme)",
        placeholder="e.g. minimalist cat",
        key="keyword_input"
    )

    col1, col2 = st.columns(2)
    with col1:
        tags = st.text_input(
            "Mandatory Tags",
            placeholder="comma, separated, tags",
            key="tags_input"
        )
        n_images = st.number_input(
            "Number of Variations",
            min_value=1, max_value=20, value=5
        )
        size = st.selectbox(
            "Size",
            ["1024x1024", "1024x1536", "1536x1024"],
            index=0
        )

    with col2:
        model = st.selectbox(
            "Model",
            ["gpt-image-1.5", "dall-e-3"],
            index=0
        )

        # スタイル定義を取得して動的に設定
        gen_instance = ImageGenerator(API_KEY)
        styles = gen_instance.get_styles()
        style_keys = list(styles.keys())
        style_labels = [styles[k]["label"] for k in style_keys]

        selected_label = st.selectbox("Style", style_labels, index=0)
        style = next(k for k, v in styles.items() if v["label"] == selected_label)

        # スタイルの説明を表示
        with st.expander("Style Details"):
            st.info(f"Style Prompt: {styles[style]['idea_prompt']}")

    if st.button("Generate Images", type="primary"):
        if not keyword:
            st.warning("Please enter a keyword.")
        else:
            with st.spinner(f"Generating {n_images} images for '{keyword}'..."):
                run_generation(keyword, tags, n_images, model, style, size)
            st.success("Generation Complete! Go to Gallery tab to review.")


def render_gallery_tab():
    """
    Render elements for the Gallery tab.
    """
    st.header("Image Gallery")

    # サイドバーでフィルタ選択 (pillsを使用)
    status_filter_label = st.sidebar.pills(
        "Filter Status",
        ["Unprocessed", "Registered", "Excluded"],
        default="Unprocessed"
    )

    # pillsは未選択(None)がありうるが、default指定していれば基本大丈夫。
    # 万が一NoneならUnprocessedにする
    if not status_filter_label:
        status_filter_label = "Unprocessed"

    # ラベルから定数へ変換
    status_map = {
        "Unprocessed": STATUS_UNPROCESSED,
        "Registered": STATUS_REGISTERED,
        "Excluded": STATUS_EXCLUDED
    }
    status_filter = status_map[status_filter_label]

    render_gallery_content(status_filter)


@st.cache_data(ttl=86400)
def load_s3_image(key: str) -> bytes:
    """S3から画像をロードしてキャッシュする"""
    s3 = S3Manager()
    return s3.download_file(key)

def render_gallery_content(status_filter): # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    """
    Render gallery content based on the selected status filter.
    Includes Pagination and Cache.
    """
    state_mgr = StateManager()
    all_images = state_mgr.get_images_by_status(status_filter)

    if not all_images:
        st.info(f"No images found in {status_filter}.")
        # 画像がない場合でも再度スキャンできるボタンがあると便利
        if st.sidebar.button("Forced Rescan"):
            state_mgr.scan_and_sync()
            st.rerun()
        return

    st.write(f"Found {len(all_images)} images.")

    # Pagination Setup
    items_per_page = 30
    if f'page_{status_filter}' not in st.session_state:
        st.session_state[f'page_{status_filter}'] = 0
    
    current_page = st.session_state[f'page_{status_filter}']
    total_pages = (len(all_images) + items_per_page - 1) // items_per_page
    
    start_idx = current_page * items_per_page
    end_idx = min(start_idx + items_per_page, len(all_images))
    display_images = all_images[start_idx:end_idx]

    # Pagination UI
    col_p1, col_p2, col_p3 = st.columns([1, 2, 1])
    with col_p1:
        if st.button("Previous", key=f"prev_{status_filter}", disabled=current_page == 0):
            st.session_state[f'page_{status_filter}'] -= 1
            st.rerun()
    with col_p2:
        st.write(f"Page {current_page + 1} / {total_pages}")
    with col_p3:
        if st.button("Next", key=f"next_{status_filter}", disabled=current_page >= total_pages - 1):
            st.session_state[f'page_{status_filter}'] += 1
            st.rerun()

    if 'selected_images' not in st.session_state:
        st.session_state.selected_images = []

    # サイドバーにアクションボタンを配置
    st.sidebar.divider()
    st.sidebar.subheader("Actions")

    # アクションボタン
    key_suffix = f"_{status_filter}"
    if status_filter == STATUS_UNPROCESSED:
        if st.sidebar.button(
            "📤 Register Selected",
            key=f"btn_reg{key_suffix}",
            type="primary"
        ):
            process_registration(keyword="batch_submit", status_filter=status_filter)
            # Rerun is tricky here because logic inside process_registration needs to run first
            # We will handle download button inside process_registration

        if st.sidebar.button("🗑️ Exclude Selected", key=f"btn_exc{key_suffix}"):
            process_exclusion(status_filter)
            st.rerun()

        # Download Button (Persistent)
        if 'latest_zip_data' in st.session_state:
            st.sidebar.download_button(
                label="📦 Download Last Submission",
                data=st.session_state['latest_zip_data'],
                file_name=st.session_state['latest_zip_name'],
                mime="application/zip",
                key="btn_download_zip"
            )

    else:
        # Registered / Excluded
        if st.sidebar.button("↩️ Revert to Unprocessed", key=f"btn_rev{key_suffix}"):
            process_revert(status_filter)
            st.rerun()

    # グリッド表示
    selected_paths = []
    cols = st.columns(4)

    for idx, img in enumerate(display_images):
        file_path = img['path'] # S3 Key
        with cols[idx % 4]:
            try:
                # S3から画像を取得して表示
                img_bytes = load_s3_image(file_path)
                st.image(img_bytes, width="stretch")

                # 詳細ボタン
                if st.button("🔍 Details", key=f"btn_det_{status_filter}_{start_idx + idx}"):
                    view_image_details(
                        img_bytes, # Pass bytes instead of path for display
                        img.get('prompt', ''),
                        img.get('tags', ''),
                        img.get('keyword', '')
                    )

                unique_key = f"chk_{status_filter}_{file_path}"
                default_val = status_filter == STATUS_UNPROCESSED

                is_selected = st.checkbox("Select", key=unique_key, value=default_val)
                if is_selected:
                    selected_paths.append(file_path)

            except Exception as e: # pylint: disable=broad-exception-caught
                st.error(f"Error loading {file_path}")

    st.session_state[f'selection_{status_filter}'] = selected_paths


def run_generation(
    keyword, tags, n_ideas, model, style, size
): # pylint: disable=too-many-arguments, too-many-positional-arguments, too-many-locals
    """
    Execute the image generation process.
    """
    generator = ImageGenerator(API_KEY, model_name=model)

    # ディレクトリ準備
    images_dir = _setup_output_dirs(keyword)

    # アイデア生成
    st.write("Creating ideas...")
    ideas = generator.generate_image_description(keyword, n_ideas=n_ideas, style=style)

    csv_data = _generate_images_loop(
        generator, ideas, images_dir, style, size, keyword
    )

    # CSV保存
    # CSV保存
    if csv_data:
        for item in csv_data:
            item['tags'] = tags

        s3 = S3Manager()
        
        df = pd.DataFrame(csv_data)
        # CSVをメモリバッファに出力
        from io import BytesIO
        csv_buffer = BytesIO()
        df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        
        # S3へアップロード
        csv_key = f"{images_dir}/prompt.csv"
        s3.upload_file(csv_buffer.getvalue(), csv_key, content_type="text/csv")

    # 最後にDBスキャンして反映
    # StateManagerをここでインスタンス化して即実行（変数削減）
    StateManager().scan_and_sync()


def _setup_output_dirs(keyword: str) -> str:
    """
    Prepare output S3 key prefix.
    """
    timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
    # Windowsファイル名禁止文字などを置換し、長さを制限する
    safe_keyword = "".join(
        c for c in keyword if c.isalnum() or c in (' ', '_', '-')
    ).strip().replace(" ", "_")
    safe_keyword = safe_keyword[:50]
    
    # S3 prefix: output/timestamp_keyword/generated_images/
    # 末尾にスラッシュをつけるかどうかは使い勝手次第だが、joinするときに便利なのでつけないでおく
    # (os.path.joinはWindowsだとバックスラッシュになるので注意、ここでは文字列操作でやる)
    base_prefix = f"output/{timestamp}_{safe_keyword}"
    images_prefix = f"{base_prefix}/generated_images"

    return images_prefix


def _generate_images_loop(
        generator, ideas, images_dir: str, style, size, keyword
): # pylint: disable=too-many-arguments, too-many-positional-arguments
    """
    Loop to generate images based on ideas.
    """
    csv_data = []
    progress_bar = st.progress(0)

    for i, idea in enumerate(ideas):
        try:
            draw_prompt = generator.generate_drawing_prompt(idea, style=style)
            filename = f"img_{i:03d}.png"
            # S3 Key構築 (Forward Slash)
            output_path = f"{images_dir}/{filename}"

            generator.generate_image(
                prompt=draw_prompt,
                output_path=output_path,
                size=size
            )
            csv_data.append({
                "filename": filename,
                "prompt": draw_prompt,
                "keyword": keyword
            })

        except Exception: # pylint: disable=broad-exception-caught
            st.error(f"Error generating image {i}")

        progress_bar.progress((i + 1) / len(ideas))
    
    return csv_data


def process_registration(keyword, status_filter=STATUS_UNPROCESSED):
    """
    Process selected images for registration.
    """
    selected = st.session_state.get(f'selection_{status_filter}', [])
    if not selected:
        st.warning("No images selected.")
        return

    submit_mgr = SubmissionManager(API_KEY)
    state_mgr = StateManager()

    target_images = []
    for path in selected:
        rel_path = os.path.relpath(path, os.getcwd()).replace("\\", "/")
        if rel_path in state_mgr.db:
            data = state_mgr.db[rel_path].copy()
            data['path'] = rel_path
            target_images.append(data)

    with st.spinner(f"Upscaling and Registering {len(target_images)} images..."):
        zip_data = submit_mgr.process_submission(target_images, keyword=keyword)

    if zip_data:
        st.session_state['latest_zip_data'] = zip_data
        st.session_state['latest_zip_name'] = (
            f"submission_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        )
        st.success("Registration Complete! Download ready.")
    else:
        st.error("Submission failed or no data.")


def process_exclusion(status_filter=STATUS_UNPROCESSED):
    """
    Process selected images to exclude them.
    """
    selected = st.session_state.get(f'selection_{status_filter}', [])
    if not selected:
        st.warning("No images selected.")
        return

    state_mgr = StateManager()
    state_mgr.update_status(selected, STATUS_EXCLUDED)
    st.success(f"Excluded {len(selected)} images.")


def process_revert(status_filter):
    """
    Revert selected images to unprocessed status.
    """
    selected = st.session_state.get(f'selection_{status_filter}', [])
    if not selected:
        st.warning("No images selected.")
        return

    state_mgr = StateManager()
    state_mgr.update_status(selected, STATUS_UNPROCESSED)
    st.success(f"Reverted {len(selected)} images to Unprocessed.")


if __name__ == "__main__":
    main()
