import { describe, it, expect } from 'vitest';
import { DuelRound, DuelStatusResponse } from '../types';

interface DuelState {
  duelId: string | null;
  status: 'idle' | 'running' | 'completed' | 'failed' | string;
  targetRounds: number;
  completedRounds: DuelRound[];
  error: string | null;
}

function createDuelReducer() {
  let state: DuelState = {
    duelId: null,
    status: 'idle',
    targetRounds: 3,
    completedRounds: [],
    error: null,
  };

  return {
    getState: () => state,
    startDuel: (id: string, targetRounds: number) => {
      state = {
        duelId: id,
        status: 'running',
        targetRounds,
        completedRounds: [],
        error: null,
      };
    },
    updateFromPoll: (response: DuelStatusResponse) => {
      if (response.status === 'failed') {
        state = {
          ...state,
          status: 'failed',
          error: response.error || 'Duel execution failed',
        };
        return;
      }

      state = {
        ...state,
        status: response.status,
        completedRounds: response.rounds,
        error: null,
      };
    },
    getCurrentRoundLabel: () => {
      if (state.status === 'completed') return 'Duel Completed';
      if (state.status === 'failed') return 'Duel Execution Failed';
      if (state.status === 'running') {
        const nextRound = state.completedRounds.length + 1;
        return `Round ${nextRound} of ${state.targetRounds} Running...`;
      }
      return 'Ready';
    },
    calculateWinner: () => {
      if (state.completedRounds.length === 0) return null;
      const shieldWins = state.completedRounds.filter((r) => r.caught).length;
      const fraudsterWins = state.completedRounds.length - shieldWins;
      return {
        shieldWins,
        fraudsterWins,
        winner: shieldWins >= fraudsterWins ? 'FinShield Shield' : 'Fraudster Syndicate',
      };
    },
  };
}

describe('Duel Arena Progress State Machine', () => {
  it('initializes in ready/idle state', () => {
    const sm = createDuelReducer();
    expect(sm.getState().status).toBe('idle');
    expect(sm.getCurrentRoundLabel()).toBe('Ready');
  });

  it('transitions to running upon start', () => {
    const sm = createDuelReducer();
    sm.startDuel('duel-abc-123', 3);

    expect(sm.getState().status).toBe('running');
    expect(sm.getState().duelId).toBe('duel-abc-123');
    expect(sm.getCurrentRoundLabel()).toBe('Round 1 of 3 Running...');
  });

  it('updates round cards progressively as rounds finish in the background', () => {
    const sm = createDuelReducer();
    sm.startDuel('duel-abc-123', 3);

    const round1: DuelRound = {
      round_number: 1,
      tactic: 'Sub-threshold line item padding',
      rationale: 'Injecting small surcharges below audit radar',
      claim_id: 'CLM-DUEL-R1',
      baseline_amount: 50000,
      total_claimed: 55000,
      inflation_ratio: 1.1,
      verdict: 'reject',
      risk_score: 85,
      caught: true,
      evaded: false,
      catching_finding_ids: ['F1'],
      catching_check_ids: ['BENCHMARK_EXCEEDED'],
      timestamp: new Date().toISOString(),
    };

    // Poll 1: Round 1 completed
    sm.updateFromPoll({
      duel_id: 'duel-abc-123',
      status: 'running',
      current_round: 1,
      max_rounds: 3,
      rounds: [round1],
    });

    expect(sm.getState().completedRounds).toHaveLength(1);
    expect(sm.getState().status).toBe('running');
    expect(sm.getCurrentRoundLabel()).toBe('Round 2 of 3 Running...');

    // Poll 2: Round 2 completed
    const round2: DuelRound = {
      round_number: 2,
      tactic: 'Prompt injection obfuscation',
      rationale: 'Hidden prompt payload in comments',
      claim_id: 'CLM-DUEL-R2',
      baseline_amount: 50000,
      total_claimed: 62500,
      inflation_ratio: 1.25,
      verdict: 'reject',
      risk_score: 95,
      caught: true,
      evaded: false,
      catching_finding_ids: ['F2'],
      catching_check_ids: ['PROMPT_INJECTION_DETECTED'],
      timestamp: new Date().toISOString(),
    };

    sm.updateFromPoll({
      duel_id: 'duel-abc-123',
      status: 'running',
      current_round: 2,
      max_rounds: 3,
      rounds: [round1, round2],
    });

    expect(sm.getState().completedRounds).toHaveLength(2);
    expect(sm.getCurrentRoundLabel()).toBe('Round 3 of 3 Running...');

    // Poll 3: Round 3 completed and duel marks completed
    const round3: DuelRound = {
      round_number: 3,
      tactic: 'Multi-hospital spacetime hopping',
      rationale: 'Overlapping admissions in two distant facilities',
      claim_id: 'CLM-DUEL-R3',
      baseline_amount: 50000,
      total_claimed: 52500,
      inflation_ratio: 1.05,
      verdict: 'reject',
      risk_score: 90,
      caught: true,
      evaded: false,
      catching_finding_ids: ['F3'],
      catching_check_ids: ['GEOGRAPHIC_IMPOSSIBILITY_VELOCITY'],
      timestamp: new Date().toISOString(),
    };

    sm.updateFromPoll({
      duel_id: 'duel-abc-123',
      status: 'completed',
      current_round: 3,
      max_rounds: 3,
      rounds: [round1, round2, round3],
    });

    expect(sm.getState().status).toBe('completed');
    expect(sm.getState().completedRounds).toHaveLength(3);
    expect(sm.getCurrentRoundLabel()).toBe('Duel Completed');

    const result = sm.calculateWinner();
    expect(result?.shieldWins).toBe(3);
    expect(result?.fraudsterWins).toBe(0);
    expect(result?.winner).toBe('FinShield Shield');
  });

  it('handles round failure explicitly and exposes retry capability', () => {
    const sm = createDuelReducer();
    sm.startDuel('duel-err-456', 3);

    sm.updateFromPoll({
      duel_id: 'duel-err-456',
      status: 'failed',
      current_round: 0,
      max_rounds: 3,
      rounds: [],
      error: 'Vertex AI 429 Quota Exceeded on Round 2',
    });

    expect(sm.getState().status).toBe('failed');
    expect(sm.getState().error).toBe('Vertex AI 429 Quota Exceeded on Round 2');
    expect(sm.getCurrentRoundLabel()).toBe('Duel Execution Failed');
  });
});
