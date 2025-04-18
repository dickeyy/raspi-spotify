#!/usr/bin/python3
import sys
import os
import time
import requests
import logging
from PIL import Image, ImageDraw, ImageFont
import traceback
from io import BytesIO
import hashlib
import websocket
import json
import threading

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Add the e-Paper library paths from the home directory
home_dir = os.path.expanduser('~')  # Get home directory
e_paper_lib = os.path.join(home_dir, 'e-Paper/RaspberryPi_JetsonNano/python/lib')
e_paper_pic = os.path.join(home_dir, 'e-Paper/RaspberryPi_JetsonNano/python/pic')

logging.info(f"Checking for e-Paper library at: {e_paper_lib}")

if os.path.exists(e_paper_lib):
    sys.path.append(e_paper_lib)
    picdir = e_paper_pic
    logging.info(f"e-Paper library found at: {e_paper_lib}")
else:
    # Fallback to the original approach
    logging.warning(f"e-Paper library not found at: {e_paper_lib}")
    logging.warning("Trying original paths...")
    
    picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
    libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
    
    if os.path.exists(libdir):
        sys.path.append(libdir)
        logging.info(f"Using library path: {libdir}")
    else:
        logging.error("Could not find e-Paper library path")
        sys.exit("Error: Could not find e-Paper library. Please install it or update paths.")

# Try to import the Waveshare display driver - using the correct V3 model per example
try:
    from waveshare_epd import epd2in13_V3
    logging.info("Successfully imported waveshare_epd module")
except ImportError as e:
    logging.error(f"Failed to import waveshare_epd: {e}")
    logging.error(f"Current sys.path: {sys.path}")
    sys.exit("Error: waveshare_epd module not found. Please install it or update paths.")

# Global variables to track current display state
previous_data = None
last_full_refresh_time = 0
BASE_IMAGE = None
epd = None
websocket_app = None
websocket_thread = None
reconnect_attempt = 0
MAX_RECONNECT_ATTEMPTS = 10
RECONNECT_DELAY = 5  # seconds

# Set up a cache directory for album art
cache_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cache')
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)
    logging.info(f"Created cache directory at {cache_dir}")
