import { useState } from "react";

export default function DeploySatelliteBox() {
  const [form, setForm] = useState({
    catalog_number: "",
    name: "",
    tle_line1: "",
    tle_line2: "",
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // We'll wire this up later to POST /satellites
    console.log("Satellite data:", form);
    alert("Satellite ready to deploy! (Backend hookup coming soon)");
  };

  return (
    <div
      style={{
        position: "absolute",
        top: "1rem",
        left: "1rem",
        width: "300px",
        background: "rgba(0, 0, 0, 0.7)",
        color: "white",
        padding: "1rem",
        borderRadius: "12px",
        boxShadow: "0 4px 10px rgba(0,0,0,0.3)",
        fontFamily: "sans-serif",
        zIndex: 10,
      }}
    >
      <h3 style={{ marginBottom: "0.75rem", fontWeight: "600" }}>🚀 Deploy Satellite</h3>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        <input
          name="catalog_number"
          placeholder="Catalog Number"
          value={form.catalog_number}
          onChange={handleChange}
          style={inputStyle}
        />
        <input
          name="name"
          placeholder="Satellite Name"
          value={form.name}
          onChange={handleChange}
          style={inputStyle}
        />
        <textarea
          name="tle_line1"
          placeholder="TLE Line 1"
          value={form.tle_line1}
          onChange={handleChange}
          rows={2}
          style={inputStyle}
        />
        <textarea
          name="tle_line2"
          placeholder="TLE Line 2"
          value={form.tle_line2}
          onChange={handleChange}
          rows={2}
          style={inputStyle}
        />
        <button
          type="submit"
          style={{
            background: "#22c55e",
            color: "white",
            border: "none",
            borderRadius: "6px",
            padding: "0.5rem 0.75rem",
            fontWeight: "bold",
            cursor: "pointer",
            transition: "background 0.2s ease",
          }}
          onMouseOver={(e) => (e.currentTarget.style.background = "#16a34a")}
          onMouseOut={(e) => (e.currentTarget.style.background = "#22c55e")}
        >
          Deploy
        </button>
      </form>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  background: "rgba(255,255,255,0.1)",
  color: "white",
  border: "1px solid rgba(255,255,255,0.2)",
  borderRadius: "6px",
  padding: "0.4rem 0.6rem",
  fontSize: "0.9rem",
  outline: "none",
};
