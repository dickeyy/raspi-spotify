#!/usr/bin/python3
import sys
import os
import time
from PIL import Image, ImageDraw, ImageFont

# Add the Waveshare e-Paper library path
lib_path = '/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib'
if os.path.exists(lib_path):
    sys.path.append(lib_path)
else:
    print(f"Error: Library path {lib_path} not found!")
    print("Please make sure you've cloned the Waveshare e-Paper repository to /home/pi/e-Paper")
    sys.exit(1)

# Import the Waveshare display driver
try:
    from waveshare_epd import epd2in13_V2
except ImportError:
    print("Error: Could not import the Waveshare e-Paper library!")
    print("Make sure you've cloned the repository: git clone https://github.com/waveshare/e-Paper.git")
    sys.exit(1)

def main():
    try:
        print("Initializing e-Paper display...")
        
        # Initialize the display
        epd = epd2in13_V2.EPD()
        epd.init(epd.FULL_UPDATE)
        
        # Clear the display (white)
        print("Clearing display...")
        epd.Clear(0xFF)
        time.sleep(1)  # Wait a second to see the clear effect
        
        # Create a new image with the display dimensions
        print("Creating image...")
        image = Image.new('1', (epd.height, epd.width), 255)  # 1: 1-bit color (black and white)
        draw = ImageDraw.Draw(image)
        
        # Try to load a font
        try:
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 24)
        except IOError:
            # Fallback to default font if the specified one isn't available
            print("Warning: Could not load DejaVuSans font, using default...")
            font = ImageFont.load_default()
        
        # Draw a simple string
        print("Drawing text...")
        text = "Hello, e-Paper!"
        draw.text((10, 50), text, font=font, fill=0)  # 0 = black
        
        # Draw a border around the display
        draw.rectangle((0, 0, epd.height-1, epd.width-1), outline=0)
        
        # Display the image on the e-paper
        print("Displaying on e-Paper...")
        epd.display(epd.getbuffer(image))
        
        print("Display update complete!")
        print("If you don't see anything on the display, check connections and lighting.")
        
        # Sleep mode to save power
        epd.sleep()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
