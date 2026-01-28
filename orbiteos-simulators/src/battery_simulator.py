#!/usr/bin/env python3
"""
OrbitEOS Battery Simulator
Tesla Powerwall 2 style battery energy storage simulation.

Features:
- 13.5 kWh usable capacity
- 5 kW continuous power (7 kW peak)
- Accurate SOC tracking
- Charge/discharge curves with efficiency losses
- Temperature-dependent performance
- Round-trip efficiency ~90%
"""

import random
import math
from datetime import datetime
from typing import Dict, Any


class BatterySimulator:
    """
    Realistic battery energy storage simulator.
    Models Tesla Powerwall 2 characteristics.
    """

    # Tesla Powerwall 2 specifications
    DEFAULT_CAPACITY_KWH = 13.5       # Usable capacity
    DEFAULT_MAX_POWER_KW = 5.0        # Continuous power
    PEAK_POWER_KW = 7.0               # Peak power (short duration)
    NOMINAL_VOLTAGE = 50.0            # Nominal battery voltage
    MIN_VOLTAGE = 42.0                # Minimum voltage at 0% SOC
    MAX_VOLTAGE = 57.6                # Maximum voltage at 100% SOC

    # Efficiency parameters
    CHARGE_EFFICIENCY = 0.95          # Charging efficiency
    DISCHARGE_EFFICIENCY = 0.95       # Discharging efficiency
    ROUND_TRIP_EFFICIENCY = 0.90      # Overall round-trip efficiency

    # SOC limits
    MIN_SOC = 5.0                     # Minimum SOC (reserve)
    MAX_SOC = 100.0                   # Maximum SOC
    LOW_SOC_THRESHOLD = 20.0          # Low battery threshold

    # Temperature parameters
    OPTIMAL_TEMP_MIN = 15.0           # Optimal operating temperature min
    OPTIMAL_TEMP_MAX = 25.0           # Optimal operating temperature max
    AMBIENT_TEMP = 20.0               # Default ambient temperature

    def __init__(
        self,
        capacity_kwh: float = DEFAULT_CAPACITY_KWH,
        max_power_kw: float = DEFAULT_MAX_POWER_KW,
        initial_soc: float = 50.0,
        min_soc: float = MIN_SOC,
        max_soc: float = MAX_SOC
    ):
        """
        Initialize battery simulator.

        Args:
            capacity_kwh: Usable battery capacity in kWh
            max_power_kw: Maximum continuous power in kW
            initial_soc: Initial state of charge (0-100%)
            min_soc: Minimum allowed SOC (reserve)
            max_soc: Maximum allowed SOC
        """
        self.capacity_kwh = capacity_kwh
        self.max_power_kw = max_power_kw
        self.soc = max(min_soc, min(max_soc, initial_soc))
        self.min_soc = min_soc
        self.max_soc = max_soc

        # Current state
        self.power_kw = 0.0           # Current power (positive=discharge)
        self.voltage = self._calculate_voltage()
        self.current = 0.0            # Current in amps
        self.temperature = self.AMBIENT_TEMP

        # Energy counters
        self.total_charged_kwh = 0.0
        self.total_discharged_kwh = 0.0
        self.cycle_count = 0.0

        # State
        self.is_charging = False
        self.is_discharging = False

    def _calculate_voltage(self) -> float:
        """
        Calculate battery voltage based on SOC.
        Uses simplified linear model.
        """
        # Linear interpolation between min and max voltage
        voltage_range = self.MAX_VOLTAGE - self.MIN_VOLTAGE
        voltage = self.MIN_VOLTAGE + (self.soc / 100.0) * voltage_range

        # Add small random variation (±0.5%)
        variation = random.uniform(0.995, 1.005)
        return round(voltage * variation, 2)

    def _calculate_temperature(self, power_kw: float, dt_seconds: float) -> float:
        """
        Simulate battery temperature based on power flow.
        Higher power = more heat generated.
        """
        # Heat generation from power flow
        heat_factor = abs(power_kw) / self.max_power_kw
        heat_generation = heat_factor * 0.5  # Max 0.5°C rise per second at full power

        # Cooling towards ambient
        temp_diff = self.temperature - self.AMBIENT_TEMP
        cooling = temp_diff * 0.01  # 1% cooling per second

        # Update temperature
        new_temp = self.temperature + (heat_generation - cooling) * (dt_seconds / 60.0)

        # Clamp to reasonable range
        return max(5.0, min(45.0, new_temp))

    def _get_efficiency(self, is_charging: bool) -> float:
        """
        Get charge/discharge efficiency based on temperature and SOC.
        """
        base_efficiency = self.CHARGE_EFFICIENCY if is_charging else self.DISCHARGE_EFFICIENCY

        # Temperature derating
        if self.temperature < self.OPTIMAL_TEMP_MIN:
            # Cold reduces efficiency
            temp_factor = 1.0 - (self.OPTIMAL_TEMP_MIN - self.temperature) * 0.005
        elif self.temperature > self.OPTIMAL_TEMP_MAX:
            # Hot reduces efficiency
            temp_factor = 1.0 - (self.temperature - self.OPTIMAL_TEMP_MAX) * 0.003
        else:
            temp_factor = 1.0

        # SOC-based efficiency (less efficient at extremes)
        if is_charging and self.soc > 90:
            soc_factor = 1.0 - (self.soc - 90) * 0.01
        elif not is_charging and self.soc < 20:
            soc_factor = 1.0 - (20 - self.soc) * 0.01
        else:
            soc_factor = 1.0

        return base_efficiency * temp_factor * soc_factor

    def _get_power_limit(self, is_charging: bool) -> float:
        """
        Get maximum allowed power based on current conditions.
        """
        # Base power limit
        max_power = self.max_power_kw

        # SOC-based derating
        if is_charging:
            # Reduce charge power at high SOC (CV phase simulation)
            if self.soc > 90:
                max_power *= (100 - self.soc) / 10.0
            elif self.soc > 95:
                max_power *= 0.2
        else:
            # Reduce discharge power at low SOC
            if self.soc < 15:
                max_power *= self.soc / 15.0
            elif self.soc < 10:
                max_power *= 0.2

        # Temperature derating
        if self.temperature > 40:
            max_power *= 0.5
        elif self.temperature > 35:
            max_power *= 0.8
        elif self.temperature < 5:
            max_power *= 0.3
        elif self.temperature < 10:
            max_power *= 0.7

        return max_power

    def update(self, requested_power_kw: float, dt_seconds: float = 1.0) -> Dict[str, Any]:
        """
        Update battery state based on requested power.

        Args:
            requested_power_kw: Requested power in kW
                               Positive = discharge (battery -> load)
                               Negative = charge (solar -> battery)
            dt_seconds: Time step in seconds

        Returns:
            Dictionary with current battery status
        """
        # Determine charging or discharging
        is_charging = requested_power_kw < 0

        # Get power limits
        max_charge_power = self._get_power_limit(True)
        max_discharge_power = self._get_power_limit(False)

        # Constrain power to limits
        if is_charging:
            # Charging (negative power)
            if self.soc >= self.max_soc:
                actual_power = 0.0  # Battery full
            else:
                actual_power = max(-max_charge_power, requested_power_kw)
        else:
            # Discharging (positive power)
            if self.soc <= self.min_soc:
                actual_power = 0.0  # Battery empty
            else:
                actual_power = min(max_discharge_power, requested_power_kw)

        # Calculate energy change
        efficiency = self._get_efficiency(is_charging)
        dt_hours = dt_seconds / 3600.0

        if is_charging:
            # Charging: energy stored is less than energy input due to losses
            energy_change_kwh = abs(actual_power) * dt_hours * efficiency
            self.soc += (energy_change_kwh / self.capacity_kwh) * 100
            self.total_charged_kwh += energy_change_kwh
        else:
            # Discharging: energy output is less than energy extracted due to losses
            energy_change_kwh = actual_power * dt_hours / efficiency
            self.soc -= (energy_change_kwh / self.capacity_kwh) * 100
            self.total_discharged_kwh += actual_power * dt_hours

        # Clamp SOC
        self.soc = max(self.min_soc, min(self.max_soc, self.soc))

        # Update cycle count (rough estimate)
        if abs(actual_power) > 0.1:
            self.cycle_count += abs(actual_power) * dt_hours / (2 * self.capacity_kwh)

        # Update voltage, current, temperature
        self.voltage = self._calculate_voltage()
        self.current = (actual_power * 1000) / self.voltage if self.voltage > 0 else 0
        self.temperature = self._calculate_temperature(actual_power, dt_seconds)

        # Store current state
        self.power_kw = actual_power
        self.is_charging = is_charging and actual_power != 0
        self.is_discharging = not is_charging and actual_power != 0

        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        """Get current battery status."""
        # Calculate remaining energy
        usable_soc = max(0, self.soc - self.min_soc)
        remaining_kwh = (usable_soc / 100.0) * self.capacity_kwh

        # Estimate time remaining at current power
        if self.is_discharging and self.power_kw > 0:
            hours_remaining = remaining_kwh / self.power_kw
        elif self.is_charging and self.power_kw < 0:
            energy_to_full = ((self.max_soc - self.soc) / 100.0) * self.capacity_kwh
            hours_remaining = energy_to_full / abs(self.power_kw) if self.power_kw != 0 else 0
        else:
            hours_remaining = 0

        return {
            'soc': round(self.soc, 1),
            'power_kw': round(self.power_kw, 3),
            'voltage': round(self.voltage, 2),
            'current': round(self.current, 2),
            'temperature': round(self.temperature, 1),
            'capacity_kwh': self.capacity_kwh,
            'remaining_kwh': round(remaining_kwh, 2),
            'hours_remaining': round(hours_remaining, 2),
            'is_charging': self.is_charging,
            'is_discharging': self.is_discharging,
            'max_charge_power_kw': self._get_power_limit(True),
            'max_discharge_power_kw': self._get_power_limit(False),
            'total_charged_kwh': round(self.total_charged_kwh, 2),
            'total_discharged_kwh': round(self.total_discharged_kwh, 2),
            'cycle_count': round(self.cycle_count, 1),
            'health': self._calculate_health(),
            'state': self._get_state_string()
        }

    def _calculate_health(self) -> float:
        """Calculate battery health based on cycle count."""
        # Assume 5000 cycles for 80% health
        degradation = self.cycle_count / 5000.0 * 20
        return max(80.0, 100.0 - degradation)

    def _get_state_string(self) -> str:
        """Get human-readable state."""
        if self.is_charging:
            return "charging"
        elif self.is_discharging:
            return "discharging"
        elif self.soc >= self.max_soc:
            return "full"
        elif self.soc <= self.min_soc:
            return "empty"
        else:
            return "standby"

    def set_soc(self, soc: float):
        """Manually set SOC (for testing)."""
        self.soc = max(self.min_soc, min(self.max_soc, soc))
        self.voltage = self._calculate_voltage()


# Example usage
if __name__ == "__main__":
    # Create a Tesla Powerwall 2 style battery
    battery = BatterySimulator(
        capacity_kwh=13.5,
        max_power_kw=5.0,
        initial_soc=50.0
    )

    print("Battery Simulator - Tesla Powerwall 2")
    print("=" * 50)

    # Simulate charging for 10 seconds
    print("\nCharging at 3 kW:")
    for i in range(10):
        status = battery.update(requested_power_kw=-3.0, dt_seconds=1.0)
        print(f"  t={i+1}s: SOC={status['soc']}%, Power={status['power_kw']}kW, State={status['state']}")

    # Simulate discharging for 10 seconds
    print("\nDischarging at 2 kW:")
    for i in range(10):
        status = battery.update(requested_power_kw=2.0, dt_seconds=1.0)
        print(f"  t={i+1}s: SOC={status['soc']}%, Power={status['power_kw']}kW, State={status['state']}")

    # Print final status
    print("\nFinal Status:")
    status = battery.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
