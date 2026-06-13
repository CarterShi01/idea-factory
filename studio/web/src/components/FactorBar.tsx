import type { Factors } from "../types";

export function FactorBar({ name, value }: { name: string; value: number }) {
  return (
    <div className="fbar">
      <span className="fname">{name}</span>
      <span className="track">
        <span className="fill" style={{ width: `${Math.round(value * 100)}%` }} />
      </span>
      <span className="fval">{value.toFixed(2)}</span>
    </div>
  );
}

export function FactorBars({ factors }: { factors: Factors }) {
  return (
    <div>
      {Object.entries(factors).map(([k, v]) => (
        <FactorBar key={k} name={k} value={v} />
      ))}
    </div>
  );
}