else:
    # Clear the cache to ensure we're not using old cached images
    logging.info(f"Clearing cache directory at {cache_dir}")
    for file in os.listdir(cache_dir):
        file_path = os.path.join(cache_dir, file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            logging.error(f"Error deleting {file_path}: {e}")

# Album art cache dictionary (in-memory cache)
album_art_cache = {}

def add_rounded_corners(image, radius):
    """Add rounded corners to an image using a mask"""
    # Create a mask with rounded corners
    mask = Image.new('L', image.size, 0)
    draw = ImageDraw.Draw(mask)
    
    # Draw a rectangle with rounded corners on the mask
    draw.rounded_rectangle([(0, 0), (image.width, image.height)], radius=radius, fill=255)
    
    # Create a new image with a white background
    result = Image.new('L', image.size, 255)
    
    # Paste the original image using the mask
    result.paste(image, (0, 0), mask)
    
    return result

# Get the display dimensions once
def get_display_dimensions():
    """Get the dimensions of the e-Paper display"""
    try:
        epd_temp = epd2in13_V3.EPD()
        width = epd_temp.width
        height = epd_temp.height
        return width, height
    except Exception as e:
        logging.error(f"Error getting display dimensions: {e}")
        # Default dimensions for 2.13" display
        return 122, 250

# Get display dimensions
DISPLAY_WIDTH, DISPLAY_HEIGHT = get_display_dimensions()
logging.info(f"Display dimensions: {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}")

# Calculate the maximum album art size (use a large portion of the display height)
ALBUM_ART_SIZE = int(DISPLAY_WIDTH * 0.7)
logging.info(f"Album art size set to: {ALBUM_ART_SIZE}x{ALBUM_ART_SIZE}")

def process_websocket_data(data):
    """Process data received from WebSocket"""
    try:
        # Parse JSON data
        if not data:
            return {"error": "Empty data received"}
            
        track_data = json.loads(data)
        
        # Check if nothing is playing
        if not track_data.get("isPlaying", True) and track_data.get("message") == "Nothing is playing":
            return {"error": "Nothing is playing"}
            
        return track_data
    except Exception as e:
        logging.error(f"Exception when processing WebSocket data: {str(e)}")
        return {"error": f"Exception when processing data: {str(e)}"}

def get_album_art(url):
    """Download and process album artwork with caching"""
    try:
        if not url:
            return None
            
        # Create a hash of the URL to use as the cache key
        url_hash = hashlib.md5(url.encode()).hexdigest()
        cache_file = os.path.join(cache_dir, f"{url_hash}.png")
        
        # Force download new image - skip cache for now
        logging.info(f"Downloading album art from: {url}")
        try:
            # Increased timeout to 15 seconds
            response = requests.get(url, timeout=15)
            if response.status_code != 200:
                logging.warning(f"Failed to download album art: {response.status_code}")
                return None
                
            # Open the image from the response content
            original_img = Image.open(BytesIO(response.content))
            
            # Create a new blank image with the desired size
            img = Image.new('L', (ALBUM_ART_SIZE, ALBUM_ART_SIZE), 255)
            
            # Resize the original image to fit within our target size while preserving aspect ratio
            original_img.thumbnail((ALBUM_ART_SIZE, ALBUM_ART_SIZE), Image.LANCZOS)
            
            # Calculate position to center the resized image
            paste_x = (ALBUM_ART_SIZE - original_img.width) // 2
            paste_y = (ALBUM_ART_SIZE - original_img.height) // 2
            
            # Convert to grayscale
            original_img = original_img.convert('L')
            
            # Paste the resized image onto our blank canvas
            img.paste(original_img, (paste_x, paste_y))
            
            # Apply rounded corners with a radius of 8 pixels
            img = add_rounded_corners(img, radius=8)
            
            # Apply dithering and convert to 1-bit
            img = img.convert('1', dither=Image.FLOYDSTEINBERG)
            
            # Log the actual size of the image
            logging.info(f"Album art processed to size: {img.width}x{img.height}")
            
            # Save to file cache
            img.save(cache_file)
            
            # Also cache in memory
            album_art_cache[url] = img
            
            return img
        except requests.exceptions.Timeout:
            logging.warning(f"Timeout downloading album art from: {url}")
            return None
        except requests.exceptions.RequestException as e:
            logging.warning(f"Network error downloading album art: {str(e)}")
            return None
            
    except Exception as e:
        logging.error(f"Error processing album art: {str(e)}")
        return None

def initialize_display():
    """Initialize the display once"""
    global epd, BASE_IMAGE
    
    logging.info("Initializing display")
    epd = epd2in13_V3.EPD()
    epd.init()
    epd.Clear(0xFF)  # Clear to white
    
    # Create base image for the display
    BASE_IMAGE = Image.new('1', (epd.height, epd.width), 255)
    
    # Do a full refresh initially
    # Rotate the base image 180 degrees
    rotated_base = BASE_IMAGE.rotate(180)
    epd.display(epd.getbuffer(rotated_base))
    
    # Initialize base image for partial updates (per example script)
    time.sleep(1)  # Short delay to ensure display is ready
    
    return epd, BASE_IMAGE

def should_do_full_refresh(current_time):
    """Determine if we should do a full refresh based on time"""
    global last_full_refresh_time
    
    # Do a full refresh every 10 minutes (600 seconds)
    if current_time - last_full_refresh_time > 600:
        last_full_refresh_time = current_time
        return True
    return False

def data_changed(new_data):
    """Check if the displayed data has changed"""
    global previous_data
    
    if previous_data is None:
        return True
        
    # Check relevant fields - added album to the check
    if new_data.get("title") != previous_data.get("title") or \
       new_data.get("artist") != previous_data.get("artist") or \
       new_data.get("album") != previous_data.get("album") or \
       new_data.get("imageUrl") != previous_data.get("imageUrl") or \
       "error" in new_data != "error" in previous_data:
        return True
    
    return False

def display_data(data):
    """Display the data on the e-Paper display"""
    global epd, BASE_IMAGE, previous_data
    
    try:
        # Initialize display if not already initialized
        if epd is None:
            epd, BASE_IMAGE = initialize_display()
        
        current_time = time.time()
        needs_update = data_changed(data)
        
        # Skip update if data hasn't changed
        if not needs_update:
            logging.info("Data hasn't changed, skipping display update")
            return True
            
        # Check if we need a full refresh
        if should_do_full_refresh(current_time):
            logging.info("Performing scheduled full refresh")
            epd.init()
            epd.Clear(0xFF)
            last_full_refresh_time = current_time
            
            # Re-display base image for partial updates (matching example)
            time_image = Image.new('1', (epd.height, epd.width), 255)
            epd.displayPartBaseImage(epd.getbuffer(time_image))
        
        # Load fonts - adapt to use the approach from the example
        try:
            # First try system fonts
            font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
            font_title = ImageFont.truetype(font_path, 16)
            font_artist = ImageFont.truetype(font_path, 12)
            font_album = ImageFont.truetype(font_path, 12)  # Same size as artist font
            font_status = ImageFont.truetype(font_path, 10)
        except IOError:
            # Fallback to the example's font approach
            logging.info("System fonts not found, using default fonts")
            font_title = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 16)
            font_artist = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 14)
            font_album = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 14)  # Same size as artist font
            font_status = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 10)
        
        # Create a new image with the display dimensions
        logging.info("Creating display image")
        image = Image.new('1', (epd.height, epd.width), 255)  # 1: 1-bit color (black and white)
        draw = ImageDraw.Draw(image)
        
        # Log display dimensions for debugging
        logging.info(f"Display dimensions: {epd.height}x{epd.width}")
        
        # Attempt to get album art if not in error state
        album_art = None
        if "error" not in data and "imageUrl" in data and data["imageUrl"]:
            # Try to get album art, but don't let it block the display update if it fails
            try:
                album_art = get_album_art(data["imageUrl"])
                if album_art:
                    logging.info(f"Album art dimensions: {album_art.width}x{album_art.height}")
            except Exception as e:
                logging.error(f"Album art retrieval failed, continuing without it: {str(e)}")
        
        # New layout constants
        left_margin = 5  # Reduced left margin to make more room
        header_y = 5      # Y position for header
        
        # Draw a header
        draw.text((left_margin, header_y), "Now Playing:", font=font_status, fill=0)
        
        if "error" in data:
            if data["error"] != "Nothing is playing":
                # Only show error if it's actually an error
                draw.text((left_margin, header_y + 20), f"Error: {data['error']}", font=font_status, fill=0)
        else:
            # New layout with album art on the left
            
            # Starting positions
            content_x = left_margin
            content_y = header_y + 20
            
            # Place album art if available
            if album_art:
                # Position album art on the left
                art_position = (left_margin, content_y)
                image.paste(album_art, art_position)
                
                # Calculate available space for text
                available_height = epd.width - (content_y + album_art.height + 5)
                logging.info(f"Available height for text: {available_height}")
                
                # If there's not enough space below the album art, position text to the right
                if available_height < 60:  # Need at least 60 pixels for title, artist and album
                    logging.info("Not enough space below album art, positioning text to the right")
                    
                    # Calculate the total height needed for text (title + album + artist)
                    text_total_height = 58  # Adjusted for reduced spacing
                    
                    # Calculate vertical position to center text alongside album art
                    text_y = content_y + (album_art.height - text_total_height) // 2
                    logging.info(f"Centering text vertically at y={text_y} (album art height={album_art.height}, text height={text_total_height})")
                    
                    # padding between album art and text
                    text_x = left_margin + album_art.width + 10
                    max_text_width = epd.height - text_x - left_margin
                else:
                    # Enough space below the album art
                    text_x = left_margin
                    # Add padding around the text and album art
                    text_y = content_y + album_art.height + 10
                    max_text_width = epd.height - (left_margin * 2)
            else:
                # No album art, position text at the left margin
                text_x = left_margin
                text_y = content_y
                max_text_width = epd.height - (left_margin * 2)
            
            # Display song title
            if "title" in data:
                title = data["title"]
                # Truncate title if too long
                if draw.textlength(title, font=font_title) > max_text_width:
                    while draw.textlength(title + "...", font=font_title) > max_text_width:
                        title = title[:-1]
                    title += "..."
                draw.text((text_x, text_y), title, font=font_title, fill=0)
            
            # Display album name below title
            if "album" in data:
                album = data["album"]
                # Truncate album if too long
                if draw.textlength(album, font=font_album) > max_text_width:
                    while draw.textlength(album + "...", font=font_album) > max_text_width:
                        album = album[:-1]
                    album += "..."
                # Spacing between title and album
                album_y = text_y + 28
                draw.text((text_x, album_y), album, font=font_album, fill=0)
            
            # Display artist below album name
            if "artist" in data:
                artist = data["artist"]
                # Truncate artist if too long
                if draw.textlength(artist, font=font_artist) > max_text_width:
                    while draw.textlength(artist + "...", font=font_artist) > max_text_width:
                        artist = artist[:-1]
                    artist += "..."
                # Spacing between album and artist
                artist_y = album_y + 16
                draw.text((text_x, artist_y), artist, font=font_artist, fill=0)
        
        # Display the image on the e-paper - using partial update method from example
        logging.info("Displaying buffer on e-Paper (partial update)")
        
        # Rotate the image 180 degrees before displaying
        rotated_image = image.rotate(180)
        epd.displayPartial(epd.getbuffer(rotated_image))
        
        # Update previous data
        previous_data = data.copy() if isinstance(data, dict) else data
        
        return True
    except Exception as e:
        logging.error(f"Error displaying data: {str(e)}")
        traceback.print_exc()
        # If there's an error, try to re-initialize the display
        epd = None
        return False

