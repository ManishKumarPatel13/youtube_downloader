import os
import sys
import argparse
import yt_dlp
from datetime import datetime
import time

# Platform-independent save path
DEFAULT_SAVE_PATH = os.path.join(os.path.expanduser("~"), "Downloads")

def setup_argparse():
    """Setup command line argument parsing"""
    parser = argparse.ArgumentParser(description='YouTube Video Downloader using yt-dlp')
    parser.add_argument('urls', nargs='*', help='YouTube URL(s) to download')
    parser.add_argument('-o', '--output', help='Output directory', default=DEFAULT_SAVE_PATH)
    parser.add_argument('-f', '--format', help='Specific format to download')
    parser.add_argument('-b', '--best', action='store_true', help='Download best quality automatically')
    parser.add_argument('--force', action='store_true', help='Force re-download even if file exists')
    return parser.parse_args()

def get_available_formats(url):
    """Get a list of available formats/resolutions for the video"""
    try:
        print(f"\n📋 Fetching available formats from: {url}")
        
        # Configure yt-dlp options for format listing
        ydl_opts = {
            'quiet': True, # Suppress output for this step only to avoid clutter in the console
        }
        
        # Extract formats information
        formats = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'Unknown Title')
            duration = info.get('duration')
            duration_str = str(datetime.fromtimestamp(duration).strftime("%M:%S")) if duration else "Unknown"
            
            print(f"\n📺 Video: {video_title}")
            print(f"⏱️ Duration: {duration_str}")
            print(f"👁️ Views: {info.get('view_count', 'Unknown')}")
            
            # Get all available formats
            for f in info.get('formats', []):
                # Extract useful information
                format_id = f.get('format_id', 'N/A')
                ext = f.get('ext', 'N/A')
                resolution = f.get('resolution', 'N/A')
                fps = f.get('fps', 'N/A')
                filesize = f.get('filesize', None)
                filesize_str = f"{filesize/(1024*1024):.1f}MB" if filesize else "Unknown"
                vcodec = f.get('vcodec', 'N/A')
                acodec = f.get('acodec', 'N/A')
                
                # Skip formats without video (unless audio-only)
                if vcodec == 'none' and not (acodec != 'none' and ext == 'mp3'):
                    continue
                
                # Create format info dictionary
                format_info = {
                    'format_id': format_id,
                    'ext': ext,
                    'resolution': resolution,
                    'fps': fps,
                    'filesize': filesize_str,
                    'has_video': vcodec != 'none',
                    'has_audio': acodec != 'none',
                }
                
                formats.append(format_info)
            
        return {'title': video_title, 'formats': formats}
    
    except Exception as e:
        print(f"❌ Error getting formats: {str(e)}")
        return None

def display_formats_and_select(formats_info):
    """Display available formats and let user select one"""
    if not formats_info:
        return None
    
    formats = formats_info['formats']
    print("\n📋 Available formats:")
    print("-" * 80)
    print(f"{'ID':<5} {'Format ID':<10} {'Resolution':<12} {'FPS':<6} {'Size':<10} {'Type':<6} {'Audio/Video':<12}")
    print("-" * 80)
    
    video_formats = []
    audio_formats = []
    
    for fmt in formats:
        if fmt['has_video']:
            video_formats.append(fmt)
        elif fmt['has_audio'] and not fmt['has_video']:
            audio_formats.append(fmt)
    
    # Display video formats first
    for i, fmt in enumerate(video_formats):
        media_type = "Video"
        if fmt['has_audio']:
            media_type += "+Audio"
        print(f"{i:<5} {fmt['format_id']:<10} {fmt['resolution']:<12} {fmt['fps']:<6} {fmt['filesize']:<10} {fmt['ext']:<6} {media_type:<12}")
    
    # Display audio formats
    offset = len(video_formats)
    for i, fmt in enumerate(audio_formats):
        idx = i + offset
        print(f"{idx:<5} {fmt['format_id']:<10} {'audio only':<12} {'-':<6} {fmt['filesize']:<10} {fmt['ext']:<6} {'Audio only':<12}")
    
    # Add the best options
    best_idx = len(formats)
    print(f"{best_idx:<5} {'best':<10} {'best':<12} {'auto':<6} {'auto':<10} {'mp4':<6} {'Best quality':<12}")
    
    best_audio_idx = best_idx + 1
    print(f"{best_audio_idx:<5} {'bestaudio':<10} {'audio':<12} {'auto':<6} {'auto':<10} {'mp3':<6} {'Best audio':<12}")
    
    # Get user selection
    try:
        selection = input("\n👉 Select format number (or press Enter for best quality): ")
        
        if selection.strip() == "":
            return "best[ext=mp4]"
        
        idx = int(selection)
        if 0 <= idx < len(video_formats):
            selected_format = video_formats[idx]['format_id']
            print(f"Selected format ID: {selected_format}")
            return selected_format
        elif len(video_formats) <= idx < len(formats):
            audio_idx = idx - len(video_formats)
            selected_format = audio_formats[audio_idx]['format_id']
            print(f"Selected format ID: {selected_format}")
            return selected_format
        elif idx == best_idx:
            return "best[ext=mp4]"
        elif idx == best_audio_idx:
            return "bestaudio[ext=mp3]/bestaudio"
        else:
            print("⚠️ Invalid selection, using best quality")
            return "best[ext=mp4]"
    
    except ValueError:
        print("⚠️ Invalid input, using best quality")
        return "best[ext=mp4]"

