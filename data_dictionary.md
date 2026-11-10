# Data Dictionary

This document defines entities, fields, relationships, and rules for the energy waste / peak demand analytics dataset.

## Conventions
- **Seed:** `20261022` (fixed, deterministic generation)
- **Timezone baseline:** Plant local time (`America/Chicago`) for operations; all timestamps stored as ISO-8601 with offset where applicable.
- **Primary keys:** immutable, deterministic where specified.
- **Lifecycle/event history:** state changes retained as events/records (no destructive overwrite).

## Entity Overview & Cardinality

| Entity | PK | Parent / FK Relationships | Cardinality | Lifecycle / Effective Dating |
|---|---|---|---|---|
| Plant | `plant_id` | - | 1 Plant : N Meter/Machine/Shift/Batch | `status` (active/inactive), `effective_from` |
| Meter | `meter_id` | `plant_id` -> Plant | 1 Meter : N EnergyReading; 1 Meter : N Machine (hierarchy assignments via effective dates) | `status`, `install_date`, `retire_date` |
| Machine | `machine_id` | `plant_id` -> Plant, `meter_id` -> Meter (current), hierarchy history in readings/assignments | 1 Machine : N ProductionBatch, N MaintenanceEvent | `status`, `commission_date` |
| Shift | `shift_id` | `plant_id` -> Plant | 1 Shift : N ProductionBatch (by time alignment) | effective by schedule window |
| Tariff | `tariff_id` | `plant_id` -> Plant | 1 Tariff window : N EnergyReading (by time match) | `effective_start`, `effective_end`, `timezone` |
| WeatherObservation | `weather_id` | `plant_id` -> Plant | 1 WeatherObservation per plant per hour (aligned) | timestamped observation |
| ProductionBatch | `batch_id` | `plant_id`, `machine_id`, `shift_id` (nullable if outside shift) | 1 Batch : N EnergyReading (aligned interval allocation) | `status` (planned/running/completed/cancelled) |
| EnergyReading | `reading_id` | `meter_id`, `plant_id`, `machine_id` (attributed), `batch_id` (nullable), `tariff_id` (nullable) | N readings : 1 meter | immutable interval event; `quality_flag` |
| MaintenanceEvent | `maintenance_id` | `machine_id`, `plant_id` | N events : 1 machine | `event_type`, `start_ts`, `end_ts` |
| Recommendation | `recommendation_id` | `plant_id`, optional `meter_id`/`machine_id` | advisory record | `status` (open/accepted/rejected/closed) |

**Bridge / history notes:** Meter-to-machine attribution is represented on `EnergyReading.machine_id` (effective attribution per interval) and documented hierarchy; many-to-many time alignments (readings↔batches↔tariffs) are resolved by interval logic and stored FKs where applicable. State changes are preserved (e.g. maintenance events, recommendation status records in export context).

---

## 1. Plant
| Field | Type | Req | Allowed / Unit | Unique | Validation |
|---|---|---|---|---|---|
| plant_id | string | Y | `PLANT-001` | Y (PK) | matches pattern |
| plant_name | string | Y | text | N | non-empty |
| timezone | string | Y | IANA TZ (e.g. `America/Chicago`) | N | valid TZ string |
| location_city | string | Y | text | N | non-empty |
| status | string | Y | active,inactive | N | enum |
| effective_from | date | Y | YYYY-MM-DD | N | valid date |

## 2. Meter
| Field | Type | Req | Allowed / Unit | Unique | Validation |
|---|---|---|---|---|---|
| meter_id | string | Y | `MTR-<plant-id>-NNN` | Y (PK) | pattern, immutable |
| plant_id | string | Y | FK Plant | N | exists in Plant |
| meter_name | string | Y | text | N | non-empty |
| meter_type | string | Y | main,sub,feeder | N | enum |
| unit_power | string | Y | `kW` | N | fixed |
| unit_energy | string | Y | `kWh` | N | fixed |
| sampling_interval_min | int | Y | 15 | N | =15 |
| install_date | date | Y | YYYY-MM-DD | N | <= retire_date if set |
| retire_date | date | N | YYYY-MM-DD/null | N | >= install_date |
| status | string | Y | active,inactive | N | enum |

## 3. Machine
| Field | Type | Req | Allowed / Unit | Unique | Validation |
|---|---|---|---|---|---|
| machine_id | string | Y | `MCH-<plant-id>-NNN` | Y (PK) | pattern |
| plant_id | string | Y | FK Plant | N | exists |
| meter_id | string | Y | FK Meter | N | exists; hierarchy consistent |
| machine_name | string | Y | text | N | non-empty |
| machine_type | string | Y | press,cnc,oven,conveyor,compressor,mixer | N | enum |
| rated_kw | float | Y | kW | N | >0 |
| idle_kw_baseline | float | Y | kW | N | >=0, <= rated_kw |
| commission_date | date | Y | YYYY-MM-DD | N | valid |
| status | string | Y | active,maintenance,retired | N | enum |

## 4. Shift
| Field | Type | Req | Allowed / Unit | Unique | Validation |
|---|---|---|---|---|---|
| shift_id | string | Y | `SHF-<plant-id>-A/B/C` | Y (PK) | pattern |
| plant_id | string | Y | FK Plant | N | exists |
| shift_name | string | Y | Day/Evening/Night | N | non-empty |
| start_time_local | time | Y | HH:MM | N | valid |
| end_time_local | time | Y | HH:MM | N | valid (may wrap) |
| days_of_week | string | Y | e.g. Mon-Sun | N | non-empty |

