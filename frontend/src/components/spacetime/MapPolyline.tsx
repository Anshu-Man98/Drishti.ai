import React, { useEffect } from 'react';
import { useMap } from '@vis.gl/react-google-maps';

interface MapPolylineProps {
  path: Array<{ lat: number; lng: number }>;
  strokeColor: string;
  strokeOpacity?: number;
  strokeWeight?: number;
  geodesic?: boolean;
}

export const MapPolyline: React.FC<MapPolylineProps> = ({
  path,
  strokeColor,
  strokeOpacity = 0.85,
  strokeWeight = 3.5,
  geodesic = true,
}) => {
  const map = useMap();

  useEffect(() => {
    if (!map || path.length < 2) return;

    const polyline = new google.maps.Polyline({
      path,
      strokeColor,
      strokeOpacity,
      strokeWeight,
      geodesic,
      map,
    });

    return () => {
      polyline.setMap(null);
    };
  }, [map, path, strokeColor, strokeOpacity, strokeWeight, geodesic]);

  return null;
};
