export type Compound = "SOFT" | "MEDIUM" | "HARD" | "INTERMEDIATE" | "WET" | "UNKNOWN";
export type TrackStatus = "GREEN" | "YELLOW" | "VSC" | "SC" | "RED";

export interface DriverInfo {
  abbr: string;
  full_name: string;
  team: string;
  team_color: string;
  number: string;
}

export interface RaceSummary {
  id: number;
  year: number;
  round: number;
  event: string;
  circuit: string;
  total_laps: number;
  source: string;
  drivers: DriverInfo[];
}

export interface EventInfo {
  round: number;
  name: string;
  country: string;
  location: string;
  date: string | null;
}

export interface BoardRow {
  position: number;
  driver: string;
  name: string;
  team: string;
  color: string;
  laps: number;
  compound: Compound;
  tyre_age: number;
  stops: number;
  last_lap: number | null;
  in_pit: boolean;
  retired: boolean;
  laps_down: number;
  gap: string;
  interval: string;
  gap_s: number | null;
}

export interface Call {
  lap: number;
  kind: "BOX" | "SC_BOX" | "WINDOW" | "STAY_OUT" | "PLAN" | "UNDERCUT" | "THREAT" | "RACE" | "INFO";
  priority: "high" | "medium" | "low";
  message: string;
  data: Record<string, unknown>;
}

export interface StopInfo {
  lap: number;
  compound: Compound;
}

export interface PlanInfo {
  label: string;
  stops: StopInfo[];
  time: number;
  delta: number;
}

export interface CompoundFit {
  intercept: number;
  deg_per_lap: number;
  deg_quadratic: number;
  laps_observed: number;
  max_stint: number;
}

export interface Frame {
  type: "lap";
  lap: number;
  total_laps: number;
  track_status: TrackStatus;
  leaderboard: BoardRow[];
  focus: {
    driver: string;
    real: {
      position: number | null;
      compound: Compound | null;
      age: number | null;
      lap_time: number | null;
      race_time: number | null;
      stops: StopInfo[];
    };
    shadow: {
      compound: Compound;
      age: number;
      race_time: number;
      stops: StopInfo[];
      pending: StopInfo | null;
      last_lap_time: number | null;
      retired: boolean;
      position: number | null;
      delta: number | null;
      active: boolean;
    };
  };
  calls: Call[];
  plans: PlanInfo[];
  undercut: { rival: string; gap: number; gain: number; on: boolean } | null;
  model: {
    compounds: Record<string, CompoundFit>;
    residual_sd: number;
    laps_used: number;
    pit_loss: number;
    curves: Record<string, { age: number; time: number }[]>;
  };
}

export interface SessionInfo {
  id: string;
  driver: string;
  mode: "auto" | "fixed";
  branch_lap: number;
  fixed_stops: StopInfo[];
  seconds_per_lap: number;
  lap: number;
  paused: boolean;
  finished: boolean;
  race_id: number;
}

export interface Summary {
  driver: string;
  mode: string;
  branch_lap: number;
  final_delta: number | null;
  shadow_position: number | null;
  actual_position: number | null;
  shadow_stops: StopInfo[];
  actual_stops: StopInfo[];
}

export interface ChatEntry {
  question: string;
  answer: string;
  lap: number;
  source: string;
}