## 5. Tariff
| Field | Type | Req | Allowed / Unit | Unique | Validation |
|---|---|---|---|---|---|
| tariff_id | string | Y | `TAR-2026-NNN` | Y (PK) | pattern, immutable |
| plant_id | string | Y | FK Plant | N | exists |
| name | string | Y | peak/shoulder/offpeak | N | enum-like |
| rate_per_kwh | float | Y | USD/kWh | N | >=0 |
| demand_charge_per_kw | float | Y | USD/kW-month (allocated) | N | >=0 |
| day_type | string | Y | weekday/weekend/all | N | enum |
| start_time_local | time | Y | HH:MM | N | valid |
| end_time_local | time | Y | HH:MM | N | valid |
| timezone | string | Y | IANA TZ | N | **must match plant for correct costing** (edge cases may mismatch) |
| effective_start | date | Y | YYYY-MM-DD | N | <= effective_end |
| effective_end | date | Y | YYYY-MM-DD | N | >= effective_start |

## 6. WeatherObservation
| Field | Type | Req | Allowed / Unit | Unique | Validation |
|---|---|---|---|---|---|
| weather_id | string | Y | `WTH-<plant-id>-<yyyymmddHH>` | Y (PK) | pattern |
| plant_id | string | Y | FK Plant | N | exists |
| timestamp_local | datetime | Y | ISO-8601 | N | hourly cadence |
| temperature_c | float | Y | °C | N | reasonable range |
| humidity_pct | float | Y | % | N | 0-100 |
| condition | string | Y | clear/cloudy/rain/snow | N | enum |

## 7. ProductionBatch
| Field | Type | Req | Allowed / Unit | Unique | Validation |
|---|---|---|---|---|---|
| batch_id | string | Y | `BATCH-2026-NNNNNN` | Y (PK) | zero-padded, immutable |
| plant_id | string | Y | FK Plant | N | exists |
| machine_id | string | Y | FK Machine | N | exists, hierarchy valid |
| shift_id | string | N | FK Shift | N | exists if set |
| planned_start_ts | datetime | Y | ISO-8601 | N | <= planned_end |
| planned_end_ts | datetime | Y | ISO-8601 | N | >= planned_start |
| actual_start_ts | datetime | Y | ISO-8601 | N | valid |
| actual_end_ts | datetime | Y | ISO-8601 | N | >= actual_start |
| output_qty | float | Y | units | N | >=0 |
| output_unit | string | Y | `units` | N | fixed |
| scrap_qty | float | Y | units | N | >=0 |
| status | string | Y | planned,running,completed,cancelled | N | enum/lifecycle |

## 8. EnergyReading
| Field | Type | Req | Allowed / Unit | Unique | Validation |
|---|---|---|---|---|---|
| reading_id | string | Y | `ENG-<meter-id>-<timestamp>` | Y (PK, except labelled duplicate edge cases) | pattern |
| meter_id | string | Y | FK Meter | N | exists |
| plant_id | string | Y | FK Plant | N | exists, matches meter |
| machine_id | string | Y | FK Machine | N | exists; **should be in meter hierarchy** (edge cases labelled) |
| batch_id | string | N | FK ProductionBatch | N | exists if set; time-aligned when producing |
| tariff_id | string | N | FK Tariff | N | resolved by interval/tz rules |
| interval_start_ts | datetime | Y | ISO-8601 | N | 15-min boundary |
| interval_end_ts | datetime | Y | ISO-8601 | N | start + 15 min |
| kwh | float | Y | kWh | N | >=0; **edge cases may confuse with kW** |
| kw_avg | float | Y | kW | N | derived/consistent `kwh*4` normally |
| is_idle | bool | Y | true/false | N | labelled idle period logic |
| is_peak_window | bool | Y | true/false | N | tariff-window derived |
| quality_flag | string | Y | ok,missing,estimated,duplicate,unit_confusion,hierarchy_mismatch | N | enum |
| source | string | Y | scada,manual,estimated | N | enum |

## 9. MaintenanceEvent
| Field | Type | Req | Allowed / Unit | Unique | Validation |
|---|---|---|---|---|---|
| maintenance_id | string | Y | `MNT-<machine-id>-NNN` | Y (PK) | pattern |
| plant_id | string | Y | FK Plant | N | exists |
| machine_id | string | Y | FK Machine | N | exists |
| event_type | string | Y | preventive,corrective,inspection | N | enum |
| start_ts | datetime | Y | ISO-8601 | N | <= end_ts |
| end_ts | datetime | Y | ISO-8601 | N | >= start_ts |
| description | string | Y | text | N | non-empty |
| impact | string | Y | downtime,reduced_output,none | N | enum |

## 10. Recommendation
| Field | Type | Req | Allowed / Unit | Unique | Validation |
|---|---|---|---|---|---|
| recommendation_id | string | Y | `REC-2026-NNNNNN` | Y (PK) | pattern, immutable |
| plant_id | string | Y | FK Plant | N | exists |
| meter_id | string | N | FK Meter | N | exists if set |
| machine_id | string | N | FK Machine | N | exists if set |
| category | string | Y | idle_load,peak_demand,tariff_shift,maintenance,anomaly | N | enum |
| baseline_metric | string | Y | text | N | measurable baseline cited |
| baseline_value | float | Y | numeric | N | from source records |
| expected_savings_kwh | float | Y | kWh/period | N | >=0, measurable |
| expected_savings_usd | float | Y | USD/period | N | >=0 |
| confidence | float | Y | 0-1 | N | in range |
| status | string | Y | open,accepted,rejected,closed | N | enum |
| created_ts | datetime | Y | ISO-8601 | N | valid |
| rationale | string | Y | text | N | cites evidence/baseline |

## Ground Truth (separate artifact)
`ground_truth.csv/json` contains labelled anomalies/expected decisions: `case_id`, `entity`, `record_id`, `issue_type`, `expected_detection`, `expected_action`, `notes`. **Never merged into model/input feature tables.**
