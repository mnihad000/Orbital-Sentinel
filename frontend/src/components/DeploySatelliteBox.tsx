import { useState } from "react";

export default function DeploySatelliteBox() {
  const [form, setForm] = useState({
    catalog_number: "",
    name: "",
    tle_line1: "",
    tle_line2: "",
  });
  const [status, setStatus] = useState<null | string>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("Deploying...");
    try {
      const res = await fetch("http://127.0.0.1:8000/satellites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error("Failed to deploy satellite.");
      setStatus("✅ Satellite deployed successfully!");
      setForm({ catalog_number: "", name: "", tle_line1: "", tle_line2: "" });
    } catch (err) {
      setStatus("❌ Error deploying satellite.");
    }
  };

  return (
    <div style={boxStyle}>
      <h3 style={{ marginBottom: "0.75rem", fontWeight: "600" }}>🚀 Deploy Satellite</h3>
      <form onSubmit={handleSubmit} style={formStyle}>
        <input name="catalog_number" placeholder="Catalog Number" value={form.catalog_number} onChange={handleChange} style={inputStyle} />
        <input name="name" placeholder="Satellite Name" value={form.name} onChange={handleChange} style={inputStyle} />
        <textarea name="tle_line1" placeholder="TLE Line 1" value={form.tle_line1} onChange={handleChange} rows={2} style={inputStyle} />
        <textarea name="tle_line2" placeholder="TLE Line 2" value={form.tle_line2} onChange={handleChange} rows={2} style={inputStyle} />
        <button type="submit" style={buttonStyle}>Deploy</button>
      </form>
      {status && <p style={{ marginTop: "0.5rem", fontSize: "0.85rem" }}>{status}</p>}
    </div>
  );
}

const boxStyle: React.CSSProperties = {
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
};

const formStyle: React.CSSProperties = { display: "flex", flexDirection: "column", gap: "0.5rem" };

const inputStyle: React.CSSProperties = {
  background: "rgba(255,255,255,0.1)",
  color: "white",
  border: "1px solid rgba(255,255,255,0.2)",
  borderRadius: "6px",
  padding: "0.4rem 0.6rem",
  fontSize: "0.9rem",
  outline: "none",
};

const buttonStyle: React.CSSProperties = {
  background: "#22c55e",
  color: "white",
  border: "none",
  borderRadius: "6px",
  padding: "0.5rem 0.75rem",
  fontWeight: "bold",
  cursor: "pointer",
};

