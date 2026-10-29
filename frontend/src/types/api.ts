export interface ModelIdentity {
  model_version: string;
  feature_contract_hash: string;
  threshold: number;
}

export interface Prediction {
  major_delay_probability: number;
  predicted_major_delay: boolean;
}

export interface CurrentPrediction extends Prediction {
  route_id: string | null;
  trip_id: string | null;
  vehicle_id: string | null;
  stop_id: string | null;
  feed_timestamp: number;
  current_arrival_delay_seconds: number | null;
  threshold: number;
  // Enriched UI context (derived or returned by scoring service)
  stop_name?: string;
  route_short_name?: string;
  route_type?: number; // 0: Tram, 3: Bus
  direction_id?: number;
  stop_sequence?: number;
  scheduled_seconds_to_next_stop?: number;
  distance_to_next_stop_meters?: number;
  vehicle_speed?: number;
  stop_lat?: number;
  stop_lon?: number;
  vehicle_lat?: number;
  vehicle_lon?: number;
}

export interface CurrentPredictionsResponse extends ModelIdentity {
  source_watermark: string;
  prediction_generated_at: string;
  source_age_seconds: number;
  rows: number;
  predictions: CurrentPrediction[];
}

export interface HistoryRecord extends Prediction {
  id: string | number;
  created_at: string;
  prediction_generated_at: string;
  source_feed_timestamp: number;
  entity_id: string;
  route_id: string | null;
  trip_id: string;
  vehicle_id: string | null;
  stop_id: string;
  stop_sequence: number;
  target_next_stop_id: string | null;
  current_arrival_delay_seconds: number | null;
  model_version: string;
  feature_contract_hash: string;
  threshold: number;
  source_silver_version: number | null;
  feature_preparation_batch_id: string | null;
  stop_name?: string;
}

export interface HistoryResponse {
  rows: number;
  query_generated_at: string;
  predictions: HistoryRecord[];
}

export interface HistoryQueryParams {
  route_id?: string;
  from?: string;
  to?: string;
  limit?: number;
  predicted_major_delay?: boolean;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface ReadyResponse {
  status: 'ready' | 'not_ready';
  model_status?: string;
  mode?: string;
  model_ready?: boolean;
  artifact_integrity?: string;
  workload_identity_configured?: boolean;
  database_configured?: boolean;
  prediction_persistence_enabled?: boolean;
}

export interface ModelInfoResponse {
  task: string;
  model_family: string;
  target: {
    event_id: string;
    description: string;
    delay_threshold_seconds: number;
  };
  operational_threshold: number;
  feature_count: number;
  metrics: {
    accuracy: number;
    precision: number;
    recall: number;
    f1: number;
    roc_auc: number;
    pr_auc: number;
  };
  feature_categories: {
    temporal: string[];
    delay_dynamics: string[];
    gtfs_spatial: string[];
    historical_aggregates: string[];
    alerts: string[];
  };
}

export interface KpiMetrics {
  currentPredictionsCount: number;
  majorDelayRate: number; // percentage, e.g. 18.5
  medianObservedDelaySeconds: number; // in seconds
  p90ObservedDelaySeconds: number; // in seconds
  sourceAgeSeconds: number;
  sourceWatermark: string;
  predictionGeneratedAt: string;
}

export type ConnectionState =
  | 'idle'
  | 'waking'
  | 'connecting'
  | 'connected'
  | 'fallback'
  | 'error';


export interface PageParams {
  page?: number; page_size?: 10 | 20 | 50; route?: string; stop?: string; query?: string;
  risk_class?: 'all' | 'major' | 'moderate' | 'regular';
  sort?: 'risk_desc' | 'delay_desc' | 'route_asc' | 'time_desc';
  mode?: 'all' | 'bus' | 'tram'; from?: string; to?: string;
}
export interface CatalogRoute {route_id:string; route_short_name:string; route_long_name:string; route_type:number;}
export interface PageInfo {source_route_count?:number; total: number; page: number; page_size: 10|20|50; total_pages: number;}