# WebSocket Handlers
def on_message(ws, message):
    """Handle incoming WebSocket messages"""
    logging.info("Received WebSocket message")
    try:
        data = process_websocket_data(message)
        display_data(data)
    except Exception as e:
        logging.error(f"Error processing message: {str(e)}")
        traceback.print_exc()

def on_error(ws, error):
    """Handle WebSocket errors"""
    logging.error(f"WebSocket error: {str(error)}")

def on_close(ws, close_status_code, close_msg):
    """Handle WebSocket connection close"""
    global reconnect_attempt
    logging.warning(f"WebSocket closed. Status code: {close_status_code}, Message: {close_msg}")
    
    # Attempt to reconnect
    if reconnect_attempt < MAX_RECONNECT_ATTEMPTS:
        reconnect_attempt += 1
        delay = RECONNECT_DELAY * reconnect_attempt
        logging.info(f"Attempting to reconnect in {delay} seconds (attempt {reconnect_attempt}/{MAX_RECONNECT_ATTEMPTS})...")
        time.sleep(delay)
        start_websocket()
    else:
        logging.error(f"Maximum reconnection attempts ({MAX_RECONNECT_ATTEMPTS}) reached. Exiting.")
        sys.exit(1)

def on_open(ws):
    """Handle WebSocket connection open"""
    global reconnect_attempt
    logging.info("WebSocket connection established")
    reconnect_attempt = 0  # Reset reconnect counter on successful connection

