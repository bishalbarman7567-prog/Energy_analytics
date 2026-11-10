from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class PlantSchema(BaseModel):
    plant_id: str
    plant_name: str
    timezone: str
    location_city: str
    status: str
    effective_from: str

    class Config:
        from_attributes = True


class MeterSchema(BaseModel):
    meter_id: str
    plant_id: str
    meter_name: str
    meter_type: str
    unit_power: str
    unit_energy: str
    sampling_interval_min: int
    install_date: str
    retire_date: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class MachineSchema(BaseModel):
    machine_id: str
    plant_id: str
    meter_id: str
    machine_name: str
    machine_type: str
    rated_kw: float
    idle_kw_baseline: float
    commission_date: str
    status: str

    class Config:
        from_attributes = True


class ShiftSchema(BaseModel):
    shift_id: str
    plant_id: str
    shift_name: str
    start_time_local: str
    end_time_local: str
    days_of_week: str

    class Config:
        from_attributes = True


class TariffSchema(BaseModel):
    tariff_id: str
    plant_id: str
    name: str
    rate_per_kwh: float
    demand_charge_per_kw: float
    day_type: str
    start_time_local: str
    end_time_local: str
    timezone: str
    effective_start: str
    effective_end: str

    class Config:
        from_attributes = True


class WeatherObservationSchema(BaseModel):
    weather_id: str
    plant_id: str
    timestamp_local: str
    temperature_c: float
    humidity_pct: float
    condition: str

    class Config:
        from_attributes = True


class ProductionBatchSchema(BaseModel):
    batch_id: str
    plant_id: str
    machine_id: str
    shift_id: Optional[str] = None
    planned_start_ts: str
    planned_end_ts: str
    actual_start_ts: str
    actual_end_ts: str
    output_qty: float
    output_unit: str
    scrap_qty: float
    status: str

    class Config:
        from_attributes = True


class EnergyReadingSchema(BaseModel):
    reading_id: str
    meter_id: str
    plant_id: str
    machine_id: Optional[str] = None
    batch_id: Optional[str] = None
    tariff_id: Optional[str] = None
    interval_start_ts: str
    interval_end_ts: str
    kwh: float
    kw_avg: float
    is_idle: str
    is_peak_window: str
    quality_flag: str
    source: str

    class Config:
        from_attributes = True


class MaintenanceEventCreate(BaseModel):
    plant_id: str = "PLANT-001"
    machine_id: str
    event_type: str  # preventive, corrective, inspection
    start_ts: str
    end_ts: str
    description: str
    impact: str = "downtime"


class MaintenanceEventSchema(MaintenanceEventCreate):
    maintenance_id: str

    class Config:
        from_attributes = True


class RecommendationSchema(BaseModel):
    recommendation_id: str
    plant_id: str
    meter_id: Optional[str] = None
    machine_id: Optional[str] = None
    category: str
    baseline_metric: str
    baseline_value: float
    expected_savings_kwh: float
    expected_savings_usd: float
    confidence: float
    status: str
    created_ts: str
    rationale: str

    class Config:
        from_attributes = True


class RecommendationActionRequest(BaseModel):
    user_role: str = "Plant Operator"
    reason: Optional[str] = "Approved by plant operator in EnergyIQ"


class AnomalySchema(BaseModel):
    anomaly_id: str
    plant_id: str
    meter_id: Optional[str] = None
    machine_id: Optional[str] = None
    timestamp: str
    anomaly_type: str
    severity: str
    score: float
    detected_value: Optional[float] = None
    baseline_value: Optional[float] = None
    evidence: str
    status: str
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None

    class Config:
        from_attributes = True


class AnomalyAcknowledgeRequest(BaseModel):
    user_role: str = "Maintenance/Quality Engineer"
    notes: Optional[str] = "Acknowledged and scheduled for inspection"


class EnergySummaryResponse(BaseModel):
    plant_id: str
    total_energy_kwh: float
    total_cost_usd: float
    peak_demand_kw: float
    peak_demand_timestamp: Optional[str] = None
    avg_energy_intensity_kwh_per_unit: float
    total_production_units: float
    total_idle_energy_kwh: float
    idle_energy_waste_usd: float
    idle_percentage: float
    total_potential_savings_kwh: float
    total_potential_savings_usd: float
    readings_count: int
    quality_flag_breakdown: Dict[str, int]


class DataQualitySummaryResponse(BaseModel):
    total_issues: int
    reconciliation_mismatches_count: int
    unit_confusions_count: int
    timezone_mismatches_count: int
    duplicates_count: int
    hierarchy_mismatches_count: int
    meter_gaps_count: int
    items: List[Dict[str, Any]]


class AuditLogSchema(BaseModel):
    log_id: int
    timestamp: str
    event_type: str
    user_role: str
    entity_type: str
    entity_id: str
    details: str
    previous_state: Optional[str] = None
    new_state: Optional[str] = None

    class Config:
        from_attributes = True

