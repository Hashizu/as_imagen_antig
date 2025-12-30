"""
Streamlit application for Adobe Stock Image Generator.
Handles UI, image generation, gallery viewing, and state management.
"""
import sys
import os
from datetime import datetime
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
from src.job_manager import GenerationJob

# セットアップ
def configure_environment():
    """
    Configure environment variables for Local (.env) and Remote (Streamlit Cloud).
    Prioritizes Streamlit Secrets if available, ensuring os.environ is consistent.
    """
    # 1. Load local .env file (if exists)
    load_dotenv()

    # 2. Overlay Streamlit Secrets (for Cloud Deployment)
    try:
        if hasattr(st, "secrets"):
            # Generic copy for strings
            for key, value in st.secrets.items():
                if isinstance(value, str):
                    os.environ[key] = value
                
    except Exception: # pylint: disable=broad-exception-caught
        pass

configure_environment()

API_KEY = os.getenv("OPENAI_API_KEY")

if "keyword_input" not in st.session_state:
    st.session_state.keyword_input = ""
if "tags_input" not in st.session_state:
    st.session_state.tags_input = ""

def check_password():
    """Returns `True` if the user had the correct password."""
    
    password = os.getenv("APP_PASSWORD")
    if not password:
        return True

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = None

    if not st.session_state["password_correct"]:
        # Show input and button side by side
        col1, col2 = st.columns([3, 1], vertical_alignment="bottom")
        with col1:
            st.text_input(
                "Please enter the password", 
                type="password", 
                on_change=password_entered, 
                key="password"
            )
        with col2:
            if st.button("Login", type="primary"):
                password_entered()
                st.rerun()

        if st.session_state["password_correct"] is False:
            st.error("😕 Password incorrect")
        
        return False

    # Password correct.
    return True

def get_remote_ip():
    """Get remote IP address from headers"""
    try:
        # Streamlit 1.38+ supports st.context.headers
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            headers = st.context.headers
            if headers:
                return headers.get("X-Forwarded-For", "127.0.0.1").split(",")[0]
    except Exception: # pylint: disable=broad-exception-caught
        pass
    return "127.0.0.1"

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
    
    # 認証チェック
    if not check_password():
        st.stop()

    # IPアドレス取得と保持
    if 'user_ip' not in st.session_state:
        st.session_state['user_ip'] = get_remote_ip()

    st.title("🎨 AS画像屋さん")

    if not API_KEY:
        st.error("🔑 OPENAI_API_KEY not found. Please set it in .env (Local) or Streamlit Secrets (Cloud).")
        return

    # サイドバー: バックグラウンドジョブのステータス表示
    _render_sidebar_status()

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


def _render_sidebar_status():
    """
    Render background job status in the sidebar.
    """
    if 'active_job' in st.session_state:
        job = st.session_state['active_job']
        status = job.status
        
        # Compact container
        with st.sidebar.container():
            st.markdown("---")
            
            # Row 1: Status Message & Action
            c1, c2 = st.columns([4, 1])
            with c1:
                # Use bold text for visibility without box
                msg = status.get('message', 'Processing...')
                # Truncate if too long
                if len(msg) > 25:
                    msg = msg[:24] + "..."
                st.markdown(f"**⚙️ {msg}**")
            with c2:
                if status['is_running']:
                    if st.button("⏹", key="stop_job", help="Stop"):
                        job.cancel()
                        st.rerun()
                elif status['is_complete'] or status.get('error'):
                    if st.button("x", key="clear_job", help="Clear"):
                        del st.session_state['active_job']
                        st.rerun()

            # Row 2: Progress (Thin)
            st.progress(status['progress'])

            if status.get('error'):
                st.caption(f"Error: {status['error']}")
                
            st.markdown("---")


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

    # 実行ボタン (すでにジョブが走っている場合は無効化)
    is_running = False
    if 'active_job' in st.session_state:
        if st.session_state['active_job'].status['is_running']:
            is_running = True

    if st.button("Generate Images", type="primary", disabled=is_running):
        if not keyword:
            st.warning("Please enter a keyword.")
        else:
            # Start background job
            job = GenerationJob(
                API_KEY, keyword, tags, n_images, model, style, size,
                creator_ip=st.session_state.get('user_ip', '127.0.0.1')
            )
            job.start()
            st.session_state['active_job'] = job
            st.toast("Generation started in background!", icon="🚀")
            st.rerun()


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

    if status_filter == STATUS_REGISTERED:
        _render_registered_gallery(all_images)
    else:
        _render_unprocessed_or_excluded_gallery(all_images, status_filter)


