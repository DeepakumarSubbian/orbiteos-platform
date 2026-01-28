#!/usr/bin/env python3
"""
OrbitEOS EV Charger Simulator
Simulates an 11kW EV charging station with OCPP-style status.

Features:
- 11 kW (16A 3-phase) charging power
- Vehicle SOC tracking
- Arrival/departure scheduling
- OCPP-compatible status codes
- Smart charging support (power modulation)
- Session energy tracking
"""

import random
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from enum import IntEnum


class ChargerStatus(IntEnum):
    """OCPP-style charger status codes."""
    AVAILABLE = 0          # Ready to charge
    PREPARING = 1          # Vehicle connected, preparing
    CHARGING = 2           # Actively charging
    SUSPENDED_EV = 3       # Paused by vehicle
    SUSPENDED_EVSE = 4     # Paused by charger
    FINISHING = 5          # Charging complete
    RESERVED = 6           # Reserved for scheduled session
    UNAVAILABLE = 7        # Out of service
    FAULTED = 8            # Error state


class EVChargerSimulator:
    """
    Realistic EV charger simulator.
    Models an 11kW home/workplace charging station.
    """

    # Default specifications
    DEFAULT_MAX_POWER_KW = 11.0       # 11kW (16A 3-phase)
    DEFAULT_VOLTAGE = 400.0           # 3-phase line voltage
    DEFAULT_MAX_CURRENT = 16.0        # Max current per phase (A)
    MIN_CURRENT = 6.0                 # Minimum charging current (A)

    # Default vehicle specifications
    DEFAULT_VEHICLE_CAPACITY_KWH = 60.0   # Typical EV battery
    DEFAULT_VEHICLE_SOC = 30.0            # Starting SOC when arriving
    TARGET_SOC = 80.0                     # Default charge target

    # Charging efficiency
    CHARGING_EFFICIENCY = 0.92            # ~92% AC charging efficiency

    def __init__(
        self,
        max_power_kw: float = DEFAULT_MAX_POWER_KW,
        vehicle_capacity_kwh: float = DEFAULT_VEHICLE_CAPACITY_KWH,
        arrival_hour: int = 18,           # Default: arrive at 18:00
        departure_hour: int = 7           # Default: leave at 07:00
    ):
        """
        Initialize EV charger simulator.

        Args:
            max_power_kw: Maximum charging power in kW
            vehicle_capacity_kwh: Vehicle battery capacity in kWh
            arrival_hour: Hour of day when vehicle arrives
            departure_hour: Hour of day when vehicle departs
        """
        self.max_power_kw = max_power_kw
        self.vehicle_capacity_kwh = vehicle_capacity_kwh
        self.arrival_hour = arrival_hour
        self.departure_hour = departure_hour

        # Calculate max current from power
        self.max_current = (max_power_kw * 1000) / (self.DEFAULT_VOLTAGE * 1.732)  # sqrt(3)
        self.current_limit = self.max_current  # Can be reduced for smart charging

        # Charger state
        self.status = ChargerStatus.AVAILABLE
        self.power_w = 0.0
        self.session_energy_wh = 0.0
        self.total_energy_wh = 0.0

        # Vehicle state
        self.vehicle_connected = False
        self.vehicle_soc = 0.0
        self.vehicle_target_soc = self.TARGET_SOC

        # Session tracking
        self.session_start = None
        self.last_update = time.time()

        # Scheduled arrival/departure
        self._schedule_vehicle()

    def _schedule_vehicle(self):
        """Schedule vehicle arrival based on time of day."""
        now = datetime.now()
        current_hour = now.hour

        # Determine if vehicle should be connected
        if self.arrival_hour < self.departure_hour:
            # Simple case: arrival before departure (e.g., 10:00-14:00)
            self.vehicle_connected = self.arrival_hour <= current_hour < self.departure_hour
        else:
            # Overnight case: arrival after departure (e.g., 18:00-07:00)
            self.vehicle_connected = current_hour >= self.arrival_hour or current_hour < self.departure_hour

        if self.vehicle_connected:
            # Simulate vehicle arriving with random SOC
            self.vehicle_soc = random.uniform(20, 50)
            self.status = ChargerStatus.CHARGING
            self.session_start = now
        else:
            self.vehicle_soc = 0.0
            self.status = ChargerStatus.AVAILABLE

    def connect_vehicle(self, initial_soc: float = None, target_soc: float = None):
        """
        Connect a vehicle to the charger.

        Args:
            initial_soc: Initial vehicle SOC (0-100%)
            target_soc: Target SOC to charge to
        """
        if initial_soc is None:
            initial_soc = random.uniform(20, 50)

        self.vehicle_connected = True
        self.vehicle_soc = min(100, max(0, initial_soc))
        self.vehicle_target_soc = target_soc or self.TARGET_SOC
        self.status = ChargerStatus.PREPARING
        self.session_energy_wh = 0.0
        self.session_start = datetime.now()

        # Transition to charging after brief preparation
        self.status = ChargerStatus.CHARGING

    def disconnect_vehicle(self):
        """Disconnect vehicle from charger."""
        self.vehicle_connected = False
        self.vehicle_soc = 0.0
        self.power_w = 0.0
        self.status = ChargerStatus.AVAILABLE
        self.session_start = None

    def set_current_limit(self, current_a: float):
        """
        Set charging current limit (for smart charging).

        Args:
            current_a: Maximum current in Amps
        """
        self.current_limit = max(self.MIN_CURRENT, min(self.max_current, current_a))

    def pause_charging(self):
        """Pause charging (EVSE-initiated)."""
        if self.status == ChargerStatus.CHARGING:
            self.status = ChargerStatus.SUSPENDED_EVSE
            self.power_w = 0.0

    def resume_charging(self):
        """Resume charging after pause."""
        if self.status in [ChargerStatus.SUSPENDED_EVSE, ChargerStatus.SUSPENDED_EV]:
            if self.vehicle_soc < self.vehicle_target_soc:
                self.status = ChargerStatus.CHARGING

    def _calculate_charging_power(self) -> float:
        """
        Calculate current charging power based on conditions.
        """
        if not self.vehicle_connected:
            return 0.0

        if self.status != ChargerStatus.CHARGING:
            return 0.0

        if self.vehicle_soc >= self.vehicle_target_soc:
            return 0.0

        # Base power from current limit
        power_kw = (self.current_limit * self.DEFAULT_VOLTAGE * 1.732) / 1000

        # Apply SOC-based tapering (CC-CV charging curve)
        if self.vehicle_soc > 80:
            # Taper charging above 80% SOC
            taper_factor = (100 - self.vehicle_soc) / 20
            power_kw *= max(0.1, taper_factor)
        elif self.vehicle_soc > 90:
            # Very slow above 90%
            power_kw *= 0.2

        # Cap at max power
        power_kw = min(power_kw, self.max_power_kw)

        # Add small variation
        power_kw *= random.uniform(0.98, 1.02)

        return power_kw * 1000  # Return in watts

    def update(self) -> Dict[str, Any]:
        """
        Update charger state.

        Returns:
            Dictionary with current charger status
        """
        current_time = time.time()
        dt_hours = (current_time - self.last_update) / 3600.0
        self.last_update = current_time

        # Check scheduled arrival/departure
        now = datetime.now()
        current_hour = now.hour

        # Handle vehicle arrival/departure based on schedule
        if not self.vehicle_connected:
            # Check if vehicle should arrive
            if self.arrival_hour < self.departure_hour:
                should_connect = self.arrival_hour <= current_hour < self.departure_hour
            else:
                should_connect = current_hour >= self.arrival_hour or current_hour < self.departure_hour

            if should_connect:
                self.connect_vehicle()
        else:
            # Check if vehicle should depart
            if self.arrival_hour < self.departure_hour:
                should_disconnect = current_hour >= self.departure_hour
            else:
                should_disconnect = self.departure_hour <= current_hour < self.arrival_hour

            if should_disconnect:
                self.disconnect_vehicle()

        # Calculate charging power
        self.power_w = self._calculate_charging_power()

        # Update vehicle SOC
        if self.power_w > 0:
            energy_wh = self.power_w * dt_hours * self.CHARGING_EFFICIENCY
            soc_increase = (energy_wh / (self.vehicle_capacity_kwh * 1000)) * 100
            self.vehicle_soc = min(100, self.vehicle_soc + soc_increase)

            # Update session energy
            self.session_energy_wh += self.power_w * dt_hours
            self.total_energy_wh += self.power_w * dt_hours

            # Check if charging complete
            if self.vehicle_soc >= self.vehicle_target_soc:
                self.status = ChargerStatus.FINISHING
                self.power_w = 0.0

        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        """Get current charger status."""
        # Calculate session duration
        if self.session_start:
            session_duration = datetime.now() - self.session_start
            session_minutes = session_duration.total_seconds() / 60
        else:
            session_minutes = 0

        # Estimate time to target
        if self.power_w > 0 and self.vehicle_soc < self.vehicle_target_soc:
            energy_needed_wh = ((self.vehicle_target_soc - self.vehicle_soc) / 100) * self.vehicle_capacity_kwh * 1000
            hours_to_target = energy_needed_wh / self.power_w
        else:
            hours_to_target = 0

        return {
            'status': self._status_string(),
            'status_code': int(self.status),
            'power_w': round(self.power_w, 1),
            'power_kw': round(self.power_w / 1000, 3),
            'max_power_w': self.max_power_kw * 1000,
            'current_limit_a': round(self.current_limit, 1),
            'vehicle_connected': self.vehicle_connected,
            'vehicle_soc': round(self.vehicle_soc, 1),
            'vehicle_target_soc': self.vehicle_target_soc,
            'session_energy_wh': round(self.session_energy_wh, 1),
            'session_energy_kwh': round(self.session_energy_wh / 1000, 3),
            'session_duration_min': round(session_minutes, 1),
            'hours_to_target': round(hours_to_target, 2),
            'total_energy_kwh': round(self.total_energy_wh / 1000, 2),
            'arrival_hour': self.arrival_hour,
            'departure_hour': self.departure_hour
        }

    def _status_string(self) -> str:
        """Get human-readable status."""
        status_map = {
            ChargerStatus.AVAILABLE: "available",
            ChargerStatus.PREPARING: "preparing",
            ChargerStatus.CHARGING: "charging",
            ChargerStatus.SUSPENDED_EV: "suspended_ev",
            ChargerStatus.SUSPENDED_EVSE: "suspended_evse",
            ChargerStatus.FINISHING: "finished",
            ChargerStatus.RESERVED: "reserved",
            ChargerStatus.UNAVAILABLE: "unavailable",
            ChargerStatus.FAULTED: "faulted"
        }
        return status_map.get(self.status, "unknown")


# Example usage
if __name__ == "__main__":
    # Create EV charger
    charger = EVChargerSimulator(
        max_power_kw=11.0,
        vehicle_capacity_kwh=60.0,
        arrival_hour=18,
        departure_hour=7
    )

    print("EV Charger Simulator")
    print("=" * 50)

    # Connect a vehicle manually
    charger.connect_vehicle(initial_soc=30, target_soc=80)

    # Simulate charging for 10 iterations
    print("\nCharging session:")
    for i in range(10):
        status = charger.update()
        print(f"  t={i+1}: SOC={status['vehicle_soc']}%, Power={status['power_kw']:.2f}kW, "
              f"Status={status['status']}, Session={status['session_energy_kwh']:.2f}kWh")
        time.sleep(0.1)

    # Smart charging: reduce current
    print("\nApplying smart charging (8A limit):")
    charger.set_current_limit(8.0)
    for i in range(5):
        status = charger.update()
        print(f"  t={i+1}: SOC={status['vehicle_soc']}%, Power={status['power_kw']:.2f}kW, "
              f"Current limit={status['current_limit_a']}A")
        time.sleep(0.1)

    # Print final status
    print("\nFinal Status:")
    status = charger.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