def start_websocket():
    """Start the WebSocket connection"""
    global websocket_app
    
    ws_url = "wss://api.kyle.so/spotify/current-track/ws?user=mrdickeyy"
    logging.info(f"Connecting to WebSocket at {ws_url}")
    
    websocket.enableTrace(True)  # Enable trace for debugging
    websocket_app = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    # Start WebSocket connection in a separate thread
    wst = threading.Thread(target=websocket_app.run_forever)
    wst.daemon = True
    wst.start()
    return wst

def main():
    """Main function"""
    try:
        logging.info("Starting Spotify track display with WebSocket")
        logging.info("Press Ctrl+C to exit")
        
        # Initial display setup
        global epd, BASE_IMAGE, websocket_thread
        epd, BASE_IMAGE = initialize_display()
        
        # Set up for partial updates (per example script)
        time_image = Image.new('1', (epd.height, epd.width), 255)
        # Rotate the time image 180 degrees
        rotated_time_image = time_image.rotate(180)
        epd.displayPartBaseImage(epd.getbuffer(rotated_time_image))
        last_full_refresh_time = time.time()
        
        # Start WebSocket connection
        websocket_thread = start_websocket()
        
        # Keep main thread alive
        while True:
            # Check if we need a full refresh periodically
            current_time = time.time()
            if should_do_full_refresh(current_time):
                logging.info("Performing scheduled full refresh")
                epd.init()
                epd.Clear(0xFF)
                
                # Re-display base image for partial updates
                time_image = Image.new('1', (epd.height, epd.width), 255)
                epd.displayPartBaseImage(epd.getbuffer(time_image))
                
                last_full_refresh_time = current_time
            
            # Sleep to reduce CPU usage
            time.sleep(60)  # Check every minute
            
    except KeyboardInterrupt:
        logging.info("Program terminated by user")
        logging.info("Exiting gracefully...")
        # Clean up resources
        try:
            if websocket_app is not None:
                websocket_app.close()
            if epd is not None:
                epd.init()
                epd.Clear(0xFF)
                epd.sleep()
        except:
            pass
    except Exception as e:
        logging.error(f"A critical error occurred: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
