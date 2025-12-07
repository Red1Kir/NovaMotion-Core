"""
Hardware manager for coordinating multiple hardware interfaces
"""

import threading
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from .tmc2209_driver import TMC2209Driver, TMC2209Config

@dataclass
class HardwareStatus:
    """Current status of hardware system"""
    connected: bool
    drivers: Dict[str, bool]
    sensors: Dict[str, bool]
    temperatures: Dict[str, float]
    errors: List[str]
    timestamp: float

class HardwareManager:
    """Manager for all hardware interfaces"""
    
    def __init__(self):
        self.drivers = {}
        self.sensors = {}
        self.status = HardwareStatus(
            connected=False,
            drivers={},
            sensors={},
            temperatures={},
            errors=[],
            timestamp=time.time()
        )
        self.lock = threading.RLock()
        self.monitor_thread = None
        self.running = False
        
    def add_driver(self, name: str, port: str, config: Optional[TMC2209Config] = None) -> bool:
        """Add a TMC2209 driver"""
        with self.lock:
            driver = TMC2209Driver(port)
            
            if config is None:
                config = TMC2209Config()
            
            if driver.connect():
                if driver.setup_driver(config):
                    self.drivers[name] = driver
                    self.status.drivers[name] = True
                    print(f"✅ Driver {name} connected on {port}")
                    return True
                else:
                    print(f"❌ Failed to setup driver {name}")
                    driver.disconnect()
            else:
                print(f"❌ Failed to connect to driver {name} on {port}")
        
        return False
    
    def remove_driver(self, name: str):
        """Remove a driver"""
        with self.lock:
            if name in self.drivers:
                self.drivers[name].disconnect()
                del self.drivers[name]
                if name in self.status.drivers:
                    del self.status.drivers[name]
                print(f"Driver {name} removed")
    
    def get_driver(self, name: str) -> Optional[TMC2209Driver]:
        """Get driver by name"""
        return self.drivers.get(name)
    
    def get_all_driver_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status for all drivers"""
        status = {}
        with self.lock:
            for name, driver in self.drivers.items():
                try:
                    drv_status = driver.read_drv_status()
                    status[name] = {
                        'connected': True,
                        'status': drv_status,
                        'stallguard': drv_status.get('stallguard', 0),
                        'cs_actual': drv_status.get('cs_actual', 0),
                        'standstill': drv_status.get('stst', 0) == 1
                    }
                except Exception as e:
                    status[name] = {
                        'connected': False,
                        'error': str(e)
                    }
        
        return status
    
    def measure_all_resonances(self) -> Dict[str, Dict]:
        """Measure resonances for all axes"""
        results = {}
        
        # Map driver names to axes (simplified)
        axis_map = {
            'x': 'x_driver',
            'y': 'y_driver',
            'z': 'z_driver'
        }
        
        for axis, driver_name in axis_map.items():
            if driver_name in self.drivers:
                driver = self.drivers[driver_name]
                try:
                    print(f"Measuring resonance for {axis}-axis...")
                    results[axis] = driver.measure_resonance(
                        axis=axis,
                        frequency_range=(20, 100),
                        steps=15
                    )
                    print(f"  Found {len(results[axis].get('resonance_peaks', []))} peaks")
                except Exception as e:
                    print(f"  Failed to measure {axis} resonance: {e}")
                    results[axis] = {'error': str(e)}
            else:
                print(f"  No driver found for {axis}-axis")
        
        return results
    
    def auto_tune_all_currents(self, target_temp: float = 50.0) -> Dict[str, float]:
        """Auto-tune currents for all drivers"""
        currents = {}
        
        for name, driver in self.drivers.items():
            try:
                print(f"Auto-tuning current for {name}...")
                optimal_current = driver.auto_tune_current(target_temp)
                currents[name] = optimal_current
                
                # Update driver config
                driver.config.current = optimal_current
                driver.setup_driver(driver.config)
                
                print(f"  Optimal current: {optimal_current:.2f}A")
            except Exception as e:
                print(f"  Failed to tune {name}: {e}")
                currents[name] = driver.config.current
        
        return currents
    
    def start_monitoring(self, interval: float = 1.0):
        """Start background monitoring"""
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            self.running = True
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop,
                args=(interval,),
                daemon=True
            )
            self.monitor_thread.start()
            print("Hardware monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
            self.monitor_thread = None
            print("Hardware monitoring stopped")
    
    def _monitor_loop(self, interval: float):
        """Background monitoring loop"""
        while self.running:
            try:
                with self.lock:
                    # Update driver status
                    for name, driver in self.drivers.items():
                        try:
                            status = driver.read_drv_status()
                            self.status.drivers[name] = True
                            
                            # Check for errors
                            if status.get('ot', 0) == 1:
                                self.status.errors.append(f"{name}: Overtemperature")
                            if status.get('ola', 0) == 1 or status.get('olb', 0) == 1:
                                self.status.errors.append(f"{name}: Open load detected")
                            
                        except Exception as e:
                            self.status.drivers[name] = False
                            self.status.errors.append(f"{name}: Connection error - {str(e)}")
                    
                    # Update overall status
                    self.status.connected = any(self.status.drivers.values())
                    self.status.timestamp = time.time()
                    
                    # Clear old errors
                    if len(self.status.errors) > 10:
                        self.status.errors = self.status.errors[-10:]
                
                time.sleep(interval)
                
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(interval)
    
    def get_status(self) -> HardwareStatus:
        """Get current hardware status"""
        with self.lock:
            return HardwareStatus(
                connected=self.status.connected,
                drivers=self.status.drivers.copy(),
                sensors=self.status.sensors.copy(),
                temperatures=self.status.temperatures.copy(),
                errors=self.status.errors.copy(),
                timestamp=self.status.timestamp
            )
    
    def emergency_stop(self):
        """Emergency stop all drivers"""
        print("🛑 EMERGENCY STOP triggered")
        with self.lock:
            for name, driver in self.drivers.items():
                try:
                    # Disable driver
                    driver.write_register(driver.REG_GCONF, 0)
                    print(f"  {name}: Driver disabled")
                except:
                    pass
    
    def cleanup(self):
        """Cleanup all resources"""
        self.stop_monitoring()
        with self.lock:
            for name in list(self.drivers.keys()):
                self.remove_driver(name)
        
        print("Hardware manager cleaned up")