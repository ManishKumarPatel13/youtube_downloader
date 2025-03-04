import streamlit as st
import os
import sys
import time
import yt_dlp
from datetime import datetime
import tempfile
import pandas as pd

# Import core functionality from downloader.py
# We'll keep the core functions but adapt them to work with Streamlit
from downloader import get_available_formats

# Initialize session state for tracking file decisions
if 'file_decision_made' not in st.session_state:
    st.session_state.file_decision_made = False
if 'file_decision' not in st.session_state:
    st.session_state.file_decision = None
if 'new_filename' not in st.session_state:
    st.session_state.new_filename = None

# Set page config
st.set_page_config(
    page_title="YouTube Downloader",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Platform-independent default save path
DEFAULT_SAVE_PATH = os.path.join(os.path.expanduser("~"), "Downloads")

def main():
    """Main Streamlit app function"""
    st.title("📺 YouTube Downloader")
    st.sidebar.image("https://www.gstatic.com/youtube/img/branding/youtubelogo/svg/youtubelogo.svg", width=200)
    
    # Sidebar for settings
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # Output directory
        save_dir = st.text_input("Download Location", DEFAULT_SAVE_PATH)
        
        # Create directory if it doesn't exist
        if not os.path.exists(save_dir):
            if st.button("Create Directory"):
                try:
                    os.makedirs(save_dir)
                    st.success(f"Created directory: {save_dir}")
                except Exception as e:
                    st.error(f"Could not create directory: {str(e)}")
        
        # Force re-download option
        force_download = st.checkbox("Force Re-download", help="Download even if file exists")
        
        # Show advanced options
        with st.expander("Advanced Options"):
            concurrent_fragments = st.slider("Concurrent Fragments", 1, 10, 5)
            audio_quality = st.selectbox("Audio Quality", ["192", "256", "320"])
    
    # Main content area
    url = st.text_input("🔗 Enter YouTube URL", help="Enter a YouTube URL to download")
    
    # URL validation
    if url and ("youtube.com" not in url and "youtu.be" not in url):
        st.warning("Please enter a valid YouTube URL")
    
    if url and ("youtube.com" in url or "youtu.be" in url):
        # Try to get formats
        with st.spinner("Fetching video information..."):
            try:
                formats_info = get_available_formats(url)
                if not formats_info:
                    st.error("Could not retrieve video information")
                    return
                
                # Display video info
                video_title = formats_info['title']
                st.subheader(f"📽️ {video_title}")
                
                # Create formats dataframe for better display
                formats = formats_info['formats']
                video_formats = [f for f in formats if f['has_video']]
                audio_formats = [f for f in formats if not f['has_video'] and f['has_audio']]
                
                # Prepare data for the table
                format_data = []
                
                # Add video formats - ensure all values are strings to avoid type issues
                for i, fmt in enumerate(video_formats):
                    media_type = "Video"
                    if fmt['has_audio']:
                        media_type += "+Audio"
                    format_data.append({
                        "ID": str(i),
                        "Format ID": str(fmt['format_id']),
                        "Resolution": str(fmt['resolution']),
                        "FPS": str(fmt['fps']),  # Convert all FPS values to strings
                        "Size": str(fmt['filesize']),
                        "Type": str(fmt['ext']),
                        "Content": media_type
                    })
                
                # Add audio formats
                for i, fmt in enumerate(audio_formats):
                    idx = i + len(video_formats)
                    format_data.append({
                        "ID": str(idx),
                        "Format ID": str(fmt['format_id']),
                        "Resolution": "audio only",
                        "FPS": "-",  # Consistent string value
                        "Size": str(fmt['filesize']),
                        "Type": str(fmt['ext']),
                        "Content": "Audio only"
                    })
                
                # Add best options
                format_data.append({
                    "ID": str(len(formats)),
                    "Format ID": "best",
                    "Resolution": "best",
                    "FPS": "auto",  # Already a string
                    "Size": "auto",  # Already a string
                    "Type": "mp4",
                    "Content": "Best quality"
                })
                
                format_data.append({
                    "ID": str(len(formats) + 1),
                    "Format ID": "bestaudio",
                    "Resolution": "audio",
                    "FPS": "auto",  # Already a string
                    "Size": "auto",  # Already a string
                    "Type": "mp3",
                    "Content": "Best audio"
                })
                
                # Display formats as a table - explicitly specify dtypes
                st.subheader("📋 Available formats:")
                
                # Create dataframe with all string dtypes to avoid conversion issues
                df = pd.DataFrame(format_data).astype(str)
                st.dataframe(df, use_container_width=True)
                
                # Format selection
                format_options = [
                    {"label": f"ID {row['ID']}: {row['Resolution']} - {row['Content']} ({row['Type']})", "value": i} 
                    for i, row in enumerate(format_data)
                ]
                format_dict = {i: row["Format ID"] for i, row in enumerate(format_data)}
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    selected_format_idx = st.selectbox(
                        "Select format to download:",
                        options=range(len(format_options)),
                        format_func=lambda x: format_options[x]["label"],
                        index=len(formats)  # Default to best quality
                    )
                
                # Get actual format_id
                if selected_format_idx == len(formats):
                    format_id = "best[ext=mp4]"
                elif selected_format_idx == len(formats) + 1:
                    format_id = "bestaudio[ext=mp3]/bestaudio"
                else:
                    if selected_format_idx < len(video_formats):
                        format_id = video_formats[selected_format_idx]['format_id']
                    else:
                        audio_idx = selected_format_idx - len(video_formats)
                        format_id = audio_formats[audio_idx]['format_id']
                
                with col2:
                    st.text("")
                    st.text("")
                    if st.button("⬇️ Download", type="primary", use_container_width=True):
                        download_with_streamlit(url, save_dir, format_id, force_download, concurrent_fragments, audio_quality)
                
            except Exception as e:
                st.error(f"Error processing URL: {str(e)}")

def download_with_streamlit(url, output_path, format_id, force=False, concurrent_fragments=5, audio_quality="192"):
    """Download video using yt-dlp with Streamlit UI"""
    try:
        # Get video info first
        with st.spinner("Preparing download..."):
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                video_title = info.get('title', 'video').replace('/', '_').replace('\\', '_')
        
        # Check if file exists
        potential_filename = os.path.join(output_path, f"{video_title}.mp4")
        potential_filename_audio = os.path.join(output_path, f"{video_title}.mp3")
        file_exists = os.path.exists(potential_filename) or os.path.exists(potential_filename_audio)
        
        # Handle file existence with proper decision flow
        if file_exists and not force and not st.session_state.file_decision_made:
            st.warning(f"⚠️ File already exists")
            
            # Set up columns for buttons
            col1, col2, col3 = st.columns(3)
            
            # Define button callbacks to set session state
            def on_redownload():
                st.session_state.file_decision_made = True
                st.session_state.file_decision = "redownload"
                
            def on_new_name():
                st.session_state.file_decision_made = True
                st.session_state.file_decision = "new_name"
                st.session_state.new_filename = f"{video_title}_{int(time.time())}"
                
            def on_skip():
                st.session_state.file_decision_made = True
                st.session_state.file_decision = "skip"
            
            # Display buttons with callbacks
            with col1:
                st.button("Re-download", on_click=on_redownload, key="btn_redownload")
            with col2:
                st.button("Download with new name", on_click=on_new_name, key="btn_newname")
            with col3:
                st.button("Skip", on_click=on_skip, key="btn_skip")
            
            # Wait for user decision before proceeding
            st.stop()  # This stops execution until next rerun with updated session state
            
        # Process the user's decision
        if st.session_state.file_decision_made:
            if st.session_state.file_decision == "redownload":
                force = True
                st.info("Re-downloading the file...")
            elif st.session_state.file_decision == "new_name":
                video_title = st.session_state.new_filename
                st.info(f"Downloading with new name: {video_title}")
            elif st.session_state.file_decision == "skip":
                st.info("Download skipped.")
                # Reset decision state for future downloads
                st.session_state.file_decision_made = False
                st.session_state.file_decision = None
                st.session_state.new_filename = None
                return
            
            # Reset decision state for future downloads
            st.session_state.file_decision_made = False
            st.session_state.file_decision = None
            st.session_state.new_filename = None
        
        # Configure yt-dlp options
        ydl_opts = {
            'format': format_id,
            'outtmpl': os.path.join(output_path, f"{video_title}.%(ext)s"),
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,
            'overwrites': force,
            'concurrent_fragment_downloads': concurrent_fragments,
        }
        
        # Add MP3 conversion if requested
        if 'bestaudio' in format_id and 'mp3' in format_id:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': audio_quality,
            }]
        
        # Create a container for download progress information
        progress_container = st.container()
        with progress_container:
            progress_columns = st.columns([3, 1])
            with progress_columns[0]:
                progress_bar = st.progress(0)
            with progress_columns[1]:
                percent_text = st.empty()
            
            status_text = st.empty()
            file_size_text = st.empty()
            eta_text = st.empty()
        
        # Custom progress hook for Streamlit with better information
        def streamlit_progress_hook(d):
            if d['status'] == 'downloading':
                # Calculate progress percentage
                downloaded_bytes = d.get('downloaded_bytes', 0)
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                
                if total_bytes > 0:
                    percentage = downloaded_bytes / total_bytes
                    # Update progress bar
                    progress_bar.progress(min(percentage, 1.0))
                    # Update percentage text
                    percent_text.markdown(f"<h3 style='text-align: center; margin: 0;'>{percentage:.1%}</h3>", unsafe_allow_html=True)
                
                # Format file sizes
                downloaded_mb = downloaded_bytes / (1024 * 1024)
                total_mb = total_bytes / (1024 * 1024) if total_bytes else 0
                
                # Update status and information
                speed = d.get('speed', 0)
                speed_str = f"{speed / (1024 * 1024):.2f} MB/s" if speed else "N/A"
                eta = d.get('eta', 0)
                eta_str = f"{eta // 60}m {eta % 60}s" if eta else "N/A"
                
                status_text.markdown(f"⏬ **Downloading at {speed_str}**")
                if total_bytes:
                    file_size_text.text(f"📦 {downloaded_mb:.1f} MB of {total_mb:.1f} MB ({percentage:.1%})")
                else:
                    file_size_text.text(f"📦 {downloaded_mb:.1f} MB downloaded (unknown total)")
                eta_text.text(f"⏱️ Estimated time remaining: {eta_str}")
                
            elif d['status'] == 'finished':
                progress_bar.progress(1.0)
                percent_text.markdown("<h3 style='text-align: center; margin: 0;'>100%</h3>", unsafe_allow_html=True)
                status_text.markdown("🔄 **Download complete, now processing...**")
                file_size_text.empty()
                eta_text.empty()
        
        # Add our custom progress hook
        ydl_opts['progress_hooks'] = [streamlit_progress_hook]
        
        # Get estimated file size before download (when possible)
        with st.spinner("Estimating file size..."):
            try:
                with yt_dlp.YoutubeDL({'quiet': True, 'format': format_id}) as ydl:
                    info = ydl.extract_info(url, download=False, process=True)
                    
                    # Try to get selected format info
                    selected_format = None
                    for fmt in info.get('formats', []):
                        if fmt.get('format_id') == format_id:
                            selected_format = fmt
                            break
                    
                    if selected_format and selected_format.get('filesize'):
                        filesize_mb = selected_format.get('filesize') / (1024 * 1024)
                        file_size_text.text(f"📦 Estimated file size: {filesize_mb:.1f} MB")
            except:
                # If estimation fails, just continue with download
                pass
        
        # Download the video
        with st.spinner("Starting download..."):
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        
        # Determine the expected file path
        if 'bestaudio' in format_id and 'mp3' in format_id:
            file_path = os.path.join(output_path, f"{video_title}.mp3")
            file_type = "Audio"
        else:
            file_path = os.path.join(output_path, f"{video_title}.mp4")
            file_type = "Video"
        
        # Show success message
        if os.path.exists(file_path):
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            st.success(f"✅ Download completed! {file_type} saved to {file_path} ({file_size_mb:.1f} MB)")
            
            # Add play button for audio files
            if file_type == "Audio" and os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    audio_bytes = f.read()
                st.audio(audio_bytes, format="audio/mp3")
        else:
            st.warning(f"⚠️ Download possibly completed, but file not found at expected location: {file_path}")
    
    except Exception as e:
        st.error(f"❌ Error during download: {str(e)}")
        st.exception(e)  # Show the full exception details for debugging

if __name__ == "__main__":
    main()
