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


def render_gallery_content(status_filter):
    """
    Render gallery content based on the selected status filter.
    """
    state_mgr = StateManager()
    display_images = state_mgr.get_images_by_status(status_filter)

    if not display_images:
        st.info(f"No images found in {status_filter}.")
        # 画像がない場合でも再度スキャンできるボタンがあると便利
        if st.sidebar.button("Forced Rescan"):
            state_mgr.scan_and_sync()
            st.rerun()
        return

    st.write(f"Found {len(display_images)} images.")

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
            st.rerun()

        if st.sidebar.button("🗑️ Exclude Selected", key=f"btn_exc{key_suffix}"):
            process_exclusion(status_filter)
            st.rerun()

    else:
        # Registered / Excluded
        if st.sidebar.button("↩️ Revert to Unprocessed", key=f"btn_rev{key_suffix}"):
            process_revert(status_filter)
            st.rerun()

    # グリッド表示
    selected_paths = []
    cols = st.columns(4)

    for idx, img in enumerate(display_images):
        file_path = img['path']
        with cols[idx % 4]:
            try:
                # use_container_width=True is better for new streamlit
                st.image(file_path, width="stretch")

                # 詳細ボタン
                if st.button("🔍 Details", key=f"btn_det_{status_filter}_{idx}"):
                    view_image_details(
                        file_path,
                        img.get('prompt', ''),
                        img.get('tags', ''),
                        img.get('keyword', '')
                    )

                unique_key = f"chk_{status_filter}_{file_path}"
                default_val = status_filter == STATUS_UNPROCESSED

                is_selected = st.checkbox("Select", key=unique_key, value=default_val)
                if is_selected:
                    selected_paths.append(file_path)

            except Exception: # pylint: disable=broad-exception-caught
                st.error(f"Error loading {file_path}")

    st.session_state[f'selection_{status_filter}'] = selected_paths


def run_generation(
    keyword, tags, n_ideas, model, style, size
): # pylint: disable=too-many-arguments, too-many-positional-arguments
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
    if csv_data:
        for item in csv_data:
            item['tags'] = tags

        df = pd.DataFrame(csv_data)
        df.to_csv(
            os.path.join(images_dir, "prompt.csv"),
            index=False,
            encoding='utf-8-sig'
        )

    # 最後にDBスキャンして反映
    # StateManagerをここでインスタンス化して即実行（変数削減）
    StateManager().scan_and_sync()


def _setup_output_dirs(keyword: str) -> str:
    """
    Prepare output directories and return the images directory path.
    """
    timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
    # Windowsファイル名禁止文字などを置換し、長さを制限する
    safe_keyword = "".join(
        c for c in keyword if c.isalnum() or c in (' ', '_', '-')
    ).strip().replace(" ", "_")
    safe_keyword = safe_keyword[:50]
    base_output_dir = os.path.join("output", f"{timestamp}_{safe_keyword}")
    images_dir = os.path.join(base_output_dir, "generated_images")
    os.makedirs(images_dir, exist_ok=True)
    return images_dir


def _generate_images_loop(
        generator, ideas, images_dir, style, size, keyword
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
            output_path = os.path.join(images_dir, filename)

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

        except Exception as e: # pylint: disable=broad-exception-caught
            st.error(f"Error generating image {i}: {e}")

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
        submit_mgr.process_submission(target_images, keyword=keyword)

    st.success("Registration Complete!")


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
