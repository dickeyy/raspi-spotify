#!/usr/bin/python3
import sys
import os
import time
import requests
import logging
from PIL import Image, ImageDraw, ImageFont
import traceback

# Set up paths similar to the working example
picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)
else:
    # Fallback path if the first one doesn't exist
    libdir = '/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib'
    sys.path.append(libdir)
    picdir = '/home/pi/e-Paper/RaspberryPi_JetsonNano/python/pic'

# Import the Waveshare display driver - using the same model as the example
from waveshare_epd import epd2in9_V2

# Set up logging
logging.basicConfig(level=logging.DEBUG)

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

def display_data(data):
    """Display the data on the e-Paper display"""
    try:
        # Initialize the display - following the example's approach
        logging.info("Initializing display")
        epd = epd2in9_V2.EPD()
        epd.init()
        epd.Clear(0xFF)  # Clear to white
        
        # Load fonts - adapt to use the approach from the example
        try:
            # First try system fonts
            font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
            font_title = ImageFont.truetype(font_path, 18)
            font_artist = ImageFont.truetype(font_path, 16)
            font_status = ImageFont.truetype(font_path, 12)
        except IOError:
            # Fallback to the example's font approach
            logging.info("System fonts not found, using default fonts")
            font_title = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 18)
            font_artist = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 16)
            font_status = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 12)
        
        # Create a new image with the display dimensions - match the example's approach
        # Note: For this display, width and height are swapped in the image creation
        logging.info("Creating display image")
        image = Image.new('1', (epd.height, epd.width), 255)  # 1: 1-bit color (black and white)
        draw = ImageDraw.Draw(image)
        
        # Draw a header
        draw.text((5, 5), "Now Playing:", font=font_status, fill=0)
        
        if "error" in data:
            if data["error"] == "Nothing is playing":
                # Special case for when nothing is playing
                draw.text((5, 25), "Nothing playing :(", font=font_artist, fill=0)
            else:
                # Handle other errors
                draw.text((5, 25), f"Error: {data['error']}", font=font_status, fill=0)
        else:
            # Display song title
            if "title" in data:
                title = data["title"]
                # Truncate title if too long
                if draw.textlength(title, font=font_title) > epd.height - 10:
                    while draw.textlength(title + "...", font=font_title) > epd.height - 10:
                        title = title[:-1]
                    title += "..."
                draw.text((5, 25), title, font=font_title, fill=0)
            
            # Display artist
            if "artist" in data:
                artist = data["artist"]
                # Truncate artist if too long
                if draw.textlength(artist, font=font_artist) > epd.height - 10:
                    while draw.textlength(artist + "...", font=font_artist) > epd.height - 10:
                        artist = artist[:-1]
                    artist += "..."
                draw.text((5, 50), artist, font=font_artist, fill=0)
            
            # Display playing status
            status_text = "▶ Playing" if data.get("isPlaying", False) else "❚❚ Paused"
            draw.text((5, 75), status_text, font=font_status, fill=0)
        
        # Display the image on the e-paper
        logging.info("Displaying buffer on e-Paper")
        epd.display(epd.getbuffer(image))
        
        # Put display to sleep to save power
        logging.info("Putting display to sleep")
        epd.sleep()
        
        return True
    except Exception as e:
        logging.error(f"Error displaying data: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """Main function"""
    try:
        logging.info("Starting Spotify track display")
        print("Press Ctrl+C to exit")
        
        while True:
            try:
                logging.info("Fetching API data...")
                data = fetch_api_data()
                
                logging.info("Displaying data on e-Paper...")
                success = display_data(data)
                
                if success:
                    logging.info("Data displayed successfully!")
                else:
                    logging.error("Failed to display data.")
                
                # Wait before refreshing
                logging.info(f"Waiting 30 seconds before next refresh...")
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
            epd = epd2in9_V2.EPD()
            epd.init()
            epd.Clear(0xFF)
            epd.sleep()
            epd2in9_V2.epdconfig.module_exit(cleanup=True)
        except:
            pass
    except Exception as e:
        logging.error(f"A critical error occurred: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
