import React, { useEffect, useRef, useMemo } from 'react';
import L from 'leaflet';
import { CurrentPrediction } from '../types/api';
import { stopDetails, escapeHtml } from '../api/geography';
import {
  MapPin,
  Layers,
  RotateCcw,
  AlertTriangle,
  ArrowRight,
  Bus,
  Gauge,
  Clock,
  Compass,
  CheckCircle2,
  X,
} from 'lucide-react';
import { Translations, Language } from '../i18n/translations';

interface CentralMobilityMapProps {
  predictions: CurrentPrediction[];
  selectedLine: string | null;
  onSelectLine: (routeId: string | null) => void;
  selectedVehicle: CurrentPrediction | null;
  onSelectVehicle: (vehicle: CurrentPrediction | null) => void;
  modeFilter: 'all' | 'bus' | 'tram';
  onSetModeFilter: (mode: 'all' | 'bus' | 'tram') => void;
  t: Translations;
  language: Language;
}

export const CentralMobilityMap: React.FC<CentralMobilityMapProps> = ({
  predictions,
  selectedLine,
  onSelectLine,
  selectedVehicle,
  onSelectVehicle,
  modeFilter,
  onSetModeFilter,
  t,
  language,
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const routeLayerRef = useRef<L.Polyline | null>(null);

  // Filter predictions by mode and selected line
  const activePredictions = useMemo(() => {
    return predictions.filter((p) => {
      const isTram = p.route_type === 0;
      if (modeFilter === 'bus' && p.route_type !== 3) return false;
      if (modeFilter === 'tram' && !isTram) return false;
      if (selectedLine && p.route_id !== selectedLine) return false;
      return true;
    });
  }, [predictions, modeFilter, selectedLine]);

  // Stops with real coordinates for the active line or all active vehicles
  const mappedStops = useMemo(() => {
    const map = new Map<
      string,
      { stopId: string; name: string; lat: number; lon: number; stopSeq?: number }
    >();

    activePredictions.forEach((p) => {
      if (p.stop_id && stopDetails(p)) {
        const details = stopDetails(p)!;
        map.set(p.stop_id, {
          stopId: p.stop_id,
          name: p.stop_name || details.name,
          lat: details.lat,
          lon: details.lon,
          stopSeq: p.stop_sequence,
        });
      }
    });

    const list = Array.from(map.values());
    list.sort((a, b) => (a.stopSeq || 0) - (b.stopSeq || 0));
    return list;
  }, [activePredictions]);

  // Ranked critical lines for the side panel
  const criticalLines = useMemo(() => {
    const map = new Map<string, { total: number; major: number; mode: 'Bus' | 'Tram' | '—' }>();
    predictions.forEach((p) => {
      const r = p.route_id || 'Altro';
      const isTram = p.route_type === 0;
      const existing = map.get(r) || { total: 0, major: 0, mode: isTram ? 'Tram' : p.route_type === 3 ? 'Bus' : '—' };
      existing.total++;
      if (p.major_delay_probability >= 0.35) {
        existing.major++;
      }
      map.set(r, existing);
    });

    return Array.from(map.entries())
      .map(([route, data]) => ({
        route,
        mode: data.mode,
        total: data.total,
        major: data.major,
        rate: (data.major / data.total) * 100,
      }))
      .sort((a, b) => b.rate - a.rate)
      .slice(0, 5);
  }, [predictions]);

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const romeCenter: [number, number] = [41.8958, 12.4825]; // Piazza Venezia
      const map = L.map(mapContainerRef.current, {
        center: romeCenter,
        zoom: 13,
        zoomControl: false,
        attributionControl: true,
        scrollWheelZoom: true,
      });

      L.control.zoom({ position: 'bottomright' }).addTo(map);

      // Official OpenStreetMap tile layer
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      markersLayerRef.current = L.layerGroup().addTo(map);
      mapInstanceRef.current = map;

      // Invalidate size on multiple ticks
      const timer1 = setTimeout(() => map.invalidateSize(), 50);
      const timer2 = setTimeout(() => map.invalidateSize(), 200);
      const timer3 = setTimeout(() => map.invalidateSize(), 500);

      // ResizeObserver
      let ro: ResizeObserver | undefined;
      if (window.ResizeObserver && mapContainerRef.current) {
        ro = new ResizeObserver(() => {
          if (mapInstanceRef.current) mapInstanceRef.current.invalidateSize();
        });
        ro.observe(mapContainerRef.current);
      }
      return () => {
        clearTimeout(timer1); clearTimeout(timer2); clearTimeout(timer3);
        ro?.disconnect();
        map.remove();
        mapInstanceRef.current = null;
        markersLayerRef.current = null;
        routeLayerRef.current = null;
      };
    }
  }, []);

  // Update Markers, Polylines and Bounds whenever activePredictions or selectedLine changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    const markersLayer = markersLayerRef.current;
    if (!map || !markersLayer) return;

    markersLayer.clearLayers();
    if (routeLayerRef.current) {
      map.removeLayer(routeLayerRef.current);
      routeLayerRef.current = null;
    }

    const boundsPoints: [number, number][] = [];

    // No shapes are available: never invent route geometry.
    // 2. Draw Stop Markers (when a line is selected)
    {
      mappedStops.forEach((stop) => {
        boundsPoints.push([stop.lat, stop.lon]);
        const stopHtml = `
          <div style="
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #FFFFFF;
            border: 3px solid #8E001C;
            box-shadow: 0 2px 5px rgba(0,0,0,0.25);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 9px;
            font-weight: 800;
            color: #8E001C;
          ">
            ${escapeHtml(stop.stopSeq || '•')}
          </div>
        `;

        const stopIcon = L.divIcon({
          className: 'transit-stop-pin',
          html: stopHtml,
          iconSize: [20, 20],
          iconAnchor: [10, 10],
        });

        const stopMarker = L.marker([stop.lat, stop.lon], { icon: stopIcon });
        stopMarker.bindPopup(`
          <div style="font-family: inherit; font-size: 12px;">
            <div style="font-size: 10px; font-weight: 700; color: #6B7280; text-transform: uppercase;">
              ${language === 'it' ? 'Fermata' : 'Stop'} #${escapeHtml(stop.stopSeq || '')}
            </div>
            <div style="font-weight: 800; color: #111827; margin-top: 2px;">
              ${escapeHtml(stop.name)}
            </div>
            <div style="font-size: 10px; color: #6B7280; margin-top: 2px;">
              ID: <code>${escapeHtml(stop.stopId)}</code>
            </div>
          </div>
        `);
        markersLayer.addLayer(stopMarker);
      });
    }

    // 3. Draw Vehicle Markers across Rome
    activePredictions.forEach((veh, idx) => {
      const stopInfo = stopDetails(veh);
      if (!stopInfo) return;

      if (!Number.isFinite(veh.vehicle_lat) || !Number.isFinite(veh.vehicle_lon)) return;
      const offsetLat = veh.vehicle_lat!;
      const offsetLon = veh.vehicle_lon!;
      boundsPoints.push([offsetLat, offsetLon]);

      const isTram = veh.route_type === 0;
      const isMajor = veh.major_delay_probability >= 0.35;
      const isModerate = !isMajor && (veh.major_delay_probability >= 0.2 || (veh.current_arrival_delay_seconds || 0) >= 120);

      const statusDotColor = isMajor ? '#8E001C' : isModerate ? '#FFB300' : '#10B981';
      const isCurrentSelected = selectedVehicle?.trip_id === veh.trip_id;

      const vehicleHtml = `
        <div style="
          background: ${isCurrentSelected ? '#8E001C' : '#111827'};
          color: #FFFFFF;
          padding: 3px 7px;
          border-radius: 6px;
          border: 2px solid ${isCurrentSelected ? '#FFB300' : statusDotColor};
          box-shadow: 0 4px 10px rgba(0,0,0,0.35);
          font-size: 11px;
          font-weight: 800;
          font-family: monospace;
          white-space: nowrap;
          display: flex;
          align-items: center;
          gap: 5px;
          transform: ${isCurrentSelected ? 'scale(1.15)' : 'scale(1)'};
          transition: transform 0.15s ease;
          cursor: pointer;
        ">
          <span style="
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: ${statusDotColor};
            box-shadow: 0 0 4px ${statusDotColor};
          "></span>
          <span>${escapeHtml(veh.route_id)}</span>
        </div>
      `;

      const vehicleIcon = L.divIcon({
        className: 'transit-vehicle-pin',
        html: vehicleHtml,
        iconSize: [44, 24],
        iconAnchor: [22, 12],
      });

      const vehMarker = L.marker([offsetLat, offsetLon], { icon: vehicleIcon });

      vehMarker.on('click', () => {
        onSelectVehicle(veh);
        if (veh.route_id && veh.route_id !== selectedLine) {
          onSelectLine(veh.route_id);
        }
      });

      markersLayer.addLayer(vehMarker);
    });

    // Auto-fit bounds if we have points and a line is selected
    if (boundsPoints.length > 0 && selectedLine) {
      const bounds = L.latLngBounds(boundsPoints);
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    } else if (!selectedLine && boundsPoints.length > 0) {
      // Zoom out to show full Rome central area
      map.setView([41.8958, 12.4825], 13);
    }
  }, [activePredictions, mappedStops, selectedLine, selectedVehicle, language, onSelectVehicle, onSelectLine]);

  const formatDelay = (seconds: number | null | undefined) => {
    if (seconds === null || seconds === undefined) return '0s';
    const abs = Math.abs(seconds);
    const mins = Math.floor(abs / 60);
    const secs = Math.round(abs % 60);
    const sign = seconds < 0 ? '-' : '+';
    if (mins === 0) return `${sign}${secs}s`;
    return `${sign}${mins}m ${secs}s`;
  };

  return (
    <div className="mb-8">
      <p role="note" className="text-xs text-[#4B5563] mb-2">{language === 'it'
        ? 'Coordinate delle fermate da GTFS statico. Posizioni veicolo e shapes non disponibili; nessuna posizione o geometria simulata.'
        : 'Stop coordinates from static GTFS. Vehicle positions and shapes unavailable; no simulated positions or geometry.'}</p>
      {/* Home Split Canvas: Large Map on Left + Synchronized Transport Panel on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-stretch">
        {/* LEFT: Central Leaflet Map (7 or 8 columns on large screens) */}
        <div className="lg:col-span-8 bg-white rounded-xl border border-[#E5E7EB] shadow-xs overflow-hidden flex flex-col relative h-[480px] sm:h-[560px]">
          {/* Map Top Bar Overlay */}
          <div className="absolute top-3 left-3 right-3 z-20 flex flex-wrap items-center justify-between gap-2 pointer-events-none">
            {/* Active Mode Filter & Title */}
            <div className="bg-white/95 backdrop-blur-md px-3 py-1.5 rounded-lg border border-[#E5E7EB] shadow-xs flex items-center space-x-2 pointer-events-auto">
              <span className="w-2.5 h-2.5 rounded-full bg-[#8E001C] animate-pulse"></span>
              <span className="font-extrabold text-xs text-[#111827]">
                {selectedLine
                  ? `${language === 'it' ? 'Linea' : 'Route'} ${selectedLine}`
                  : language === 'it'
                  ? 'Mappa delle fermate'
                  : 'Stop Map'}
              </span>
              <span className="text-[#9CA3AF]">•</span>
              <span className="font-mono text-xs font-bold text-[#8E001C]">
                {activePredictions.length} {language === 'it' ? 'osservazioni' : 'observations'}
              </span>
            </div>

            {/* Reset / All Network Button (if filtered) */}
            {selectedLine && (
              <button
                onClick={() => {
                  onSelectLine(null);
                  onSelectVehicle(null);
                }}
                className="bg-white/95 backdrop-blur-md px-3 py-1.5 rounded-lg border border-[#8E001C] text-[#8E001C] font-bold text-xs hover:bg-[#FDF2F4] transition-colors shadow-xs flex items-center space-x-1.5 pointer-events-auto cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>{language === 'it' ? 'Mostra tutta la rete' : 'Show entire network'}</span>
              </button>
            )}

            {/* Mode Filter Pills */}
            <div className="bg-white/95 backdrop-blur-md p-1 rounded-lg border border-[#E5E7EB] shadow-xs flex items-center space-x-1 pointer-events-auto text-xs font-bold">
              <button
                onClick={() => onSetModeFilter('all')}
                className={`px-2 py-0.5 rounded transition-all cursor-pointer ${
                  modeFilter === 'all'
                    ? 'bg-[#111827] text-white shadow-2xs'
                    : 'text-[#4B5563] hover:text-[#111827]'
                }`}
              >
                {t.search.modes.all}
              </button>
              <button
                onClick={() => onSetModeFilter('bus')}
                className={`px-2 py-0.5 rounded transition-all cursor-pointer ${
                  modeFilter === 'bus'
                    ? 'bg-[#8E001C] text-white shadow-2xs'
                    : 'text-[#4B5563] hover:text-[#111827]'
                }`}
              >
                {t.search.modes.bus}
              </button>
              <button
                onClick={() => onSetModeFilter('tram')}
                className={`px-2 py-0.5 rounded transition-all cursor-pointer ${
                  modeFilter === 'tram'
                    ? 'bg-[#00703C] text-white shadow-2xs'
                    : 'text-[#4B5563] hover:text-[#111827]'
                }`}
              >
                {t.search.modes.tram}
              </button>
            </div>
          </div>

          {/* Leaflet DOM Node */}
          <div ref={mapContainerRef} className="w-full h-full" />

          {/* Map Legend Overlay at Bottom-Left */}
          <div className="absolute bottom-3 left-3 z-20 bg-white/95 backdrop-blur-md px-3 py-1.5 rounded-lg border border-[#E5E7EB] shadow-xs flex items-center space-x-3 text-[11px] text-[#4B5563]">
            <span className="flex items-center space-x-1">
              <span className="w-2 h-2 rounded-full bg-[#10B981]"></span>
              <span>{t.currentSituation.statuses.normal}</span>
            </span>
            <span className="flex items-center space-x-1">
              <span className="w-2 h-2 rounded-full bg-[#FFB300]"></span>
              <span>{t.currentSituation.statuses.moderateDelay}</span>
            </span>
            <span className="flex items-center space-x-1">
              <span className="w-2 h-2 rounded-full bg-[#8E001C]"></span>
              <span>{t.currentSituation.statuses.majorDelay}</span>
            </span>
          </div>
        </div>

        {/* RIGHT: Synchronized Transport Intelligence Panel (4 or 5 columns on desktop) */}
        <div className="lg:col-span-4 flex flex-col justify-between space-y-3">
          {/* Active Vehicle Telemetry Card (If a vehicle is selected from the map or list) */}
          {selectedVehicle ? (
            <div className="bg-white rounded-xl border-2 border-[#8E001C] p-4 shadow-sm animate-in fade-in duration-150">
              <div className="flex items-center justify-between pb-2.5 border-b border-[#E5E7EB]">
                <div className="flex items-center space-x-2">
                  <span className="inline-flex items-center justify-center min-w-[34px] px-2 py-0.5 rounded font-black text-xs text-white bg-[#8E001C]">
                    {selectedVehicle.route_id}
                  </span>
                  <div>
                    <h3 className="font-extrabold text-xs text-[#111827]">
                      {selectedVehicle.vehicle_id || 'ATAC'}
                    </h3>
                    <span className="text-[10px] text-[#6B7280]">
                      {language === 'it' ? 'Corsa in transito' : 'Active vehicle'}
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => onSelectVehicle(null)}
                  className="text-[#9CA3AF] hover:text-[#111827] p-1 rounded cursor-pointer"
                  title={language === 'it' ? 'Chiudi dettaglio' : 'Close detail'}
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Vehicle Detail Focus */}
              <div className="mt-3 space-y-2.5 text-xs">
                <div>
                  <span className="text-[10px] text-[#6B7280] block">
                    {t.currentSituation.table.nextStop}:
                  </span>
                  <div className="font-bold text-sm text-[#111827] flex items-center space-x-1.5 mt-0.5">
                    <MapPin className="w-3.5 h-3.5 text-[#8E001C] shrink-0" />
                    <span className="truncate">
                      {selectedVehicle.stop_name ||

                        `Fermata ${selectedVehicle.stop_id}`}
                    </span>
                  </div>
                  <span className="text-[10px] text-[#6B7280]">
                    {language === 'it' ? 'Sequenza fermata' : 'Stop sequence'} #{selectedVehicle.stop_sequence || '—'}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-[#F3F4F6]">
                  <div className="p-2 bg-[#F8F9FA] rounded border border-[#E5E7EB]">
                    <span className="text-[10px] text-[#6B7280] block">
                      {t.currentSituation.table.observedDelay}:
                    </span>
                    <span
                      className={`font-mono text-base font-extrabold ${
                        (selectedVehicle.current_arrival_delay_seconds || 0) >= 300
                          ? 'text-[#8E001C]'
                          : 'text-[#111827]'
                      }`}
                    >
                      {formatDelay(selectedVehicle.current_arrival_delay_seconds)}
                    </span>
                  </div>

                  <div className="p-2 bg-[#F8F9FA] rounded border border-[#E5E7EB]">
                    <span className="text-[10px] text-[#6B7280] block">
                      {t.currentSituation.table.majorDelayRisk}:
                    </span>
                    <span className="font-mono text-base font-extrabold text-[#111827]">
                      {(selectedVehicle.major_delay_probability * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>

                {/* Risk Progress Bar */}
                <div>
                  <div className="relative w-full h-2 bg-[#E5E7EB] rounded-full overflow-hidden">
                    <div
                      className={`h-full ${
                        selectedVehicle.major_delay_probability >= 0.35
                          ? 'bg-[#8E001C]'
                          : selectedVehicle.major_delay_probability >= 0.2
                          ? 'bg-[#FFB300]'
                          : 'bg-[#10B981]'
                      }`}
                      style={{
                        width: `${Math.min(100, selectedVehicle.major_delay_probability * 100)}%`,
                      }}
                    ></div>
                  </div>
                </div>

                {selectedVehicle.vehicle_speed !== undefined && (
                  <div className="flex items-center justify-between text-[11px] text-[#6B7280] pt-1">
                    <span>
                      {language === 'it' ? 'Velocità istantanea:' : 'Current speed:'}{' '}
                      <strong className="text-[#111827]">{selectedVehicle.vehicle_speed.toFixed(1)} km/h</strong>
                    </span>
                    {selectedVehicle.distance_to_next_stop_meters !== undefined && (
                      <span>
                        {language === 'it' ? 'Distanza:' : 'Distance:'}{' '}
                        <strong className="text-[#111827]">{selectedVehicle.distance_to_next_stop_meters}m</strong>
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* If no single vehicle is selected, show line focus or network critical lines */
            <div className="bg-white rounded-xl border border-[#E5E7EB] p-4 sm:p-5 shadow-xs flex-1 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-extrabold text-[#111827] flex items-center space-x-1.5">
                    <AlertTriangle className="w-4 h-4 text-[#8E001C]" />
                    <span>
                      {selectedLine
                        ? `${language === 'it' ? 'Mezzi sulla linea' : 'Vehicles on route'} ${selectedLine}`
                        : t.visualizations.criticalLinesTitle}
                    </span>
                  </h3>
                  <span className="text-[10px] font-bold text-[#8E001C] bg-[#FDF2F4] px-1.5 py-0.5 rounded">
                    {language === 'it' ? 'Persistito' : 'Persisted'}
                  </span>
                </div>
                <p className="text-xs text-[#6B7280] mb-3 leading-relaxed">
                  {selectedLine
                    ? language === 'it'
                      ? 'Clicca su un veicolo sulla mappa o nell’elenco per esaminarne la telemetria.'
                      : 'Click any vehicle pin on the map or list below to inspect arrival telemetry.'
                    : t.visualizations.criticalLinesSubtitle}
                </p>
              </div>

              {/* Dynamic Content: If line selected, show its vehicles list; else show critical lines ranking */}
              {selectedLine ? (
                <div className="space-y-1.5 max-h-[300px] overflow-y-auto pr-1">
                  {activePredictions.map((veh) => (
                    <button
                      key={veh.trip_id}
                      onClick={() => onSelectVehicle(veh)}
                      role="button" tabIndex={0}
                      onKeyDown={(event) => { if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); onSelectVehicle(veh); } }}
                      className="w-full text-left p-2 rounded-lg border border-[#E5E7EB] hover:border-[#8E001C] hover:bg-[#FDF2F4] transition-colors flex items-center justify-between text-xs cursor-pointer group"
                    >
                      <div>
                        <span className="font-mono font-bold text-[#111827] block">
                          {veh.vehicle_id || 'ATAC'}
                        </span>
                        <span className="text-[11px] text-[#6B7280] truncate max-w-[170px] block">
                          {veh.stop_name || veh.stop_id}
                        </span>
                      </div>

                      <div className="text-right">
                        <span
                          className={`font-mono font-bold text-xs ${
                            (veh.current_arrival_delay_seconds || 0) >= 300
                              ? 'text-[#8E001C]'
                              : 'text-[#111827]'
                          }`}
                        >
                          {formatDelay(veh.current_arrival_delay_seconds)}
                        </span>
                        <span className="text-[10px] text-[#6B7280] block">
                          {(veh.major_delay_probability * 100).toFixed(0)}% risk
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="space-y-2">
                  {criticalLines.map((item) => (
                    <button
                      key={item.route}
                      onClick={() => onSelectLine(item.route)}
                      className="w-full text-left p-2 rounded-lg hover:bg-[#FDF2F4] transition-all group flex flex-col space-y-1 border border-transparent hover:border-[#F1C3CA] cursor-pointer"
                    >
                      <div className="flex items-center justify-between text-xs w-full">
                        <div className="flex items-center space-x-2">
                          <span
                            className={`px-2 py-0.5 rounded font-mono font-black text-xs text-white ${
                              item.mode === 'Tram' ? 'bg-[#00703C]' : 'bg-[#8E001C]'
                            }`}
                          >
                            {item.route}
                          </span>
                          <span className="font-bold text-[#111827] text-xs">
                            {item.mode} {item.route}
                          </span>
                          <span className="text-[#6B7280] text-[11px]">
                            • {item.major}/{item.total} {language === 'it' ? 'in ritardo' : 'delayed'}
                          </span>
                        </div>

                        <div className="flex items-center space-x-1">
                          <span className="font-mono font-extrabold text-[#111827]">
                            {item.rate.toFixed(0)}%
                          </span>
                          <ArrowRight className="w-3.5 h-3.5 text-[#9CA3AF] group-hover:text-[#8E001C] group-hover:translate-x-0.5 transition-all" />
                        </div>
                      </div>

                      <div className="w-full h-1.5 bg-[#F3F4F6] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-[#8E001C] rounded-full transition-all duration-300"
                          style={{ width: `${Math.min(100, item.rate)}%` }}
                        ></div>
                      </div>
                    </button>
                  ))}
                </div>
              )}

              <div className="pt-3 mt-3 border-t border-[#F3F4F6] text-[11px] text-[#6B7280]">
                {selectedLine
                  ? language === 'it'
                    ? 'Visualizzazione sincronizzata con la mappa di Roma.'
                    : 'Map and vehicle details are synchronized.'
                  : t.visualizations.criticalLinesClickHint}
              </div>
            </div>
          )}

          {/* Quick Line Search / Switcher integrated in the sidebar */}
          <div className="bg-[#F8F9FA] rounded-xl border border-[#E5E7EB] p-3 text-xs flex items-center justify-between">
            <span className="text-[#6B7280] font-medium">
              {language === 'it' ? 'Linee nei dati correnti:' : 'Routes in current data:'}
            </span>
            <div className="flex flex-wrap items-center gap-1">
              {Array.from(new Set(predictions.map(p => p.route_id).filter((route): route is string => Boolean(route)))).slice(0, 7).map((r) => (
                <button
                  key={r}
                  onClick={() => onSelectLine(selectedLine === r ? null : r)}
                  className={`px-1.5 py-0.5 rounded font-mono font-bold text-[11px] transition-all cursor-pointer ${
                    selectedLine === r
                      ? 'bg-[#8E001C] text-white shadow-xs'
                      : 'bg-white border border-[#E5E7EB] text-[#374151] hover:border-[#8E001C]'
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
