#!/usr/bin/python3
import sys
import os
import time
import requests
from PIL import Image, ImageDraw, ImageFont

# Add the e-Paper library to the path
lib_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'e-Paper/RaspberryPi_JetsonNano/python/lib')
if os.path.exists(lib_path):
    sys.path.append(lib_path)
else:
    lib_path = '/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib'
    sys.path.append(lib_path)

# Import the Waveshare display driver
from waveshare_epd import epd2in13_V2

def fetch_api_data():
    """Fetch data from your API"""
    try:
        response = requests.get("https://api.kyle.so/spotify/current-track?user=mrdickeyy")
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API request failed with status code: {response.status_code}"}
    except Exception as e:
        return {"error": f"Exception when fetching API data: {str(e)}"}

def display_data(data):
    """Display the data on the e-Paper display"""
    try:
        # Initialize the display
        epd = epd2in13_V2.EPD()
        epd.init(epd.FULL_UPDATE)
        epd.Clear(0xFF)  # Clear to white
        
        # Create a new image with the display dimensions
        # Note: For this display, width and height are swapped in the image creation
        image = Image.new('1', (epd.height, epd.width), 255)  # 1: 1-bit color (black and white)
        draw = ImageDraw.Draw(image)
        
        # Load a font
        font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        font_title = ImageFont.truetype(font_path, 16)
        font_text = ImageFont.truetype(font_path, 12)
        
        # Draw a title
        draw.text((5, 5), "Spotify Current Track", font=font_title, fill=0)
        draw.line((5, 25, epd.height-5, 25), fill=0)
        
        # Format and display the data
        y_position = 30
        
        if "error" in data:
            draw.text((5, y_position), f"Error: {data['error']}", font=font_text, fill=0)
        else:
            # Display each key-value pair from the API data
            # Customize this section based on your API response structure
            for key, value in data.items():
                if isinstance(value, (str, int, float, bool)):
                    text = f"{key}: {value}"
                    # Truncate text if it's too long
                    if draw.textlength(text, font=font_text) > epd.height - 10:
                        while draw.textlength(text + "...", font=font_text) > epd.height - 10:
                            text = text[:-1]
                        text += "..."
                    draw.text((5, y_position), text, font=font_text, fill=0)
                    y_position += 15
                    
                    # Check if we're running out of space
                    if y_position > epd.width - 20:
                        draw.text((5, y_position), "...", font=font_text, fill=0)
                        break
        
        # Display the image on the e-paper
        epd.display(epd.getbuffer(image))
        
        # Put display to sleep to save power
        epd.sleep()
        
        return True
    except Exception as e:
        print(f"Error displaying data: {str(e)}")
        return False

def main():
    """Main function"""
    try:
        print("Fetching API data...")
        data = fetch_api_data()
        
        print("Displaying data on e-Paper...")
        success = display_data(data)
        
        if success:
            print("Data displayed successfully!")
        else:
            print("Failed to display data.")
            
    except KeyboardInterrupt:
        print("Program terminated by user")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
