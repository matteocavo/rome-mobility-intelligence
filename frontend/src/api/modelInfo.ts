import type { ModelInfoResponse } from '../types/api';
// Documented held-out TEST metrics; not a live readiness or training response.
export const DOCUMENTED_MODEL_INFO: ModelInfoResponse = {
  task: 'Binary Classification (Operational Early Warning)',
  model_family: 'HistGradientBoostingClassifier',
  target: {
    event_id: 'next_stop_delay_ge_300s',
    description: 'Next-stop arrival delay â‰¥ 300 seconds (5 minutes)',
    delay_threshold_seconds: 300,
  },
  operational_threshold: 0.35,
  feature_count: 47,
  metrics: {
    accuracy: 0.95652,
    precision: 0.78419,
    recall: 0.79907,
    f1: 0.79156,
    roc_auc: 0.97168,
    pr_auc: 0.87416,
  },
  feature_categories: {
    temporal: ['feed_hour', 'feed_minute', 'day_of_week', 'is_weekend', 'minutes_since_midnight'],
    delay_dynamics: [
      'current_arrival_delay_seconds',
      'lag_1_arrival_delay_seconds',
      'lag_2_arrival_delay_seconds',
      'lag_3_arrival_delay_seconds',
      'rolling_mean_delay_last_3_stops',
      'rolling_max_delay_last_3_stops',
      'rolling_std_delay_last_3_stops',
      'delay_change_from_previous_stop',
      'delay_acceleration',
    ],
    gtfs_spatial: [
      'scheduled_seconds_to_next_stop',
      'distance_to_next_stop_meters',
      'vehicle_speed',
      'vehicle_bearing',
      'current_stop_sequence',
      'vehicle_position_staleness_seconds',
    ],
    historical_aggregates: [
      'historical_route_mean_delay',
      'historical_stop_mean_delay',
      'historical_route_stop_mean_delay',
      'historical_route_hour_mean_delay',
      'historical_route_observation_count',
      'historical_stop_observation_count',
    ],
    alerts: [
      'active_alert_flag',
      'active_alert_count',
      'active_detour_flag',
      'active_construction_flag',
    ],
  },
};
