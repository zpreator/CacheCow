# Youtubedl and Radarr Integration

This project does 3 things:
1. Hosts a web UI for managing youtube downloads (Docker, streamlit)
2. A python script for downloading youtube videos from curated list of creators (via cronjob)
3. A python script for adding movies to Radarr from my letterboxd wishlist (via cronjob)

## Web UI

The webui presents all your youtube subsriptions with checkboxes to curate. 
*Only edits a config file, which is then used in the python script for youtube download.

![image](https://github.com/user-attachments/assets/81ae0e0d-4a30-464f-bbe9-a33756af8d3f)

## Youtube Download

Uses the config file generated from the Web UI to download youtube videos using youtubedl

## Letterboxd to Radarr

Scrapes the public watchlist of a letterboxd account to add to Radarr

## Server Setup

This is mostly my notes for how to set this up.

### Radarr

### Prowlarr

### Qbittorrent

### Windscribe
Using tightvncserver, login to the desktop, install the windscribe linux app (gui) and login.

Adjust the settings to:

1. Start on computer boot (Should start as soon as vncserver starts on reboot)
2. Firewall always on (when windscribe quits, stop all internet traffic)
3. Allow lan connections (allow local connections. Turning this off will lock you out!!)
### Install tightvncserver
I am using the paid Windscribe VPN.

Windscribe VPN has a cli, but I found the GUI to work better and have more options (split tunneling, killswitch etc.)

So in order to get windscribe to launch reliably on reboot on a headless ubuntu server, I need a virtual desktop. Hence, tightvncserver which can create a virtual desktop on reboot

Install tightvncserver and dependencies
```
sudo apt update
sudo apt install tightvncserver xfce4 xfce4-goodies
```

Test server (switch :1 with :2 or :<num> for different IDs)
```
tightvncserver :1
```

If no errors, kill the server
```
tightvncserver -kill :1
```

Create vnc startup config
```
nano ~/.vnc/xstartup
```

Add the following for a light desktop experience
```bash
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
exec startxfce4 &
```


Create script to auto launch on reboot
```cmd
sudo nano /etc/init.d/tightvncserver
```

Fill with the following, making sure to replace the user with the user you are using
```bash
#!/bin/bash
### BEGIN INIT INFO
# Provides:          tightvncserver
# Required-Start:    $local_fs
# Required-Stop:     $local_fs
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Start/stop TightVNC server
### END INIT INFO

# Define the user to start VNC under
USER="<your_username>"
DISPLAY=":1"

case "$1" in
  start)
    echo "Starting VNC server for $USER on display $DISPLAY"
    su - $USER -c "/usr/bin/tightvncserver $DISPLAY"
    ;;
  stop)
    echo "Stopping VNC server for $USER on display $DISPLAY"
    su - $USER -c "/usr/bin/tightvncserver -kill $DISPLAY"
    ;;
  restart)
    $0 stop
    $0 start
    ;;
  *)
    echo "Usage: /etc/init.d/tightvncserver {start|stop|restart}"
    exit 1
    ;;
esac

exit 0
```

Make the script executable
```
sudo chmod +x /etc/init.d/tightvncserver
```

Add the script to the startup sequence
```
sudo update-rc.d tightvncserver defaults
```

It should work on reboot, but just to test it manually:
```
sudo /etc/init.d/tightvncserver start
```