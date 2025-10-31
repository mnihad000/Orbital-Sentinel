import EarthScene from "./components/earthscene";
import DeploySatelliteBox from "./components/DeploySatelliteBox";

export default function App() {
  return (
    <div style={{ width: "100vw", height: "100vh", position: "relative" }}>
      <EarthScene />
      <DeploySatelliteBox />
    </div>
  );
}

