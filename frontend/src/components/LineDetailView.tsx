import React, { useState } from 'react';
import { ArrowLeft, Clock, Bus, AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, MapPin, Gauge } from 'lucide-react';
import { CurrentPrediction, PredictionAggregate } from '../types/api';
import { RouteMap } from './RouteMap';
import { Translations, Language } from '../i18n/translations';

interface LineDetailViewProps {
  routeId: string;
  predictions: CurrentPrediction[];
  /** Server-side aggregate over every current observation of the line (not the visible page). */
  aggregate: PredictionAggregate | null;
  aggregateLoading: boolean;
  onBack: () => void;
  onInspectVehicle?: (vehicle: CurrentPrediction) => void;
  t: Translations;
  language: Language;
}

export const LineDetailView: React.FC<LineDetailViewProps> = ({
  routeId,
  predictions,
  aggregate,
  aggregateLoading,
  onBack,
  onInspectVehicle,
  t,
  language,
}) => {
  const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(null);
  const [expandedTechId, setExpandedTechId] = useState<string | null>(null);

  const lineVehicles = predictions.filter((p) => p.route_id === routeId);
  const isTram = lineVehicles[0]?.route_type === 0;
  const mode = isTram ? 'Tram' : lineVehicles[0]?.route_type === 3 ? 'Bus' : '—';

  const formatDelay = (seconds: number | null | undefined) => {
    if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return t.states.noValue;
    const abs = Math.abs(seconds);
    const mins = Math.floor(abs / 60);
    const secs = Math.round(abs % 60);
    const sign = seconds < 0 ? '-' : '+';
    if (mins === 0) return `${sign}${secs}s`;
    return `${sign}${mins}m ${secs}s`;
  };

  const getSemanticStatus = (probability: number) => {
    if (probability >= 0.35) {
      return {
        label: t.currentSituation.statuses.majorDelay,
        color: 'text-[#8E001C] bg-[#FDF2F4] border-[#F1C3CA]',
        barColor: 'bg-[#8E001C]',
      };
    }
    if (probability >= 0.2) {
      return {
        label: t.currentSituation.statuses.moderateDelay,
        color: 'text-[#9A6700] bg-[#FFF9E6] border-[#FEEA9F]',
        barColor: 'bg-[#FFB300]',
      };
    }
    return {
      label: t.currentSituation.statuses.normal,
      color: 'text-[#065F46] bg-[#ECFDF5] border-[#A7F3D0]',
      barColor: 'bg-[#10B981]',
    };
  };

  // KPIs come from the server aggregate over the whole line population. While it is
  // loading or unavailable the cards show a dash, never a value derived from the visible page.
  const totalObservations = aggregate ? aggregate.total : null;
  const avgProb = aggregate && aggregate.total > 0 ? aggregate.average_probability : null;
  const maxDelay = aggregate && aggregate.total > 0 ? aggregate.max_observed_delay_seconds : null;

  const handleSelectVehicle = (v: CurrentPrediction) => {
    setSelectedVehicleId(v.trip_id || null);
    if (onInspectVehicle) onInspectVehicle(v);
  };

  return (
    <section id="route-detail" className="bg-white rounded-xl border border-[#E5E7EB] shadow-xs p-4 sm:p-6 mb-8">
      {/* Return button */}
      <button
        onClick={onBack}
        className="inline-flex items-center space-x-1.5 text-xs font-bold text-[#8E001C] hover:text-[#700016] mb-4 p-1 -ml-1 transition-colors group cursor-pointer"
      >
        <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
        <span>{t.lineDetail.backToAll}</span>
      </button>

      {/* Transport Information Header: Big Badge + Editorial Status Summary */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-5 border-b border-[#E5E7EB]">
        <div className="flex items-center space-x-4">
          <div
            className={`w-14 h-14 sm:w-16 sm:h-16 rounded-xl flex items-center justify-center text-white font-black text-2xl sm:text-3xl shadow-xs shrink-0 ${
              isTram ? 'bg-[#00703C]' : 'bg-[#8E001C]'
            }`}
          >
            {routeId}
          </div>
          <div>
            <div className="flex items-center space-x-2.5">
              <h2 className="text-xl sm:text-2xl font-black text-[#111827] tracking-tight">
                {t.lineDetail.lineTitle(routeId)}
              </h2>
              {mode !== '—' && (
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-[#F3F4F6] text-[#374151]">
                  {t.lineDetail.modeLabel(mode)}
                </span>
              )}
            </div>
            <p className="text-xs text-[#6B7280] mt-0.5 font-medium">
              {totalObservations === null
                ? t.states.noValue
                : totalObservations === 0
                  ? t.states.noCurrentData
                  : t.lineDetail.activeTripsCount(totalObservations)}
            </p>
          </div>
        </div>

        {/* Integrated Status Strip */}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 py-2 px-3.5 bg-[#F8F9FA] rounded-lg border border-[#E5E7EB] text-xs">
          <div>
            <span className="text-[#6B7280] block text-[11px]">{t.lineDetail.averageRisk}:</span>
            <span className="font-mono font-bold text-[#111827] text-sm">
              {avgProb === null ? t.states.noValue : `${(avgProb * 100).toFixed(1)}%`}
            </span>
          </div>
          <div className="h-6 w-px bg-[#E5E7EB] hidden sm:block"></div>
          <div>
            <span className="text-[#6B7280] block text-[11px]">{t.lineDetail.maxDelay}:</span>
            <span
              className={`font-mono font-bold text-sm ${
                maxDelay !== null && maxDelay >= 300 ? 'text-[#8E001C]' : 'text-[#111827]'
              }`}
            >
              {formatDelay(maxDelay)}
            </span>
          </div>
          <div className="h-6 w-px bg-[#E5E7EB] hidden sm:block"></div>
          <div>
            <span className="text-[#6B7280] block text-[11px]">{t.lineDetail.lastUpdate}:</span>
            <span className="font-medium text-[#111827] flex items-center space-x-1">
              <Clock className="w-3 h-3 text-[#9CA3AF]" />
              <span>{language === 'it' ? 'Scoring corrente' : 'Current scoring'}</span>
            </span>
          </div>
        </div>
      </div>

      {/* Primary Layout: Split between Route Map (Left) and Active Vehicles / Telemetry (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 mt-5 items-stretch">
        {/* LEFT / MAIN: Dedicated Leaflet Interactive Route Map */}
        <div className="lg:col-span-7 flex flex-col">
          <RouteMap
            routeId={routeId}
            vehicles={lineVehicles}
            selectedVehicleId={selectedVehicleId}
            onSelectVehicle={handleSelectVehicle}
            t={t}
            language={language}
          />
        </div>

        {/* RIGHT / SIDE PANEL: Monitored Vehicles and Telemetry */}
        <div className="lg:col-span-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-[#E5E7EB]">
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-[#111827]">
                {t.lineDetail.scoredVehiclesOnLine}
              </h3>
              <span className="text-[11px] font-mono font-bold text-[#8E001C]">
                {totalObservations === null || totalObservations === 0
                  ? t.states.noValue
                  : language === 'it'
                    ? `${lineVehicles.length} di ${totalObservations} osservazioni`
                    : `${lineVehicles.length} of ${totalObservations} observations`}
              </span>
            </div>

            {lineVehicles.length === 0 ? (
              <div className="py-8 text-center text-xs text-[#6B7280] bg-[#F9FAFB] rounded-lg border border-[#E5E7EB]">
                {aggregateLoading || aggregate === null ? t.states.noValue : t.states.noCurrentData}
              </div>
            ) : (
              <div className="space-y-3 max-h-[460px] overflow-y-auto pr-1">
                {lineVehicles.map((vehicle, idx) => {
                  const status = getSemanticStatus(vehicle.major_delay_probability);
                  const isSelected = selectedVehicleId === vehicle.trip_id;
                  const stopDisplayName =
                    vehicle.stop_name ||
                    (vehicle.stop_id && undefined) ||
                    `Fermata ${vehicle.stop_id}`;
                  const isTechOpen = expandedTechId === vehicle.trip_id;

                  return (
                    <div
                      key={`${vehicle.trip_id}-${idx}`}
                      onClick={() => handleSelectVehicle(vehicle)}
                      role="button" tabIndex={0}
                      onKeyDown={(event) => { if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); handleSelectVehicle(vehicle); } }}
                      className={`p-3.5 rounded-lg border transition-all cursor-pointer ${
                        isSelected
                          ? 'bg-[#FDF2F4] border-2 border-[#8E001C] shadow-xs'
                          : 'bg-[#FAFAFA] hover:bg-white border-[#E5E7EB] hover:border-[#D1D5DB]'
                      }`}
                    >
                      {/* Top line: Vehicle ID & Status Badge */}
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center space-x-2">
                          <span className="font-mono text-xs font-extrabold text-[#111827]">
                            {vehicle.vehicle_id || (language === 'it' ? 'Osservazione' : 'Observation')}
                          </span>
                          <span className="text-[10px] text-[#6B7280]">
                            {vehicle.stop_sequence ? `#Fermata ${vehicle.stop_sequence}` : ''}
                          </span>
                        </div>
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded border ${status.color}`}
                        >
                          {status.label}
                        </span>
                      </div>

                      {/* Main stop & delay focus */}
                      <div className="flex items-start justify-between gap-3 mt-1.5">
                        <div className="min-w-0">
                          <span className="text-[10px] text-[#6B7280] block">
                            {t.currentSituation.table.nextStop}:
                          </span>
                          <span className="text-xs font-bold text-[#111827] flex items-center space-x-1 mt-0.5 truncate">
                            <MapPin className="w-3.5 h-3.5 text-[#8E001C] shrink-0" />
                            <span className="truncate">{stopDisplayName}</span>
                          </span>
                        </div>

                        <div className="text-right shrink-0">
                          <span className="text-[10px] text-[#6B7280] block">
                            {t.currentSituation.table.observedDelay}:
                          </span>
                          <span
                            className={`font-mono text-xs font-extrabold block mt-0.5 ${
                              (vehicle.current_arrival_delay_seconds || 0) >= 300
                                ? 'text-[#8E001C]'
                                : 'text-[#111827]'
                            }`}
                          >
                            {formatDelay(vehicle.current_arrival_delay_seconds)}
                          </span>
                        </div>
                      </div>

                      {/* Delay probability indicator */}
                      <div className="mt-2.5">
                        <div className="flex justify-between text-[10px] mb-1">
                          <span className="text-[#6B7280]">
                            {t.currentSituation.table.majorDelayRisk}:
                          </span>
                          <span className="font-mono font-bold text-[#111827]">
                            {(vehicle.major_delay_probability * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="relative w-full h-1.5 bg-[#E5E7EB] rounded-full overflow-hidden">
                          <div
                            className={`h-full ${status.barColor}`}
                            style={{ width: `${Math.min(100, vehicle.major_delay_probability * 100)}%` }}
                          ></div>
                        </div>
                      </div>

                      {/* Collapsible Technical Details */}
                      <div className="mt-2.5 pt-2 border-t border-[#E5E7EB]">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setExpandedTechId(isTechOpen ? null : (vehicle.trip_id || ''));
                          }}
                          className="text-[10px] font-semibold text-[#6B7280] hover:text-[#111827] flex items-center space-x-1"
                        >
                          <span>
                            {isTechOpen
                              ? t.lineDetail.hideTechnicalDetails
                              : t.lineDetail.technicalDetails}
                          </span>
                          {isTechOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        </button>

                        {isTechOpen && (
                          <div className="mt-2 p-2 bg-[#F3F4F6] rounded text-[10px] font-mono text-[#4B5563] space-y-1">
                            <div>Trip ID: <span className="text-[#111827]">{vehicle.trip_id}</span></div>
                            <div>Stop ID: <span className="text-[#111827]">{vehicle.stop_id}</span></div>
                            {vehicle.vehicle_speed !== undefined && (
                              <div>Velocità: <span className="text-[#111827]">{vehicle.vehicle_speed.toFixed(1)} km/h</span></div>
                            )}
                            {vehicle.distance_to_next_stop_meters !== undefined && (
                              <div>Distanza: <span className="text-[#111827]">{vehicle.distance_to_next_stop_meters} m</span></div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};
