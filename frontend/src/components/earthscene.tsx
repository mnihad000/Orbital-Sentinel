import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Stars } from "@react-three/drei";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { BackSide, CanvasTexture, Group, SRGBColorSpace, Vector3 } from "three";
import Satellites, { Sat } from "./satellites";
import DeploySatelliteBox from "./DeploySatelliteBox";
import CollisionMonitor from "./collisionmonitor";
import DeployedSatellitesPanel from "./DeployedSatellitesPanel";
import { API_BASE_URL } from "../config";
import {
  EARTH_RADIUS_UNITS,
  KM_TO_SCENE_UNITS,
  SATELLITE_DOT_UNITS,
} from "../orbitalScale";

const KM2U = KM_TO_SCENE_UNITS;
const ORBIT_CENTER: [number, number, number] = [0, 0, 0];

function createEarthTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 1024;
  canvas.height = 512;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;

  const ocean = ctx.createLinearGradient(0, 0, 0, canvas.height);
  ocean.addColorStop(0, "#1b5d9e");
  ocean.addColorStop(0.45, "#0d3e73");
  ocean.addColorStop(1, "#062747");
  ctx.fillStyle = ocean;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.fillStyle = "#2f8a57";
  const continents = [
    [[170, 150], [250, 95], [330, 120], [360, 195], [320, 245], [225, 235], [155, 205]],
    [[265, 250], [340, 270], [360, 335], [325, 430], [285, 455], [260, 360]],
    [[480, 145], [575, 105], [650, 140], [675, 205], [620, 245], [530, 235], [455, 195]],
    [[555, 250], [670, 260], [745, 330], [720, 390], [605, 375], [535, 315]],
    [[735, 135], [820, 105], [905, 145], [940, 220], [865, 255], [755, 225]],
    [[820, 305], [890, 320], [925, 370], [890, 420], [825, 400]],
  ];

  continents.forEach((points) => {
    ctx.beginPath();
    points.forEach(([x, y], index) => {
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.fill();
  });

  ctx.fillStyle = "rgba(184, 221, 169, 0.7)";
  continents.forEach((points) => {
    points.forEach(([x, y], index) => {
      if (index % 2 === 0) {
        ctx.beginPath();
        ctx.arc(x, y, 12, 0, Math.PI * 2);
        ctx.fill();
      }
    });
  });

  ctx.strokeStyle = "rgba(255, 255, 255, 0.16)";
  ctx.lineWidth = 1;
  for (let y = 64; y < canvas.height; y += 64) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(canvas.width, y);
    ctx.stroke();
  }
  for (let x = 0; x < canvas.width; x += 64) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
  }

  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  return texture;
}

function ProceduralEarth() {
  const earthRef = useRef<Group>(null);
  const texture = useMemo(() => createEarthTexture(), []);

  useEffect(() => {
    return () => texture?.dispose();
  }, [texture]);

  useFrame((_, delta) => {
    if (earthRef.current) {
      earthRef.current.rotation.y += delta * 0.04;
    }
  });

  return (
    <group ref={earthRef} position={ORBIT_CENTER}>
      <mesh>
        <sphereGeometry args={[EARTH_RADIUS_UNITS, 64, 64]} />
        <meshStandardMaterial
          map={texture || undefined}
          color={texture ? "#ffffff" : "#17558e"}
          roughness={0.82}
          metalness={0}
        />
      </mesh>
      <mesh>
        <sphereGeometry args={[EARTH_RADIUS_UNITS * 1.01, 48, 48]} />
        <meshStandardMaterial
          color="#ffffff"
          transparent
          opacity={0.12}
          roughness={1}
          depthWrite={false}
        />
      </mesh>
      <mesh>
        <sphereGeometry args={[EARTH_RADIUS_UNITS * 1.08, 48, 48]} />
        <meshBasicMaterial
          color="#64c7ff"
          transparent
          opacity={0.16}
          side={BackSide}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}

function FocusOnSatellite({
  satellite,
  controlsRef,
}: {
  satellite: Sat | null;
  controlsRef: React.MutableRefObject<any>;
}) {
  const { camera } = useThree();

  useEffect(() => {
    if (!satellite) return;

    const target = new Vector3(
      satellite.x * KM2U,
      satellite.y * KM2U,
      satellite.z * KM2U
    );
    const direction = target.clone().normalize();
    const distanceFromTarget = EARTH_RADIUS_UNITS * 0.7;
    const cameraPos = target.clone().add(direction.multiplyScalar(distanceFromTarget));

    camera.position.set(cameraPos.x, cameraPos.y, cameraPos.z);
    if (controlsRef.current) {
      controlsRef.current.target.set(target.x, target.y, target.z);
      controlsRef.current.update();
    } else {
      camera.lookAt(target);
    }
  }, [camera, controlsRef, satellite]);

  return null;
}

export default function EarthScene() {
  const [userSatellites, setUserSatellites] = useState<Sat[]>([]);
  const [selectedNoradId, setSelectedNoradId] = useState<string | null>(null);
  const [clickedSatellite, setClickedSatellite] = useState<Sat | null>(null);
  const controlsRef = useRef<any>(null);

  const selectedSatellite = useMemo(
    () => userSatellites.find((s) => s.norad_id === selectedNoradId) || null,
    [selectedNoradId, userSatellites]
  );
  const focusedSatellite = clickedSatellite || selectedSatellite;

  return (
    <>
      <DeploySatelliteBox />
      <CollisionMonitor />
      <DeployedSatellitesPanel
        satellites={userSatellites}
        selectedNoradId={selectedNoradId}
        onSelect={setSelectedNoradId}
      />
      <Canvas
        camera={{ position: [0, EARTH_RADIUS_UNITS * 1.35, EARTH_RADIUS_UNITS * 2.4], fov: 48, near: 0.1, far: 50000 }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, powerPreference: "high-performance" }}
        style={{ width: "100vw", height: "100vh", background: "#05070d" }}
      >
        <Suspense fallback={null}>
          <color attach="background" args={["#05070d"]} />
          <ambientLight intensity={0.28} />
          <hemisphereLight args={["#d7efff", "#111827", 0.7]} />
          <directionalLight position={[5, 4, 6]} intensity={2.2} />
          <Stars radius={80} depth={40} count={1200} factor={3} fade speed={0.2} />

          <ProceduralEarth />

          <Satellites
            endpoint={`${API_BASE_URL}/api/positions`}
            limit={2000}
            refreshMs={5000}
            dotScale={SATELLITE_DOT_UNITS}
            onUserSatellitesChange={setUserSatellites}
            onSatelliteSelect={setClickedSatellite}
          />

          <FocusOnSatellite satellite={focusedSatellite} controlsRef={controlsRef} />
          <OrbitControls
            ref={controlsRef}
            enableDamping
            makeDefault
            target={ORBIT_CENTER}
            minDistance={EARTH_RADIUS_UNITS * 1.12}
            maxDistance={50000}
          />
        </Suspense>
      </Canvas>
    </>
  );
}
