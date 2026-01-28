#!/usr/bin/env python3
"""
OrbitEOS Grid Meter Simulator
Simulates a smart electricity meter at the grid connection point.

Features:
- 3-phase power measurement
- Import/export power tracking
- Voltage and frequency simulation
- Energy counters (import/export)
- Dynamic electricity pricing integration
- Power quality parameters
"""

import random
import math
import time
from datetime import datetime
from typing import Dict, Any, Optional


class GridSimulator:
    """
    Realistic smart grid meter simulator.
    Models a 3-phase grid connection point.
    """

    # Grid specifications (European standard)
    NOMINAL_VOLTAGE = 230.0           # Nominal phase voltage (V)
    NOMINAL_FREQUENCY = 50.0          # Nominal frequency (Hz)
    MAX_GRID_POWER_KW = 25.0          # Maximum grid connection (kW)

    # Voltage tolerances (EN 50160)
    VOLTAGE_MIN = 207.0               # -10% of nominal
    VOLTAGE_MAX = 253.0               # +10% of nominal
    VOLTAGE_VARIATION = 2.0           # Normal variation (V)

    # Frequency tolerances
    FREQUENCY_MIN = 49.5              # Minimum frequency (Hz)
    FREQUENCY_MAX = 50.5              # Maximum frequency (Hz)
    FREQUENCY_VARIATION = 0.02        # Normal variation (Hz)

    def __init__(
        self,
        max_power_kw: float = MAX_GRID_POWER_KW,
        initial_import_kwh: float = 0.0,
        initial_export_kwh: float = 0.0
    ):
        """
        Initialize grid meter simulator.

        Args:
            max_power_kw: Maximum grid connection power
            initial_import_kwh: Initial import energy counter
            initial_export_kwh: Initial export energy counter
        """
        self.max_power_kw = max_power_kw

        # Energy counters (persist across updates)
        self.import_energy_wh = initial_import_kwh * 1000
        self.export_energy_wh = initial_export_kwh * 1000

        # Current power state
        self.power_w = 0.0
        self.reactive_power_var = 0.0

        # 3-phase voltages
        self.voltage_l1 = self.NOMINAL_VOLTAGE
        self.voltage_l2 = self.NOMINAL_VOLTAGE
        self.voltage_l3 = self.NOMINAL_VOLTAGE

        # 3-phase currents
        self.current_l1 = 0.0
        self.current_l2 = 0.0
        self.current_l3 = 0.0

        # Frequency
        self.frequency = self.NOMINAL_FREQUENCY

        # Power factor
        self.power_factor = 0.95

        # Last update time
        self.last_update = time.time()

        # Electricity prices (EUR/kWh)
        self.import_price = 0.25      # Current import price
        self.export_price = 0.08      # Current export price (feed-in tariff)

    def _simulate_voltage(self) -> tuple:
        """
        Simulate realistic 3-phase voltages with variations.
        Returns (L1, L2, L3) voltages.
        """
        # Base voltage with time-of-day variation
        hour = datetime.now().hour

        # Voltage tends to be lower during peak demand (evening)
        if 17 <= hour <= 21:
            base_offset = -3.0  # Lower during peak
        elif 2 <= hour <= 6:
            base_offset = 2.0   # Higher at night
        else:
            base_offset = 0.0

        # Generate 3-phase voltages with slight imbalance
        l1 = self.NOMINAL_VOLTAGE + base_offset + random.uniform(-self.VOLTAGE_VARIATION, self.VOLTAGE_VARIATION)
        l2 = self.NOMINAL_VOLTAGE + base_offset + random.uniform(-self.VOLTAGE_VARIATION, self.VOLTAGE_VARIATION) - 0.5
        l3 = self.NOMINAL_VOLTAGE + base_offset + random.uniform(-self.VOLTAGE_VARIATION, self.VOLTAGE_VARIATION) + 0.3

        # Clamp to valid range
        l1 = max(self.VOLTAGE_MIN, min(self.VOLTAGE_MAX, l1))
        l2 = max(self.VOLTAGE_MIN, min(self.VOLTAGE_MAX, l2))
        l3 = max(self.VOLTAGE_MIN, min(self.VOLTAGE_MAX, l3))

        return (round(l1, 1), round(l2, 1), round(l3, 1))

    def _simulate_frequency(self) -> float:
        """
        Simulate grid frequency.
        Real grids have very tight frequency control.
        """
        # Small random variation around 50 Hz
        variation = random.gauss(0, self.FREQUENCY_VARIATION)
        frequency = self.NOMINAL_FREQUENCY + variation

        # Clamp to valid range
        return max(self.FREQUENCY_MIN, min(self.FREQUENCY_MAX, round(frequency, 3)))

    def _calculate_currents(self, power_w: float) -> tuple:
        """
        Calculate 3-phase currents from power.
        Assumes balanced load for simplicity.
        """
        # 3-phase power formula: P = sqrt(3) * V_line * I * cos(phi)
        # For single-phase per conductor: P_phase = V_phase * I * cos(phi)

        avg_voltage = (self.voltage_l1 + self.voltage_l2 + self.voltage_l3) / 3
        power_per_phase = power_w / 3

        # Current per phase
        current_per_phase = abs(power_per_phase) / (avg_voltage * self.power_factor) if avg_voltage > 0 else 0

        # Add slight imbalance between phases
        i1 = current_per_phase * random.uniform(0.98, 1.02)
        i2 = current_per_phase * random.uniform(0.97, 1.01)
        i3 = current_per_phase * random.uniform(0.99, 1.03)

        return (round(i1, 2), round(i2, 2), round(i3, 2))

    def _calculate_reactive_power(self, active_power_w: float) -> float:
        """
        Calculate reactive power based on power factor.
        Q = P * tan(arccos(pf))
        """
        if self.power_factor >= 1.0:
            return 0.0

        tan_phi = math.sqrt(1 - self.power_factor ** 2) / self.power_factor
        reactive_power = abs(active_power_w) * tan_phi

        # Reactive power is typically lagging (inductive) for imports
        if active_power_w > 0:
            return round(reactive_power, 1)
        else:
            return round(-reactive_power, 1)

    def update(self, net_power_w: float) -> Dict[str, Any]:
        """
        Update grid meter with net power flow.

        Args:
            net_power_w: Net power at grid connection point
                        Positive = importing from grid
                        Negative = exporting to grid

        Returns:
            Dictionary with current grid status
        """
        # Limit to grid connection capacity
        max_power_w = self.max_power_kw * 1000
        self.power_w = max(-max_power_w, min(max_power_w, net_power_w))

        # Calculate time delta for energy accumulation
        current_time = time.time()
        dt_hours = (current_time - self.last_update) / 3600.0
        self.last_update = current_time

        # Update energy counters
        energy_wh = abs(self.power_w) * dt_hours
        if self.power_w > 0:
            self.import_energy_wh += energy_wh
        else:
            self.export_energy_wh += energy_wh

        # Simulate voltages
        self.voltage_l1, self.voltage_l2, self.voltage_l3 = self._simulate_voltage()

        # Simulate frequency
        self.frequency = self._simulate_frequency()

        # Calculate currents
        self.current_l1, self.current_l2, self.current_l3 = self._calculate_currents(self.power_w)

        # Calculate reactive power
        self.reactive_power_var = self._calculate_reactive_power(self.power_w)

        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        """Get current grid meter status."""
        # Determine grid mode
        if self.power_w > 50:
            mode = "importing"
        elif self.power_w < -50:
            mode = "exporting"
        else:
            mode = "balanced"

        return {
            'power_w': round(self.power_w, 1),
            'reactive_power_var': self.reactive_power_var,
            'voltage_l1': self.voltage_l1,
            'voltage_l2': self.voltage_l2,
            'voltage_l3': self.voltage_l3,
            'voltage_avg': round((self.voltage_l1 + self.voltage_l2 + self.voltage_l3) / 3, 1),
            'current_l1': self.current_l1,
            'current_l2': self.current_l2,
            'current_l3': self.current_l3,
            'current_total': round(self.current_l1 + self.current_l2 + self.current_l3, 2),
            'frequency': self.frequency,
            'power_factor': self.power_factor,
            'import_energy_wh': round(self.import_energy_wh, 1),
            'export_energy_wh': round(self.export_energy_wh, 1),
            'import_energy_kwh': round(self.import_energy_wh / 1000, 3),
            'export_energy_kwh': round(self.export_energy_wh / 1000, 3),
            'mode': mode,
            'import_price_eur_kwh': self.import_price,
            'export_price_eur_kwh': self.export_price,
            'max_power_kw': self.max_power_kw
        }

    def set_prices(self, import_price: float, export_price: float):
        """
        Set electricity prices.

        Args:
            import_price: Price for imported electricity (EUR/kWh)
            export_price: Price for exported electricity (EUR/kWh)
        """
        self.import_price = import_price
        self.export_price = export_price

    def get_daily_cost(self) -> Dict[str, float]:
        """
        Calculate daily electricity cost based on energy counters.
        Note: This is a simplified calculation.
        """
        import_cost = (self.import_energy_wh / 1000) * self.import_price
        export_revenue = (self.export_energy_wh / 1000) * self.export_price
        net_cost = import_cost - export_revenue

        return {
            'import_cost_eur': round(import_cost, 2),
            'export_revenue_eur': round(export_revenue, 2),
            'net_cost_eur': round(net_cost, 2)
        }

    def reset_energy_counters(self):
        """Reset energy counters (e.g., for daily reset)."""
        self.import_energy_wh = 0.0
        self.export_energy_wh = 0.0


# Example usage
if __name__ == "__main__":
    # Create grid meter
    grid = GridSimulator(max_power_kw=25.0)

    print("Grid Meter Simulator")
    print("=" * 50)

    # Simulate importing power
    print("\nImporting 3000W from grid:")
    for i in range(5):
        status = grid.update(3000)
        print(f"  t={i+1}s: Power={status['power_w']}W, Mode={status['mode']}, "
              f"V_L1={status['voltage_l1']}V, f={status['frequency']}Hz")

    # Simulate exporting power
    print("\nExporting 2000W to grid:")
    for i in range(5):
        status = grid.update(-2000)
        print(f"  t={i+1}s: Power={status['power_w']}W, Mode={status['mode']}, "
              f"V_L1={status['voltage_l1']}V, f={status['frequency']}Hz")

    # Print final status
    print("\nFinal Status:")
    status = grid.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")

    # Print daily cost
    print("\nDaily Cost:")
    cost = grid.get_daily_cost()
    for key, value in cost.items():
        print(f"  {key}: {value}")
