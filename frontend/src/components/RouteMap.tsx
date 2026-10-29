import React, { useEffect, useRef, useMemo, useState } from 'react';
import L from 'leaflet';
import {api} from '../api/client';
import 'leaflet/dist/leaflet.css';
import { CurrentPrediction } from '../types/api';
import { stopDetails, escapeHtml } from '../api/geography';
import { Translations, Language } from '../i18n/translations';
import { MapPin, Info, AlertTriangle, CheckCircle2, RotateCcw } from 'lucide-react';

interface RouteMapProps {
  routeId: string;
  vehicles: CurrentPrediction[];
  selectedVehicleId?: string | null;
  onSelectVehicle?: (vehicle: CurrentPrediction) => void;
  t: Translations;
  language: Language;
}

export const RouteMap: React.FC<RouteMapProps> = ({
  routeId,
  vehicles,
  selectedVehicleId,
  onSelectVehicle,
  t,
  language,
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const polylineLayerRef = useRef<L.Polyline | null>(null);
  const vehicleMarkersMapRef = useRef<Map<string, L.Marker>>(new Map());

  const [geometry,setGeometry]=useState<[number,number][]>([]);
  const trip=vehicles.find(v=>v.vehicle_id===selectedVehicleId)?.trip_id ?? vehicles[0]?.trip_id;
  useEffect(()=>{
    let active=true;setGeometry([]);
    if(trip)void api.getRouteMap(routeId,trip).then(points=>{if(active)setGeometry(points);}).catch(()=>{if(active)setGeometry([]);});
    return ()=>{active=false;};
  },[routeId,trip]);

  // Extract stops that belong to this route with verified coordinates from the dataset
  const stopsWithCoords = useMemo(() => {
    const list: {
      stopId: string;
      name: string;
      lat: number;
      lon: number;
      stopSeq?: number;
      vehiclesApproaching: CurrentPrediction[];
    }[] = [];

    const seenStops = new Set<string>();

    vehicles.forEach((v) => {
      if (v.stop_id && !seenStops.has(v.stop_id)) {
        seenStops.add(v.stop_id);
        const details = stopDetails(v);
        if (details) {
          list.push({
            stopId: v.stop_id,
            name: v.stop_name || details.name,
            lat: details.lat,
            lon: details.lon,
            stopSeq: v.stop_sequence,
            vehiclesApproaching: vehicles.filter((veh) => veh.stop_id === v.stop_id),
          });
        }
      }
    });

    // Sort by stop sequence number
    list.sort((a, b) => (a.stopSeq || 0) - (b.stopSeq || 0));
    return list;
  }, [vehicles]);

  const hasCoordinates = stopsWithCoords.length > 0;

  // Format delay string
  const formatDelay = (seconds: number | null | undefined) => {
    if (seconds === null || seconds === undefined) return '0s';
    const abs = Math.abs(seconds);
    const mins = Math.floor(abs / 60);
    const secs = Math.round(abs % 60);
    const sign = seconds < 0 ? '-' : '+';
    if (mins === 0) return `${sign}${secs}s`;
    return `${sign}${mins}m ${secs}s`;
  };

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current || !hasCoordinates) return;

    // Destroy existing instance if container changed or remounted
    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
    }

    const defaultCenter: [number, number] = [stopsWithCoords[0].lat, stopsWithCoords[0].lon];

    const map = L.map(mapContainerRef.current, {
      center: defaultCenter,
      zoom: 13,
      zoomControl: true,
      attributionControl: true,
      scrollWheelZoom: true,
    });

    // Official OpenStreetMap standard tile layer
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    const markersGroup = L.layerGroup().addTo(map);
    markersLayerRef.current = markersGroup;
    mapInstanceRef.current = map;

    // Call invalidateSize across multiple ticks to guarantee tiles render when DOM settles
    const timer1 = setTimeout(() => {
      map.invalidateSize();
    }, 50);

    const timer2 = setTimeout(() => {
      map.invalidateSize();
    }, 200);

    const timer3 = setTimeout(() => {
      map.invalidateSize();
    }, 500);

    // Resize observer to handle dynamic layout shifts
    let resizeObserver: ResizeObserver | null = null;
    if (window.ResizeObserver && mapContainerRef.current) {
      resizeObserver = new ResizeObserver(() => {
        if (mapInstanceRef.current) {
          mapInstanceRef.current.invalidateSize();
        }
      });
      resizeObserver.observe(mapContainerRef.current);
    }

    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
      if (resizeObserver) resizeObserver.disconnect();
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [hasCoordinates]);

  // Update markers, polyline and bounds whenever vehicles/route or selection changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    const markersGroup = markersLayerRef.current;
    if (!map || !markersGroup || !hasCoordinates) return;

    markersGroup.clearLayers();
    if (polylineLayerRef.current) {
      map.removeLayer(polylineLayerRef.current);
      polylineLayerRef.current = null;
    }
    vehicleMarkersMapRef.current.clear();

    const isTram = vehicles[0]?.route_type === 0;
    const routeColor = isTram ? '#00703C' : '#8E001C';
    const boundsPoints: [number, number][] = [];

    // Only the exact static route/trip/shape join is drawable; never connect observed stops.
    if(geometry.length>1){
      polylineLayerRef.current=L.polyline(geometry,{color:routeColor,weight:4,opacity:.7}).addTo(map);
      boundsPoints.push(...geometry);
    }
    // 2. Render verified stop markers
    stopsWithCoords.forEach((stop) => {
      boundsPoints.push([stop.lat, stop.lon]);

      const stopHtml = `
        <div style="
          width: 24px;
          height: 24px;
          border-radius: 50%;
          background: #FFFFFF;
          border: 3px solid ${routeColor};
          box-shadow: 0 2px 8px rgba(0,0,0,0.3);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 10px;
          font-weight: 800;
          color: ${routeColor};
          font-family: monospace;
        ">
          ${escapeHtml(stop.stopSeq || '•')}
        </div>
      `;

      const stopIcon = L.divIcon({
        className: 'custom-stop-marker',
        html: stopHtml,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      });

      const stopMarker = L.marker([stop.lat, stop.lon], { icon: stopIcon });

      const approachingHtml = stop.vehiclesApproaching
        .map(
          (v) => `
          <div style="margin-top: 4px; padding: 4px 6px; background: #F8F9FA; border-radius: 4px; border-left: 3px solid ${
            v.major_delay_probability >= 0.35 ? '#8E001C' : '#10B981'
          };">
            <div style="display: flex; justify-content: space-between; font-weight: 700; font-size: 11px;">
              <span>${v.vehicle_id || 'ATAC'}</span>
              <span style="color: ${v.major_delay_probability >= 0.35 ? '#8E001C' : '#111827'}; font-family: monospace;">
                ${formatDelay(v.current_arrival_delay_seconds)}
              </span>
            </div>
            <div style="font-size: 10px; color: #6B7280; margin-top: 1px;">
              ${language === 'it' ? 'Prob. ritardo ≥5m:' : 'Major delay risk:'} <strong>${(
            v.major_delay_probability * 100
          ).toFixed(1)}%</strong>
            </div>
          </div>
        `
        )
        .join('');

      stopMarker.bindPopup(`
        <div style="font-family: inherit; min-width: 180px;">
          <div style="font-size: 10px; font-weight: 700; color: #6B7280; text-transform: uppercase;">
            ${language === 'it' ? 'Fermata monitorata' : 'Monitored stop'} #${escapeHtml(stop.stopSeq || '')}
          </div>
          <div style="font-size: 13px; font-weight: 800; color: #111827; margin-top: 2px;">
            ${escapeHtml(stop.name)}
          </div>
          <div style="font-size: 10px; color: #6B7280; margin-top: 1px;">
            ID fermata GTFS: <code>${escapeHtml(stop.stopId)}</code>
          </div>
          ${
            stop.vehiclesApproaching.length > 0
              ? `<div style="margin-top: 8px; font-size: 11px; font-weight: 700; color: #374151;">
                   ${language === 'it' ? 'Mezzi diretti a questa fermata:' : 'Vehicles en route to stop:'}
                 </div>
                 ${approachingHtml}`
              : ''
          }
        </div>
      `);

      markersGroup.addLayer(stopMarker);
    });

    // Vehicle positions are unavailable to this identity. No vehicle markers are created.

    // Auto-fit bounds to include all stops and vehicles
    if (boundsPoints.length > 0) {
      const bounds = L.latLngBounds(boundsPoints);
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    }

    // Invalidate size once more after adding layers
    setTimeout(() => {
      if (mapInstanceRef.current) mapInstanceRef.current.invalidateSize();
    }, 100);
  }, [hasCoordinates, stopsWithCoords, vehicles, routeId, selectedVehicleId, language, onSelectVehicle,geometry]);

  // Center on selected vehicle if clicked from sidebar
  useEffect(() => {
    if (!selectedVehicleId || !mapInstanceRef.current) return;
    const marker = vehicleMarkersMapRef.current.get(selectedVehicleId);
    if (marker) {
      const latLng = marker.getLatLng();
      mapInstanceRef.current.setView(latLng, 15, { animate: true });
      marker.openPopup();
    }
  }, [selectedVehicleId]);

  // If no verified coordinates are available, show the strict requested placeholder
  if (!hasCoordinates) {
    return (
      <div className="bg-[#F8F9FA] border-2 border-dashed border-[#D1D5DB] rounded-xl p-8 text-center flex flex-col items-center justify-center min-h-[360px]">
        <div className="w-12 h-12 rounded-full bg-[#E5E7EB] flex items-center justify-center text-[#6B7280] mb-3">
          <MapPin className="w-6 h-6" />
        </div>
        <h4 className="text-sm font-bold text-[#111827] max-w-md">
          {t.lineDetail.noCoordinatesPlaceholder}
        </h4>
        <p className="text-xs text-[#6B7280] mt-2 max-w-md leading-relaxed">
          {language === 'it'
            ? 'I dati per questa linea sono attualmente registrati a livello tabellare senza coordinate geografiche collegate nello stream.'
            : 'Operational telemetry for this route is currently reported at the tabular feed level without geocoded stop positions.'}
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Map Header / Legend Strip */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 mb-2.5 border-b border-[#E5E7EB]">
        <div>
          <h4 className="text-xs font-extrabold uppercase tracking-wider text-[#111827] flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#8E001C]"></span>
            <span>{t.lineDetail.routeMapTitle}</span>
          </h4>
          <p className="text-[11px] text-[#6B7280]">
            {t.lineDetail.routeMapSubtitle}
          </p>
        </div>

        {/* Legend */}
        <div className="flex items-center space-x-3 text-[11px] text-[#4B5563]">
          <span className="flex items-center space-x-1">
            <span className="w-2.5 h-2.5 rounded-full border-2 border-[#8E001C] bg-white"></span>
            <span>{stopsWithCoords.length} {t.lineDetail.stopsOnMap}</span>
          </span>
          <span className="flex items-center space-x-1">
            <span className="w-2.5 h-2.5 rounded-xs bg-[#111827]"></span>
            <span>{vehicles.filter(v => Number.isFinite(v.vehicle_lat) && Number.isFinite(v.vehicle_lon)).length} {t.lineDetail.vehiclesOnMap}</span>
          </span>
        </div>
      </div>

      {/* Verified Data Badge & Polyline Disclosure (Strict compliance with no-fabrication rule) */}
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-[10px] text-[#6B7280] bg-[#F8F9FA] px-2.5 py-1 rounded border border-[#E5E7EB]">
        <span className="flex items-center space-x-1 text-[#065F46] font-medium">
          <CheckCircle2 className="w-3 h-3 text-[#10B981]" />
          <span>
            {language === 'it'
              ? 'Fermate reali da GTFS statico; posizioni veicolo non disponibili'
              : 'Real static GTFS stops; vehicle positions unavailable'}
          </span>
        </span>
        <span className="text-[#9CA3AF]">
          {geometry.length ? language==='it'?'Geometria GTFS statica della corsa selezionata':'Static GTFS geometry for the selected trip' : language==='it'?'Shape non abbinata: solo fermate reali':'No matching shape: real stops only'}
        </span>
      </div>

      {/* Real Map Container with explicit pixel height */}
      <div
        className="relative w-full rounded-xl overflow-hidden border border-[#E5E7EB] shadow-xs flex-1"
        style={{ minHeight: '420px', height: '460px' }}
      >
        <div
          ref={mapContainerRef}
          className="w-full h-full"
          style={{ minHeight: '420px', height: '100%', width: '100%' }}
        />
      </div>
    </div>
  );
};
