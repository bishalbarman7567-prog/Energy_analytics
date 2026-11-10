from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, ForeignKey, DateTime, Text, Boolean, PrimaryKeyConstraint
)
from sqlalchemy.orm import relationship
from backend.database import Base


class Plant(Base):
    __tablename__ = "Plant"

    plant_id = Column(String(50), primary_key=True, index=True)
    plant_name = Column(String(200), nullable=False)
    timezone = Column(String(100), nullable=False)
    location_city = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, default="active")
    effective_from = Column(String(50), nullable=False)

    meters = relationship("Meter", back_populates="plant")
    machines = relationship("Machine", back_populates="plant")
    shifts = relationship("Shift", back_populates="plant")
    tariffs = relationship("Tariff", back_populates="plant")
    weather_observations = relationship("WeatherObservation", back_populates="plant")


class Meter(Base):
    __tablename__ = "Meter"

    meter_id = Column(String(50), primary_key=True, index=True)
    plant_id = Column(String(50), ForeignKey("Plant.plant_id"), nullable=False)
    meter_name = Column(String(200), nullable=False)
    meter_type = Column(String(50), nullable=False)  # main, sub, feeder
    unit_power = Column(String(20), nullable=False, default="kW")
    unit_energy = Column(String(20), nullable=False, default="kWh")
    sampling_interval_min = Column(Integer, nullable=False, default=15)
    install_date = Column(String(50), nullable=False)
    retire_date = Column(String(50), nullable=True)
    status = Column(String(50), nullable=False, default="active")

    plant = relationship("Plant", back_populates="meters")
    machines = relationship("Machine", back_populates="meter")
    readings = relationship("EnergyReading", back_populates="meter")


class Machine(Base):
    __tablename__ = "Machine"

    machine_id = Column(String(50), primary_key=True, index=True)
    plant_id = Column(String(50), ForeignKey("Plant.plant_id"), nullable=False)
    meter_id = Column(String(50), ForeignKey("Meter.meter_id"), nullable=False)
    machine_name = Column(String(200), nullable=False)
    machine_type = Column(String(50), nullable=False)  # press, cnc, oven, conveyor, compressor, mixer
    rated_kw = Column(Float, nullable=False)
    idle_kw_baseline = Column(Float, nullable=False)
    commission_date = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default="active")

    plant = relationship("Plant", back_populates="machines")
    meter = relationship("Meter", back_populates="machines")
    batches = relationship("ProductionBatch", back_populates="machine")
    maintenance_events = relationship("MaintenanceEvent", back_populates="machine")


class Shift(Base):
    __tablename__ = "Shift"

    shift_id = Column(String(50), primary_key=True, index=True)
    plant_id = Column(String(50), ForeignKey("Plant.plant_id"), nullable=False)
    shift_name = Column(String(100), nullable=False)
    start_time_local = Column(String(10), nullable=False)
    end_time_local = Column(String(10), nullable=False)
    days_of_week = Column(String(100), nullable=False)

    plant = relationship("Plant", back_populates="shifts")
    batches = relationship("ProductionBatch", back_populates="shift")


class Tariff(Base):
    __tablename__ = "Tariff"

    tariff_id = Column(String(50), primary_key=True, index=True)
    plant_id = Column(String(50), ForeignKey("Plant.plant_id"), nullable=False)
    name = Column(String(50), nullable=False)  # peak, shoulder, offpeak
    rate_per_kwh = Column(Float, nullable=False)
    demand_charge_per_kw = Column(Float, nullable=False)
    day_type = Column(String(50), nullable=False)  # weekday, weekend
    start_time_local = Column(String(10), nullable=False)
    end_time_local = Column(String(10), nullable=False)
    timezone = Column(String(100), nullable=False)
    effective_start = Column(String(50), nullable=False)
    effective_end = Column(String(50), nullable=False)

    plant = relationship("Plant", back_populates="tariffs")


class WeatherObservation(Base):
    __tablename__ = "WeatherObservation"

    weather_id = Column(String(50), primary_key=True, index=True)
    plant_id = Column(String(50), ForeignKey("Plant.plant_id"), nullable=False)
    timestamp_local = Column(String(50), nullable=False, index=True)
    temperature_c = Column(Float, nullable=False)
    humidity_pct = Column(Float, nullable=False)
    condition = Column(String(50), nullable=False)

    plant = relationship("Plant", back_populates="weather_observations")


class ProductionBatch(Base):
    __tablename__ = "ProductionBatch"

    batch_id = Column(String(50), primary_key=True, index=True)
    plant_id = Column(String(50), ForeignKey("Plant.plant_id"), nullable=False)
    machine_id = Column(String(50), ForeignKey("Machine.machine_id"), nullable=False)
    shift_id = Column(String(50), ForeignKey("Shift.shift_id"), nullable=True)
    planned_start_ts = Column(String(50), nullable=False)
    planned_end_ts = Column(String(50), nullable=False)
    actual_start_ts = Column(String(50), nullable=False)
    actual_end_ts = Column(String(50), nullable=False)
    output_qty = Column(Float, nullable=False, default=0.0)
    output_unit = Column(String(50), nullable=False, default="units")
    scrap_qty = Column(Float, nullable=False, default=0.0)
    status = Column(String(50), nullable=False)  # planned, running, completed, cancelled

    machine = relationship("Machine", back_populates="batches")
    shift = relationship("Shift", back_populates="batches")
    readings = relationship("EnergyReading", back_populates="batch")


