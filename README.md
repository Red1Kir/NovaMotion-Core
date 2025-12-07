# NovaMotion Core

Intelligent Motion Planning System for 3D Printers with Digital Twin and MPC Control.

## Features

- **Digital Twin Modeling**: Physical simulation of printer dynamics
- **MPC Trajectory Optimization**: Predictive control for optimal motion
- **TMC2209 Integration**: Full hardware support with auto-calibration
- **Web Interface**: Real-time visualization and control
- **Auto-Calibration**: Automatic measurement of resonance, backlash, and inertia

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/novamotion-core.git
cd novamotion-core

# Run installation script
chmod +x install.sh
./install.sh

# For systemd service
./install.sh --systemd