#!/bin/bash
# NovaMotion Core Installation Script

set -e

echo "Installing NovaMotion Core..."

# Check Python version
python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $python_version"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
echo "Creating directories..."
mkdir -p logs
mkdir -p data/calibrations
mkdir -p data/simulations
mkdir -p config

# Set permissions
echo "Setting permissions..."
chmod +x main.py

# Create default configuration
if [ ! -f "config/settings.json" ]; then
    echo "Creating default configuration..."
    cat > config/settings.json << EOF
{
    "web_port": 5000,
    "serial_port": "/dev/ttyUSB0",
    "baudrate": 115200,
    "log_level": "INFO",
    "data_path": "./data",
    "calibration_file": "./data/calibrations/latest.json"
}
EOF
fi

# Create systemd service file if requested
if [ "$1" = "--systemd" ]; then
    echo "Creating systemd service..."
    sudo cat > /etc/systemd/system/novamotion.service << EOF
[Unit]
Description=NovaMotion Core Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/venv/bin"
ExecStart=$(pwd)/venv/bin/python main.py --mode web
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable novamotion.service
    echo "Service installed. Start with: sudo systemctl start novamotion"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "To start NovaMotion Core:"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
echo "Or use one of these modes:"
echo "  python main.py --mode web        # Web interface"
echo "  python main.py --mode calibrate  # Calibration"
echo "  python main.py --mode demo       # Demo"
echo "  python main.py --mode test       # Hardware test"
echo ""
echo "Web interface: http://localhost:5000"