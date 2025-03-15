#!/usr/bin/python3
import sys
import os
import time
import requests
import logging
from PIL import Image, ImageDraw, ImageFont
import traceback

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

def fetch_api_data():
    """Fetch data from API"""
    try:
        response = requests.get("https://api.kyle.so/spotify/current-track?user=mrdickeyy")
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API request failed with status code: {response.status_code}"}
    except Exception as e:
        logging.error(f"Exception when fetching API data: {str(e)}")
        return {"error": f"Exception when fetching API data: {str(e)}"}

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
    epd.display(epd.getbuffer(BASE_IMAGE))
    
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
        
    # Check relevant fields
    if new_data.get("title") != previous_data.get("title") or \
       new_data.get("artist") != previous_data.get("artist") or \
       new_data.get("isPlaying") != previous_data.get("isPlaying") or \
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
            font_artist = ImageFont.truetype(font_path, 14)
            font_status = ImageFont.truetype(font_path, 12)
        except IOError:
            # Fallback to the example's font approach
            logging.info("System fonts not found, using default fonts")
            font_title = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 16)
            font_artist = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 14)
            font_status = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 12)
        
        # Create a new image with the display dimensions
        logging.info("Creating display image")
        image = Image.new('1', (epd.height, epd.width), 255)  # 1: 1-bit color (black and white)
        draw = ImageDraw.Draw(image)
        
        # Calculate better margin - centered more
        left_margin = 15
        
        # Draw a header
        draw.text((left_margin, 5), "Now Playing:", font=font_status, fill=0)
        
        if "error" in data:
            if data["error"] == "Nothing is playing":
                # Special case for when nothing is playing
                draw.text((left_margin, 25), "Nothing playing :(", font=font_artist, fill=0)
            else:
                # Handle other errors
                draw.text((left_margin, 25), f"Error: {data['error']}", font=font_status, fill=0)
        else:
            # Display song title
            if "title" in data:
                title = data["title"]
                # Truncate title if too long
                if draw.textlength(title, font=font_title) > epd.height - (left_margin*2):
                    while draw.textlength(title + "...", font=font_title) > epd.height - (left_margin*2):
                        title = title[:-1]
                    title += "..."
                draw.text((left_margin, 25), title, font=font_title, fill=0)
            
            # Display artist
            if "artist" in data:
                artist = data["artist"]
                # Truncate artist if too long
                if draw.textlength(artist, font=font_artist) > epd.height - (left_margin*2):
                    while draw.textlength(artist + "...", font=font_artist) > epd.height - (left_margin*2):
                        artist = artist[:-1]
                    artist += "..."
                draw.text((left_margin, 45), artist, font=font_artist, fill=0)
            
            # Display playing status
            status_text = "▶ Playing" if data.get("isPlaying", False) else "❚❚ Paused"
            draw.text((left_margin, 65), status_text, font=font_status, fill=0)
        
        # Display the image on the e-paper - using partial update method from example
        logging.info("Displaying buffer on e-Paper (partial update)")
        epd.displayPartial(epd.getbuffer(image))
        
        # Update previous data
        previous_data = data.copy() if isinstance(data, dict) else data
        
        return True
    except Exception as e:
        logging.error(f"Error displaying data: {str(e)}")
        traceback.print_exc()
        # If there's an error, try to re-initialize the display
        epd = None
        return False

def main():
    """Main function"""
    try:
        logging.info("Starting Spotify track display")
        print("Press Ctrl+C to exit")
        
        # Initial display setup
        global epd, BASE_IMAGE
        epd, BASE_IMAGE = initialize_display()
        
        # Set up for partial updates (per example script)
        time_image = Image.new('1', (epd.height, epd.width), 255)
        epd.displayPartBaseImage(epd.getbuffer(time_image))
        last_full_refresh_time = time.time()
        
        while True:
            try:
                logging.info("Fetching API data...")
                data = fetch_api_data()
                
                logging.info("Updating display if needed...")
                success = display_data(data)
                
                if success:
                    logging.info("Display update successful")
                else:
                    logging.error("Failed to update display")
                
                # Wait before refreshing
                logging.info(f"Waiting 30 seconds before next check...")
                time.sleep(30)
                
            except Exception as e:
                logging.error(f"Error in refresh cycle: {str(e)}")
                traceback.print_exc()
                logging.info("Will try again in 30 seconds...")
                time.sleep(30)
            
    except KeyboardInterrupt:
        logging.info("Program terminated by user")
        logging.info("Exiting gracefully...")
        # Clean up resources
        try:
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
