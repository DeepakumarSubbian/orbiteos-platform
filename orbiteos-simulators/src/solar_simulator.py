"""
OrbitEOS Solar Simulator
Realistic solar PV production simulation with sun trajectory following
"""

import math
from datetime import datetime
import pytz
import random


class SolarSimulator:
    """
    Realistic solar PV production simulator
    Follows actual sun trajectory based on location
    """
    
    def __init__(self,
                 latitude: float,
                 longitude: float,
                 peak_power_kw: float = 6.0,
                 panels: int = 20,
                 efficiency: float = 0.85,
                 timezone: str = "Europe/Amsterdam"):
        """
        Initialize solar simulator
        
        Args:
            latitude: Location latitude in degrees
            longitude: Location longitude in degrees
            peak_power_kw: Peak power rating in kW
            panels: Number of solar panels
            efficiency: System efficiency (inverter + wiring losses)
            timezone: Timezone string
        """
        self.latitude = latitude
        self.longitude = longitude
        self.peak_power = peak_power_kw
        self.panels = panels
        self.efficiency = efficiency
        self.timezone = pytz.timezone(timezone)
        
    def calculate_solar_elevation(self, timestamp: datetime) -> float:
        """
        Calculate sun elevation angle in degrees
        
        Args:
            timestamp: Current datetime
            
        Returns:
            Sun elevation angle in degrees (0 = horizon, 90 = zenith)
        """
        # Ensure timestamp is timezone-aware
        if timestamp.tzinfo is None:
            timestamp = self.timezone.localize(timestamp)
        
        # Day of year (1-365)
        day = timestamp.timetuple().tm_yday
        
        # Solar declination (degrees)
        # Varies from -23.45° (winter solstice) to +23.45° (summer solstice)
        declination = 23.45 * math.sin(math.radians(360 / 365 * (day - 81)))
        
        # Hour angle (degrees)
        # 0° at solar noon, -15° per hour before noon, +15° per hour after
        solar_time = timestamp.hour + timestamp.minute / 60 + timestamp.second / 3600
        hour_angle = 15 * (solar_time - 12)
        
        # Solar elevation angle
        lat_rad = math.radians(self.latitude)
        dec_rad = math.radians(declination)
        hour_rad = math.radians(hour_angle)
        
        elevation = math.degrees(
            math.asin(
                math.sin(lat_rad) * math.sin(dec_rad) +
                math.cos(lat_rad) * math.cos(dec_rad) * math.cos(hour_rad)
            )
        )
        
        return max(0, elevation)
    
    def calculate_solar_azimuth(self, timestamp: datetime) -> float:
        """Calculate sun azimuth angle (compass direction)"""
        # Simplified azimuth calculation
        # 0° = North, 90° = East, 180° = South, 270° = West
        day = timestamp.timetuple().tm_yday
        declination = 23.45 * math.sin(math.radians(360 / 365 * (day - 81)))
        
        solar_time = timestamp.hour + timestamp.minute / 60
        hour_angle = 15 * (solar_time - 12)
        
        lat_rad = math.radians(self.latitude)
        dec_rad = math.radians(declination)
        hour_rad = math.radians(hour_angle)
        
        # Simplified azimuth (good enough for simulation)
        if hour_angle < 0:  # Morning
            azimuth = 90 + hour_angle  # East to South
        else:  # Afternoon
            azimuth = 180 + hour_angle  # South to West
            
        return azimuth % 360
    
    def get_cloud_cover(self) -> float:
        """
        Simulate realistic cloud cover
        
        Returns:
            Cloud cover fraction (0.0 = clear, 1.0 = overcast)
        """
        # Simple weather simulation
        # In reality, this would come from weather API or weather simulator
        
        # Base cloud probability
        base_cloud = 0.3
        
        # Add some randomness
        cloud_variation = random.uniform(-0.2, 0.3)
        
        cloud_cover = max(0.0, min(1.0, base_cloud + cloud_variation))
        
        return cloud_cover
    
    def get_ambient_temperature(self, timestamp: datetime) -> float:
        """
        Simulate ambient temperature (affects panel efficiency)
        
        Returns:
            Temperature in Celsius
        """
        # Simplified temperature model
        hour = timestamp.hour
        
        # Daily temperature cycle
        if 6 <= hour < 12:
            # Morning warming
            temp = 10 + (hour - 6) * 2
        elif 12 <= hour < 18:
            # Afternoon peak
            temp = 22 - (hour - 12) * 1.5
        else:
            # Night cooling
            temp = 8 + random.uniform(-2, 2)
        
        return temp
    
    def calculate_power_output(self,
                               timestamp: datetime,
                               cloud_cover: float = None) -> float:
        """
        Calculate realistic PV output in kW
        
        Args:
            timestamp: Current time
            cloud_cover: Cloud cover fraction (0.0-1.0), None = auto-simulate
            
        Returns:
            Power output in kW
        """
        # Sun elevation
        elevation = self.calculate_solar_elevation(timestamp)
        
        if elevation <= 0:
            return 0.0  # Night time
        
        # Base irradiance calculation
        # Max ~1000 W/m² at solar noon, clear sky
        base_irradiance = 1000 * math.sin(math.radians(elevation))
        
        # Cloud impact
        if cloud_cover is None:
            cloud_cover = self.get_cloud_cover()
        
        cloud_factor = 1.0 - (cloud_cover * 0.8)  # Max 80% reduction
        
        # Temperature derating
        # PV panels lose efficiency at high temperatures
        # Typical: -0.4% per °C above 25°C
        temp = self.get_ambient_temperature(timestamp)
        temp_factor = 1.0 - (max(0, temp - 25) * 0.004)
        
        # Calculate power
        irradiance = base_irradiance * cloud_factor
        power_kw = (irradiance / 1000) * self.peak_power * temp_factor * self.efficiency
        
        # Add small random variation (±3%)
        # Represents micro-variations in panel performance, soiling, etc.
        variation = random.uniform(0.97, 1.03)
        
        return round(max(0, power_kw * variation), 3)
    
    def get_daily_production_curve(self, date: datetime) -> list:
        """
        Generate 24-hour production profile
        
        Args:
            date: Date to generate profile for
            
        Returns:
            List of hourly production data
        """
        curve = []
        for hour in range(24):
            timestamp = date.replace(hour=hour, minute=30, second=0, microsecond=0)
            power = self.calculate_power_output(timestamp)
            elevation = self.calculate_solar_elevation(timestamp)
            azimuth = self.calculate_solar_azimuth(timestamp)
            
            curve.append({
                'time': timestamp.isoformat(),
                'hour': hour,
                'power_kw': power,
                'elevation': round(elevation, 2),
                'azimuth': round(azimuth, 2),
                'daylight': elevation > 0
            })
        
        return curve
    
    def get_current_status(self) -> dict:
        """
        Get current solar system status
        
        Returns:
            Dictionary with current status information
        """
        now = datetime.now(self.timezone)
        power = self.calculate_power_output(now)
        elevation = self.calculate_solar_elevation(now)
        azimuth = self.calculate_solar_azimuth(now)
        cloud_cover = self.get_cloud_cover()
        temp = self.get_ambient_temperature(now)
        
        return {
            'timestamp': now.isoformat(),
            'power_kw': power,
            'power_w': round(power * 1000, 1),
            'sun_elevation': round(elevation, 2),
            'sun_azimuth': round(azimuth, 2),
            'cloud_cover_percent': round(cloud_cover * 100, 1),
            'ambient_temp_c': round(temp, 1),
            'daylight': elevation > 0,
            'system': {
                'peak_power_kw': self.peak_power,
                'panels': self.panels,
                'efficiency': self.efficiency,
                'location': {
                    'latitude': self.latitude,
                    'longitude': self.longitude
                }
            }
        }


# Example usage
if __name__ == "__main__":
    # Create simulator for Amsterdam
    simulator = SolarSimulator(
        latitude=52.3676,
        longitude=4.9041,
        peak_power_kw=6.0,
        timezone="Europe/Amsterdam"
    )
    
    # Get current status
    status = simulator.get_current_status()
    print("Current Solar Status:")
    print(f"  Power: {status['power_kw']} kW")
    print(f"  Sun Elevation: {status['sun_elevation']}°")
    print(f"  Cloud Cover: {status['cloud_cover_percent']}%")
    print(f"  Daylight: {status['daylight']}")
    
    # Get daily profile
    today = datetime.now(pytz.timezone("Europe/Amsterdam"))
    profile = simulator.get_daily_production_curve(today)
    print(f"\nDaily Production Profile ({len(profile)} hours):")
    for hour_data in profile:
        if hour_data['daylight']:
            print(f"  {hour_data['hour']:02d}:00 - {hour_data['power_kw']} kW (elevation: {hour_data['elevation']}°)")
