"""
Digital Twin module for NovaMotion Core
Physical modeling and simulation of 3D printer dynamics
"""

from .printer_model import (
    DigitalTwin,
    PrinterParams
)

__all__ = [
    'DigitalTwin',
    'PrinterParams'
]