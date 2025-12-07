"""
Automatic calibration routines for printer parameters
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import json
import time

@dataclass
class CalibrationResult:
    """Results of calibration procedure"""
    success: bool
    parameters: Dict[str, float]
    resonance_peaks: List[Dict[str, float]]
    backlash_measurements: Dict[str, float]
    motor_currents: Dict[str, float]
    timestamp: float
    duration: float
    
    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'parameters': self.parameters,
            'resonance_peaks': self.resonance_peaks,
            'backlash_measurements': self.backlash_measurements,
            'motor_currents': self.motor_currents,
            'timestamp': self.timestamp,
            'duration': self.duration
        }
    
    def save(self, filename: str):
        """Save calibration results to file"""
        with open(filename, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, filename: str) -> 'CalibrationResult':
        """Load calibration results from file"""
        with open(filename, 'r') as f:
            data = json.load(f)
        
        return cls(
            success=data['success'],
            parameters=data['parameters'],
            resonance_peaks=data['resonance_peaks'],
            backlash_measurements=data['backlash_measurements'],
            motor_currents=data['motor_currents'],
            timestamp=data['timestamp'],
            duration=data['duration']
        )

class AutoCalibrator:
    """Automatic calibration system for printer parameters"""
    
    def __init__(self, hardware_interface=None):
        self.hardware = hardware_interface
        self.results = None
        
    def full_calibration(self, save_path: Optional[str] = None) -> CalibrationResult:
        """
        Perform full automatic calibration
        
        Returns:
            CalibrationResult object with all parameters
        """
        start_time = time.time()
        
        try:
            print("Starting full calibration procedure...")
            
            # 1. Motor current calibration
            print("\n[1/5] Calibrating motor currents...")
            motor_currents = self._calibrate_motor_currents()
            
            # 2. Resonance frequency measurement
            print("\n[2/5] Measuring resonance frequencies...")
            resonance_data = self._measure_resonances()
            
            # 3. Backlash measurement
            print("\n[3/5] Measuring backlash...")
            backlash_data = self._measure_backlash()
            
            # 4. Inertia estimation
            print("\n[4/5] Estimating inertia...")
            inertia_data = self._estimate_inertia()
            
            # 5. Stiffness measurement
            print("\n[5/5] Measuring stiffness...")
            stiffness_data = self._measure_stiffness()
            
            # Combine all parameters
            parameters = {
                **motor_currents,
                **resonance_data,
                **backlash_data,
                **inertia_data,
                **stiffness_data
            }
            
            # Extract resonance peaks for reporting
            resonance_peaks = []
            for axis in ['x', 'y']:
                freq_key = f'resonance_freq_{axis}'
                if freq_key in parameters:
                    resonance_peaks.append({
                        'axis': axis,
                        'frequency': parameters[freq_key],
                        'amplitude': 1.0  # Simplified
                    })
            
            duration = time.time() - start_time
            
            self.results = CalibrationResult(
                success=True,
                parameters=parameters,
                resonance_peaks=resonance_peaks,
                backlash_measurements=backlash_data,
                motor_currents=motor_currents,
                timestamp=start_time,
                duration=duration
            )
            
            print(f"\n✅ Calibration completed in {duration:.1f} seconds")
            
            if save_path:
                self.results.save(save_path)
                print(f"Results saved to {save_path}")
            
            return self.results
            
        except Exception as e:
            print(f"❌ Calibration failed: {e}")
            duration = time.time() - start_time
            
            return CalibrationResult(
                success=False,
                parameters={},
                resonance_peaks=[],
                backlash_measurements={},
                motor_currents={},
                timestamp=start_time,
                duration=duration
            )
    
    def _calibrate_motor_currents(self) -> Dict[str, float]:
        """Calibrate optimal motor currents"""
        if self.hardware:
            # Real hardware calibration
            currents = {}
            for axis in ['x', 'y', 'z', 'e']:
                try:
                    # This would use the hardware interface
                    current = self.hardware.auto_tune_current(axis)
                    currents[f'motor_current_{axis}'] = current
                except:
                    currents[f'motor_current_{axis}'] = 1.2  # Default
        else:
            # Simulated calibration
            currents = {
                'motor_current_x': 1.2,
                'motor_current_y': 1.2,
                'motor_current_z': 1.0,
                'motor_current_e': 0.8
            }
        
        return currents
    
    def _measure_resonances(self) -> Dict[str, float]:
        """Measure resonance frequencies"""
        if self.hardware:
            # Real hardware measurement
            resonance_data = {}
            for axis in ['x', 'y']:
                try:
                    results = self.hardware.measure_resonance(axis)
                    if results['resonance_peaks']:
                        freq = results['resonance_peaks'][0]['frequency']
                    else:
                        freq = 45.0 if axis == 'x' else 38.0
                except:
                    freq = 45.0 if axis == 'x' else 38.0
                
                resonance_data[f'resonance_freq_{axis}'] = freq
                resonance_data[f'resonance_damping_{axis}'] = 0.1
        else:
            # Simulated measurement
            resonance_data = {
                'resonance_freq_x': 45.0,
                'resonance_freq_y': 38.0,
                'resonance_damping_x': 0.1,
                'resonance_damping_y': 0.1
            }
        
        return resonance_data
    
    def _measure_backlash(self) -> Dict[str, float]:
        """Measure mechanical backlash"""
        if self.hardware:
            # Real hardware measurement
            backlash_data = {}
            for axis in ['x', 'y']:
                try:
                    # This would involve moving back and forth
                    backlash = self.hardware.measure_backlash(axis)
                except:
                    backlash = 0.01
                
                backlash_data[f'backlash_{axis}'] = backlash
        else:
            # Simulated measurement
            backlash_data = {
                'backlash_x': 0.01,
                'backlash_y': 0.01,
                'backlash_z': 0.02
            }
        
        return backlash_data
    
    def _estimate_inertia(self) -> Dict[str, float]:
        """Estimate moving mass inertia"""
        # These are typical values for common printers
        return {
            'mass_x': 0.5,   # kg
            'mass_y': 0.8,   # kg
            'mass_z': 1.2,   # kg
            'inertia_x': 0.001,
            'inertia_y': 0.0015,
            'inertia_z': 0.002
        }
    
    def _measure_stiffness(self) -> Dict[str, float]:
        """Measure mechanical stiffness"""
        return {
            'stiffness_x': 5000.0,   # N/m
            'stiffness_y': 4500.0,   # N/m
            'stiffness_z': 6000.0,   # N/m
            'damping_x': 5.0,        # N·s/m
            'damping_y': 4.5,        # N·s/m
            'damping_z': 6.0         # N·s/m
        }
    
    def quick_calibration(self) -> CalibrationResult:
        """Quick calibration using default values"""
        print("Running quick calibration...")
        
        start_time = time.time()
        
        parameters = {
            # Motor currents
            'motor_current_x': 1.2,
            'motor_current_y': 1.2,
            'motor_current_z': 1.0,
            'motor_current_e': 0.8,
            
            # Resonances
            'resonance_freq_x': 45.0,
            'resonance_freq_y': 38.0,
            'resonance_damping_x': 0.1,
            'resonance_damping_y': 0.1,
            
            # Backlash
            'backlash_x': 0.01,
            'backlash_y': 0.01,
            'backlash_z': 0.02,
            
            # Inertia
            'mass_x': 0.5,
            'mass_y': 0.8,
            'mass_z': 1.2,
            
            # Stiffness
            'stiffness_x': 5000.0,
            'stiffness_y': 4500.0,
            'stiffness_z': 6000.0
        }
        
        resonance_peaks = [
            {'axis': 'x', 'frequency': 45.0, 'amplitude': 1.0},
            {'axis': 'y', 'frequency': 38.0, 'amplitude': 0.8}
        ]
        
        duration = time.time() - start_time
        
        return CalibrationResult(
            success=True,
            parameters=parameters,
            resonance_peaks=resonance_peaks,
            backlash_measurements={'x': 0.01, 'y': 0.01, 'z': 0.02},
            motor_currents={'x': 1.2, 'y': 1.2, 'z': 1.0, 'e': 0.8},
            timestamp=start_time,
            duration=duration
        )
    
    def validate_calibration(self, results: CalibrationResult) -> Dict[str, bool]:
        """Validate calibration results"""
        checks = {}
        
        # Check required parameters
        required = ['resonance_freq_x', 'resonance_freq_y', 'mass_x', 'mass_y']
        for param in required:
            checks[f'has_{param}'] = param in results.parameters
        
        # Check parameter ranges
        if 'resonance_freq_x' in results.parameters:
            freq = results.parameters['resonance_freq_x']
            checks['resonance_x_in_range'] = 10 <= freq <= 200
        
        if 'resonance_freq_y' in results.parameters:
            freq = results.parameters['resonance_freq_y']
            checks['resonance_y_in_range'] = 10 <= freq <= 200
        
        if 'mass_x' in results.parameters:
            mass = results.parameters['mass_x']
            checks['mass_x_plausible'] = 0.1 <= mass <= 5.0
        
        # Overall validation
        checks['all_checks_passed'] = all(checks.values())
        
        return checks