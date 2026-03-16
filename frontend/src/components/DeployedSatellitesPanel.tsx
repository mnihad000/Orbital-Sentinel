import { Sat } from "./satellites";

type Props = {
  satellites: Sat[];
  selectedNoradId: string | null;
  onSelect: (noradId: string) => void;
};

export default function DeployedSatellitesPanel({
  satellites,
  selectedNoradId,
  onSelect,
}: Props) {
  return (
    <div style={boxStyle}>
      <h3 style={{ margin: "0 0 0.6rem 0" }}>Deployed Satellites</h3>
      {satellites.length === 0 && (
        <p style={{ margin: 0, fontSize: "0.85rem", opacity: 0.8 }}>
          No deployed satellites in view.
        </p>
      )}
      <ul style={listStyle}>
        {satellites.map((sat) => {
          const label = sat.name?.trim() || sat.norad_id;
          const active = selectedNoradId === sat.norad_id;
          return (
            <li key={sat.norad_id}>
              <button
                type="button"
                onClick={() => onSelect(sat.norad_id)}
                style={{
                  ...itemButtonStyle,
                  ...(active ? activeItemStyle : null),
                }}
              >
                {label}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

const boxStyle: React.CSSProperties = {
  position: "absolute",
  top: "14rem",
  right: "1rem",
  width: "260px",
  maxHeight: "48vh",
  overflowY: "auto",
  background: "rgba(0, 0, 0, 0.7)",
  color: "white",
  padding: "1rem",
  borderRadius: "12px",
  boxShadow: "0 4px 10px rgba(0,0,0,0.3)",
  fontFamily: "sans-serif",
  zIndex: 10,
};

const listStyle: React.CSSProperties = {
  listStyle: "none",
  margin: 0,
  padding: 0,
  display: "flex",
  flexDirection: "column",
  gap: "0.4rem",
};

const itemButtonStyle: React.CSSProperties = {
  width: "100%",
  background: "rgba(255,255,255,0.09)",
  color: "white",
  border: "1px solid rgba(255,255,255,0.2)",
  borderRadius: "8px",
  padding: "0.45rem 0.55rem",
  fontSize: "0.85rem",
  textAlign: "left",
  cursor: "pointer",
};

const activeItemStyle: React.CSSProperties = {
  border: "1px solid #22c55e",
  background: "rgba(34,197,94,0.22)",
};