def download_with_yt_dlp(url, output_path=DEFAULT_SAVE_PATH, format_id=None, auto_best=False, force=False):
    """Download video using yt-dlp with selected format"""
    try:
        # If auto_best is True, skip format selection
        if auto_best:
            format_id = "best[ext=mp4]"
        # First, get available formats if no format specified
        elif not format_id:
            formats_info = get_available_formats(url)
            if not formats_info:
                print("❌ Could not retrieve format information")
                return False
            
            # Let user select format
            format_id = display_formats_and_select(formats_info)
        
        print(f"\n⏬ Downloading with format ID: {format_id}")
        
        # Extract video info first to get the title for filename construction
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'video').replace('/', '_').replace('\\', '_')
        
        # Determine filename template with timestamp if needed
        timestamp = int(time.time())
        filename_template = '%(title)s.%(ext)s'
        
        # Configure yt-dlp options with explicit format
        ydl_opts = {
            'format': format_id,
            'format_sort': ['res', 'ext'],
            'outtmpl': os.path.join(output_path, filename_template),
            'progress_hooks': [yt_dlp_progress_hook],
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,  # Don't download playlists
        }
        
        # Force re-download if requested
        if force:
            ydl_opts['overwrites'] = True
        else:
            ydl_opts['skip_download'] = False
            ydl_opts['continuedl'] = True
            # Handle duplicate filenames with timestamp
            ydl_opts['outtmpl_na_placeholder'] = ''
            ydl_opts['concurrent_fragment_downloads'] = 5  # Speed up downloads
        
        # Add MP3 conversion if requested
        if format_id and ('bestaudio' in format_id and 'mp3' in format_id):
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        
        print("Starting download with these options:")
        print(f"  Format ID: {format_id}")
        print(f"  Output: {output_path}")
        print(f"  Force re-download: {force}")
        
        # Check if file might already exist
        potential_filename = os.path.join(output_path, f"{video_title}.mp4")
        if os.path.exists(potential_filename) and not force:
            print(f"\n⚠️ File already exists: {potential_filename}")
            response = input("Do you want to re-download? (y/n, or 'r' to rename): ").lower()
            
            if response == 'y':
                ydl_opts['overwrites'] = True
            elif response == 'r':
                # Add timestamp to filename to make it unique
                ydl_opts['outtmpl'] = os.path.join(output_path, f"%(title)s_{timestamp}.%(ext)s")
                print(f"Will download with new filename including timestamp: {timestamp}")
            else:
                print("Download skipped.")
                return True
        
        # Download the video with specific format ID
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Show what was actually downloaded
            print(f"\nDownloaded format information:")
            print(f"  Title: {info.get('title', 'Unknown')}")
            print(f"  Format ID: {info.get('format_id', 'Unknown')}")
            print(f"  Resolution: {info.get('resolution', 'Unknown')}")
            print(f"  Extension: {info.get('ext', 'Unknown')}")
            
            # Get the actual filename that was downloaded
            if '_filename' in info:
                print(f"\n📄 File saved as: {info['_filename']}")
            
        print(f"\n✅ '{video_title}' downloaded successfully to {output_path}!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def yt_dlp_progress_hook(d):
    """Progress hook for yt-dlp"""
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', 'N/A')
        speed = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        sys.stdout.write(f"\r⏬ Downloading... {percent} at {speed}, ETA: {eta}")
        sys.stdout.flush()
    elif d['status'] == 'finished':
        print("\n🔄 Download complete, now processing...")

def main():
    """Main function to handle command line arguments and start download"""
    args = setup_argparse()
    output_dir = args.output
    
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"📁 Created output directory: {output_dir}")
        except Exception as e:
            print(f"❌ Error creating directory {output_dir}: {str(e)}")
            output_dir = DEFAULT_SAVE_PATH
            print(f"📁 Using default directory: {output_dir}")
    
    print(f"📂 Files will be saved to: {output_dir}")
    
    # Get URLs from command line or prompt user
    urls = args.urls
    if not urls:
        url = input("🔗 Enter YouTube URL: ")
        urls = [url] if url else []
    
    if not urls:
        print("❌ No URLs provided. Exiting.")
        return
    
    # Process each URL
    success_count = 0
    for url in urls:
        print(f"\n🎬 Processing: {url}")
        if download_with_yt_dlp(url, output_dir, args.format, args.best, args.force):
            success_count += 1
    
    if len(urls) > 1:
        print(f"\n✅ Downloaded {success_count} of {len(urls)} videos")

if __name__ == "__main__":
    main()
