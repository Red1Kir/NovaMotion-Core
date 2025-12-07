"""
Hardware interface module for NovaMotion Core
Communication with TMC2209 and other hardware components
"""

from .tmc2209_driver import TMC2209Driver, TMC2209Config
from .hardware_manager import HardwareManager
from .sensor_interface import SensorInterface

__all__ = [
    'TMC2209Driver',
    'TMC2209Config',
    'HardwareManager',
    'SensorInterface'
]