def _render_registered_gallery(all_images):
    """
    Render gallery for Registered images with grouping by submission.
    """
    # Group by submission_id
    grouped = {}
    legacy_key = "Legacy (No Batch Info)"
    
    for img in all_images:
        sub_id = img.get("submission_id")
        if not sub_id:
            sub_id = legacy_key
        
        if sub_id not in grouped:
            grouped[sub_id] = []
        grouped[sub_id].append(img)
    
    # Sort groups: Newest submission first
    sorted_keys = sorted([k for k in grouped.keys() if k != legacy_key], reverse=True)
    if legacy_key in grouped:
        sorted_keys.append(legacy_key)
        
    s3 = S3Manager()

    for sub_id in sorted_keys:
        images = grouped[sub_id]
        
        # Header
        timestamp_str = "Unknown Date"
        if sub_id != legacy_key:
            try:
                # simple parse
                parts = sub_id.split('/')[-1].split('_')
                timestamp_str = parts[0]
            except Exception: # pylint: disable=broad-exception-caught
                timestamp_str = sub_id

        with st.expander(f"📦 Batch: {timestamp_str} ({len(images)} images)", expanded=True):
            # Download ZIP Link (Presigned URL)
            if sub_id != legacy_key:
                zip_key = f"{sub_id}/submission.zip"
                
                # Presigned URLの発行 (有効期限 1時間)
                url = s3.get_presigned_url(zip_key, expiration=3600)
                
                if url:
                    # HTMLリンクとして表示 (ボタン風のスタイル)
                    st.markdown(
                        f"""
                        <a href="{url}" download style="text-decoration:none;">
                            <button style="
                                display: inline-flex;
                                -webkit-box-align: center;
                                align-items: center;
                                -webkit-box-pack: center;
                                justify-content: center;
                                font-weight: 400;
                                padding: 0.25rem 0.75rem;
                                border-radius: 0.5rem;
                                min-height: 38.4px;
                                margin: 0px;
                                line-height: 1.6;
                                color: inherit;
                                width: auto;
                                user-select: none;
                                background-color: rgb(255, 255, 255);
                                border: 1px solid rgba(49, 51, 63, 0.2);
                            ">
                                📥 Download ZIP (Direct)
                            </button>
                        </a>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.caption("ZIP link unavailable.")

            # Grid Display
            cols = st.columns(4)
            for idx, img in enumerate(images):
                file_path = img['path']
                with cols[idx % 4]:
                    try:
                        img_bytes = load_s3_image(file_path)
                        st.image(img_bytes, width="stretch")

                        # 詳細ボタン
                        if st.button("🔍 Details", key=f"btn_det_reg_{file_path}"):
                            view_image_details(
                                img_bytes,
                                img.get('prompt', ''),
                                img.get('tags', ''),
                                img.get('keyword', '')
                            )

                        unique_key = f"chk_reg_{file_path}"
                        if st.checkbox("Select", key=unique_key):
                            if 'selection_REGISTERED' not in st.session_state:
                                st.session_state['selection_REGISTERED'] = []
                            if file_path not in st.session_state['selection_REGISTERED']:
                                st.session_state['selection_REGISTERED'].append(file_path)

                    except Exception as e: # pylint: disable=broad-exception-caught
                        st.error("Error")


def _render_unprocessed_or_excluded_gallery(all_images, status_filter):
    """
    Render gallery for Unprocessed or Excluded images (Standard Grid).
    """
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
        # Excluded (Registered is handled above)
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
