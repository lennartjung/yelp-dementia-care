#!/bin/bash
# Install web interface for Yelp

echo "=== Installing Yelp Web Interface ==="
echo ""

cd /home/ljung/yelp
source venv/bin/activate

# Install Flask
echo "Installing Flask..."
pip install flask

# Copy service file
echo "Installing systemd service..."
sudo cp yelp_web.service /etc/systemd/system/

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable yelp_web.service
sudo systemctl start yelp_web.service

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Web interface is running on:"
echo "  http://localhost:5000"
echo "  http://$(hostname -I | awk '{print $1}'):5000"
echo ""

# Get Tailscale IP if available
if command -v tailscale &> /dev/null; then
    TAILSCALE_IP=$(tailscale ip -4 2>/dev/null)
    if [ -n "$TAILSCALE_IP" ]; then
        echo "  http://$TAILSCALE_IP:5000 (Tailscale)"
        echo ""
    fi
fi

echo "Service management:"
echo "  sudo systemctl status yelp_web"
echo "  sudo systemctl restart yelp_web"
echo "  sudo systemctl stop yelp_web"
