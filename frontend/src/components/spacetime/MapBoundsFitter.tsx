import React, { useEffect } from 'react';
import { useMap } from '@vis.gl/react-google-maps';
import { TimelineEvent } from '../../types';

interface MapBoundsFitterProps {
  events: TimelineEvent[];
}

export const MapBoundsFitter: React.FC<MapBoundsFitterProps> = ({ events }) => {
  const map = useMap();

  useEffect(() => {
    if (!map || events.length === 0) return;

    const bounds = new google.maps.LatLngBounds();
    let validCount = 0;

    for (const ev of events) {
      if (ev.lat && ev.lng && (ev.lat !== 0 || ev.lng !== 0)) {
        bounds.extend({ lat: ev.lat, lng: ev.lng });
        validCount++;
      }
    }

    if (validCount > 0) {
      map.fitBounds(bounds, { top: 60, bottom: 60, left: 60, right: 60 });
    }
  }, [map, events]);

  return null;
};
