"""
Sensor interface for reading various printer sensors
"""

import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import random

@dataclass
class SensorReading:
    """Single sensor reading"""
    value: float
    unit: str
    timestamp: float
    valid: bool

class SensorInterface:
    """Interface for various printer sensors"""
    
    def __init__(self):
        self.sensors = {}
        self.readings = {}
        
    def add_thermistor(self, name: str, pin: int, 
                      resistance: float = 100000,
                      beta: float = 3950) -> bool:
        """Add a thermistor sensor"""
        self.sensors[name] = {
            'type': 'thermistor',
            'pin': pin,
            'resistance': resistance,
            'beta': beta,
            'connected': True
        }
        return True
    
    def add_accelerometer(self, name: str, port: str) -> bool:
        """Add an accelerometer sensor"""
        self.sensors[name] = {
            'type': 'accelerometer',
            'port': port,
            'connected': True
        }
        return True
    
    def add_encoder(self, name: str, ppi: int) -> bool:
        """Add an encoder sensor"""
        self.sensors[name] = {
            'type': 'encoder',
            'ppi': ppi,  # Pulses per inch
            'connected': True
        }
        return True
    
    def read_temperature(self, name: str) -> Optional[SensorReading]:
        """Read temperature from sensor"""
        if name not in self.sensors:
            return None
        
        sensor = self.sensors[name]
        if not sensor['connected']:
            return SensorReading(0.0, 'C', time.time(), False)
        
        # Simulated temperature reading
        # In real implementation, this would read from actual hardware
        if sensor['type'] == 'thermistor':
            # Simulate bed temperature around 60C
            temp = 60.0 + random.uniform(-2, 2)
            return SensorReading(temp, 'C', time.time(), True)
        
        return None
    
    def read_acceleration(self, name: str) -> Optional[Dict[str, SensorReading]]:
        """Read acceleration from sensor"""
        if name not in self.sensors:
            return None
        
        sensor = self.sensors[name]
        if not sensor['connected'] or sensor['type'] != 'accelerometer':
            return None
        
        # Simulated accelerometer readings
        timestamp = time.time()
        return {
            'x': SensorReading(
                random.uniform(-0.5, 0.5), 'g', timestamp, True
            ),
            'y': SensorReading(
                random.uniform(-0.5, 0.5), 'g', timestamp, True
            ),
            'z': SensorReading(
                1.0 + random.uniform(-0.1, 0.1), 'g', timestamp, True
            )
        }
    
    def read_position(self, name: str) -> Optional[SensorReading]:
        """Read position from encoder"""
        if name not in self.sensors:
            return None
        
        sensor = self.sensors[name]
        if not sensor['connected'] or sensor['type'] != 'encoder':
            return None
        
        # Simulated encoder reading
        position = random.uniform(0, 100)  # mm
        return SensorReading(position, 'mm', time.time(), True)
    
    def read_vibration(self, name: str, duration: float = 0.1) -> Optional[Dict]:
        """Measure vibration spectrum"""
        if name not in self.sensors:
            return None
        
        # Simulate FFT analysis
        timestamp = time.time()
        
        # Generate some frequency peaks
        frequencies = list(range(10, 101, 10))
        amplitudes = [random.uniform(0, 1) for _ in frequencies]
        
        # Add resonance peaks at typical frequencies
        resonance_freqs = [45, 38, 67]
        for freq in resonance_freqs:
            if freq <= 100:
                idx = frequencies.index(freq) if freq in frequencies else -1
                if idx >= 0:
                    amplitudes[idx] = random.uniform(0.8, 1.2)
        
        return {
            'frequencies': frequencies,
            'amplitudes': amplitudes,
            'rms': sum(a**2 for a in amplitudes) ** 0.5 / len(amplitudes),
            'peak_frequency': frequencies[amplitudes.index(max(amplitudes))],
            'peak_amplitude': max(amplitudes),
            'timestamp': timestamp
        }
    
    def calibrate_sensor(self, name: str) -> bool:
        """Calibrate a sensor"""
        if name in self.sensors:
            print(f"Calibrating sensor {name}...")
            # Simulate calibration
            time.sleep(0.5)
            print(f"✅ Sensor {name} calibrated")
            return True
        return False
    
    def get_sensor_status(self) -> Dict:
        """Get status of all sensors"""
        status = {}
        for name, sensor in self.sensors.items():
            status[name] = {
                'type': sensor['type'],
                'connected': sensor['connected'],
                'last_reading': self.readings.get(name)
            }
        return status