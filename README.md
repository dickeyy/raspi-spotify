# Raspberry Pi Spotify Display

> [!NOTE]
> This program _technically_ displays Last.fm data, not Spotify directly. So please have a Last.fm account and link your Spotify account to it otherwise the program will not work. The data should be the same, Spotify's API just doesn't provide the necessary data, and Last.fm's API is _much_ easier to use with far fewer restrictions.

This is a little program that displays whatever song you are currently listening to on Spotify on a Waveshare e-Paper display connected to a Raspberry Pi.

## Required Hardware

- Raspberry Pi (any model but I recommend using a Raspi Zero 2 W).
- Waveshare 2.13" e-Paper Display (HAT mode recommended).
- 5V 3A Power Supply (or a PiSugar battery pack).

## Required Software

- Any OS will work, I have only tested on Raspberry Pi OS Lite 32-bit though.
- Python 3.10+
- Waveshare e-Paper display library. Currently only supports Waveshare 2.13" e-Paper HAT.
- Python packages: requests, Pillow (PIL)

## Installation

### 1. Set up your Raspberry Pi

1. Install Raspberry Pi OS (or your preferred OS) on your Raspberry Pi.
2. Connect the Waveshare e-Paper display to your Raspberry Pi according to the manufacturer's instructions.
3. Enable SPI interface on your Raspberry Pi:
   ```
   sudo raspi-config
   ```
   Navigate to "Interface Options" > "SPI" > "Yes" to enable SPI.

### 2. Install the Waveshare e-Paper library

```bash
# Clone the Waveshare e-Paper library repository
cd ~
git clone https://github.com/waveshare/e-Paper.git
```

### 3. Install required Python packages

```bash
# Install required packages
sudo apt-get update
sudo apt-get install -y python3-pip python3-pil python3-numpy
pip3 install requests Pillow
```

### 4. Clone this repository

```bash
# Clone this repository
cd ~
git clone https://github.com/yourusername/raspi-spotify.git
cd raspi-spotify
```

### 5. Configure the API endpoint

The script uses an API endpoint to fetch your currently playing Spotify track. By default, it uses:

```
https://api.kyle.so/spotify/current-track?user=mrdickeyy
```

Note that this API is mine and NOT official. I'm not affiliated with Spotify or Last.fm. You will need to replace the `user` parameter with your own **Last.fm username**, NOT your Spotify username.

You'll need to either:

1. Set up your own API endpoint that returns your Spotify data in the same format
   - Source code for my API is [here](https://github.com/dickeyy/dickey-api)
2. Or modify the script to use a different method to fetch your Spotify data

## Running the Program

### Manual Run

To run the program manually:

```bash
cd ~/raspi-spotify
python3 spotify.py
```

Once you start playing a song on Spotify, from anywhere in the world, the display will update with the song information. The default refresh rate is 10 seconds so be patient. You _can_ change this in the script, though, I ask that if you want a high refresh rate, you also self-host the API to save on my server resources.

### Run as a Service (recommended)

To have the program start automatically when your Raspberry Pi boots:

1. Create a systemd service file:

```bash
sudo nano /etc/systemd/system/spotify-display.service
```

2. Add the following content:

```
[Unit]
Description=Spotify e-Paper Display
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/raspi-spotify/spotify.py
WorkingDirectory=/home/pi/raspi-spotify
StandardOutput=inherit
StandardError=inherit
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

3. Enable and start the service:

```bash
sudo systemctl enable spotify-display.service
sudo systemctl start spotify-display.service
```

4. Check the status of the service:

```bash
sudo systemctl status spotify-display.service
```

## Troubleshooting

- If you encounter issues with the display, check the SPI interface is enabled.
- Ensure the Waveshare e-Paper library is correctly installed.
- Check the logs for any errors:
  ```bash
  sudo journalctl -u spotify-display.service
  ```

## Customization

You can modify the `spotify.py` script to change:

- The refresh rate (currently set to 10 seconds)
- The display layout
- The API endpoint for fetching Spotify data

## License

[MIT License](LICENSE)
