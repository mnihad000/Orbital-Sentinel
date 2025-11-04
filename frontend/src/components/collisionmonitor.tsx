import { useEffect, useState } from "react";

export default function CollisionMonitor() {
  const [collisions, setCollisions] = useState<any[]>([]);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/api/collisions");
        if (!res.ok) return;
        const data = await res.json();
        setCollisions(data.collisions || []);
        setTotal(data.collision_count || 0);
      } catch {}
    };
    load();
    const id = setInterval(load, 8000);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={boxStyle}>
      <h3>☄️ Collision Monitor</h3>
      <p>Total: {total}</p>
      <ul style={{ fontSize: "0.85rem", maxHeight: "150px", overflowY: "auto" }}>
        {collisions.slice(0, 5).map((c, i) => (
          <li key={i}>
            {c.satellite1_label} vs {c.satellite2_label} — {c.distance_km} km
          </li>
        ))}
      </ul>
    </div>
  );
}

const boxStyle: React.CSSProperties = {
  position: "absolute",
  top: "1rem",
  right: "1rem",
  width: "260px",
  background: "rgba(0, 0, 0, 0.7)",
  color: "white",
  padding: "1rem",
  borderRadius: "12px",
  boxShadow: "0 4px 10px rgba(0,0,0,0.3)",
  fontFamily: "sans-serif",
  zIndex: 10,
};