class EnergyReading(Base):
    __tablename__ = "EnergyReading"

    reading_id = Column(String(100), primary_key=True, index=True)
    meter_id = Column(String(50), ForeignKey("Meter.meter_id"), nullable=False, index=True)
    plant_id = Column(String(50), ForeignKey("Plant.plant_id"), nullable=False)
    machine_id = Column(String(50), ForeignKey("Machine.machine_id"), nullable=True, index=True)
    batch_id = Column(String(50), ForeignKey("ProductionBatch.batch_id"), nullable=True, index=True)
    tariff_id = Column(String(50), ForeignKey("Tariff.tariff_id"), nullable=True)
    interval_start_ts = Column(String(50), nullable=False, index=True)
    interval_end_ts = Column(String(50), nullable=False)
    kwh = Column(Float, nullable=False)
    kw_avg = Column(Float, nullable=False)
    is_idle = Column(String(10), nullable=False, default="false")  # stored as string 'true'/'false'
    is_peak_window = Column(String(10), nullable=False, default="false")
    quality_flag = Column(String(50), nullable=False, default="ok", index=True)
    source = Column(String(50), nullable=False, default="scada")

    meter = relationship("Meter", back_populates="readings")
    batch = relationship("ProductionBatch", back_populates="readings")


class MaintenanceEvent(Base):
    __tablename__ = "MaintenanceEvent"

    maintenance_id = Column(String(50), primary_key=True, index=True)
    plant_id = Column(String(50), ForeignKey("Plant.plant_id"), nullable=False)
    machine_id = Column(String(50), ForeignKey("Machine.machine_id"), nullable=False)
    event_type = Column(String(50), nullable=False)  # preventive, corrective, inspection
    start_ts = Column(String(50), nullable=False)
    end_ts = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    impact = Column(String(50), nullable=False)  # downtime, reduced_output, none

    machine = relationship("Machine", back_populates="maintenance_events")


class Recommendation(Base):
    __tablename__ = "Recommendation"

    recommendation_id = Column(String(50), primary_key=True, index=True)
    plant_id = Column(String(50), ForeignKey("Plant.plant_id"), nullable=False)
    meter_id = Column(String(50), nullable=True)
    machine_id = Column(String(50), nullable=True)
    category = Column(String(50), nullable=False)  # idle_load, peak_demand, tariff_shift, maintenance, anomaly
    baseline_metric = Column(String(200), nullable=False)
    baseline_value = Column(Float, nullable=False)
    expected_savings_kwh = Column(Float, nullable=False)
    expected_savings_usd = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    status = Column(String(50), nullable=False, default="open")  # open, approved, rejected, implemented
    created_ts = Column(String(50), nullable=False)
    rationale = Column(Text, nullable=False)


class MeterDailyTotal(Base):
    __tablename__ = "MeterDailyTotal"

    meter_id = Column(String(50), primary_key=True)
    day = Column(String(20), primary_key=True)
    interval_sum_kwh = Column(Float, nullable=False)
    reported_total_kwh = Column(Float, nullable=False)
    reconciles = Column(String(10), nullable=False, default="true")

    __table_args__ = (
        PrimaryKeyConstraint("meter_id", "day"),
    )


class AnomalyRecord(Base):
    __tablename__ = "AnomalyRecord"

    anomaly_id = Column(String(50), primary_key=True, index=True)
    plant_id = Column(String(50), nullable=False)
    meter_id = Column(String(50), nullable=True)
    machine_id = Column(String(50), nullable=True)
    timestamp = Column(String(50), nullable=False, index=True)
    anomaly_type = Column(String(100), nullable=False)  # peak_spike, high_idle, intensity_outlier, quality_issue
    severity = Column(String(20), nullable=False)  # CRITICAL, HIGH, MEDIUM, LOW
    score = Column(Float, nullable=False, default=1.0)
    detected_value = Column(Float, nullable=True)
    baseline_value = Column(Float, nullable=True)
    evidence = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="OPEN")  # OPEN, ACKNOWLEDGED, RESOLVED
    acknowledged_by = Column(String(100), nullable=True)
    acknowledged_at = Column(String(50), nullable=True)


class AuditLog(Base):
    __tablename__ = "AuditLog"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String(50), nullable=False, default=lambda: datetime.utcnow().isoformat())
    event_type = Column(String(100), nullable=False)  # RECOMMENDATION_APPROVED, ANOMALY_ACKNOWLEDGED, DATA_GENERATION, etc.
    user_role = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(100), nullable=False)
    details = Column(Text, nullable=False)
    previous_state = Column(String(100), nullable=True)
    new_state = Column(String(100), nullable=True)

