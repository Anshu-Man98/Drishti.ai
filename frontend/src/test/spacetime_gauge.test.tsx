import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SpeedometerGauge } from '../components/spacetime/SpeedometerGauge';
import { TimelineEvent } from '../types';

describe('Spacetime Stop-to-Leg Mapping & SpeedometerGauge', () => {
  const sampleTimeline: TimelineEvent[] = [
    {
      actor: 'PAT-ROHAN',
      lat: 19.076,
      lng: 72.8777,
      place: 'Mumbai, Maharashtra',
      ts: '2026-10-14T08:00:00Z',
      description: 'Admitted at Mumbai Clinic',
      doc_id: 'CLM-001',
    },
    {
      actor: 'PAT-ROHAN',
      lat: 28.6139,
      lng: 77.209,
      place: 'New Delhi, Delhi',
      ts: '2026-10-14T08:45:00Z', // 45 mins later for ~1150 km distance -> impossible
      description: 'Consultation at Delhi Hospital',
      doc_id: 'CLM-002',
    },
    {
      actor: 'PAT-ROHAN',
      lat: 28.7041,
      lng: 77.1025,
      place: 'Rohini, New Delhi',
      ts: '2026-10-14T14:00:00Z', // ~5 hours later for 15 km distance -> feasible
      description: 'Pharmacy Dispense',
      doc_id: 'CLM-003',
    },
  ];

  function getArrivingLeg(timeline: TimelineEvent[], selectedStopIndex: number) {
    if (timeline.length < 2 || selectedStopIndex === 0) {
      return null;
    }
    const from = timeline[selectedStopIndex - 1];
    const to = timeline[selectedStopIndex];
    return {
      fromIndex: selectedStopIndex - 1,
      toIndex: selectedStopIndex,
      fromCity: from.place.split(',')[0].trim(),
      toCity: to.place.split(',')[0].trim(),
      fromEvent: from,
      toEvent: to,
    };
  }

  it('correctly maps Stop #0 to departure origin with NO arriving leg', () => {
    const leg = getArrivingLeg(sampleTimeline, 0);
    expect(leg).toBeNull();
  });

  it('correctly maps Stop #1 to arriving leg from Stop #0 (Mumbai -> New Delhi)', () => {
    const leg = getArrivingLeg(sampleTimeline, 1);
    expect(leg).not.toBeNull();
    expect(leg?.fromIndex).toBe(0);
    expect(leg?.toIndex).toBe(1);
    expect(leg?.fromCity).toBe('Mumbai');
    expect(leg?.toCity).toBe('New Delhi');
  });

  it('correctly maps Stop #2 to arriving leg from Stop #1 (New Delhi -> Rohini)', () => {
    const leg = getArrivingLeg(sampleTimeline, 2);
    expect(leg).not.toBeNull();
    expect(leg?.fromIndex).toBe(1);
    expect(leg?.toIndex).toBe(2);
    expect(leg?.fromCity).toBe('New Delhi');
    expect(leg?.toCity).toBe('Rohini');
  });

  it('renders SpeedometerGauge with arriving leg banner and feasible road speed', () => {
    render(
      <SpeedometerGauge
        speedKmH={35}
        distanceKm={15}
        availableMinutes={315}
        requiredHours={0.5}
        isImpossible={false}
        fromCity="New Delhi"
        toCity="Rohini"
      />
    );

    // Arriving Leg Banner
    expect(screen.getByText(/Leg: New Delhi → Rohini/i)).toBeInTheDocument();
    expect(screen.getByText(/Required speed: 35 km\/h/i)).toBeInTheDocument();

    // Road Feasible Badge
    expect(screen.getByText(/Road Transit Feasible/i)).toBeInTheDocument();

    // Physics Geodesic Readout
    expect(screen.getByText(/15 km/i)).toBeInTheDocument();
    expect(screen.getAllByText(/315 min/i).length).toBeGreaterThan(0);
  });

  it('renders SpeedometerGauge with IMPOSSIBLE VELOCITY alert for impossible travel leg', () => {
    render(
      <SpeedometerGauge
        speedKmH={1533}
        distanceKm={1150}
        availableMinutes={45}
        requiredHours={3.2}
        isImpossible={true}
        fromCity="Mumbai"
        toCity="New Delhi"
      />
    );

    // Impossible Alert Banner
    expect(screen.getByText(/IMPOSSIBLE VELOCITY/i)).toBeInTheDocument();
    expect(screen.getByText(/Leg: Mumbai → New Delhi/i)).toBeInTheDocument();

    // Physics Explanation
    expect(
      screen.getByText(/Door-to-door transit between Mumbai and New Delhi requires at least/i)
    ).toBeInTheDocument();
  });
});
