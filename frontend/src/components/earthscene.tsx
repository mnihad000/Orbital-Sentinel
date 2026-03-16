import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls, Center, Environment, useGLTF } from "@react-three/drei";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Vector3 } from "three";
import Satellites, { Sat } from "./satellites";
import DeploySatelliteBox from "./DeploySatelliteBox";
import CollisionMonitor from "./collisionmonitor";
import DeployedSatellitesPanel from "./DeployedSatellitesPanel";
import { API_BASE_URL } from "../config";

const EARTH_RADIUS_KM = 6371;
const EARTH_RADIUS_UNITS = 0.6;
const KM2U = EARTH_RADIUS_UNITS / EARTH_RADIUS_KM;

function EarthModel(props: any) {
  const gltf = useGLTF("/models/earth_mr.glb");
  return <primitive object={gltf.scene} {...props} />;
}
useGLTF.preload("/models/earth_mr.glb");

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
    const distanceFromTarget = 1.2;
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
  const controlsRef = useRef<any>(null);

  const selectedSatellite = useMemo(
    () => userSatellites.find((s) => s.norad_id === selectedNoradId) || null,
    [selectedNoradId, userSatellites]
  );

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
        camera={{ position: [15, 15, 25], fov: 50, near: 0.1, far: 50000 }}
        dpr={[1, 2]}
        shadows
        style={{ width: "100vw", height: "100vh", background: "#0b0b0b" }}
      >
        <Suspense fallback={null}>
          <hemisphereLight intensity={0.6} />
          <directionalLight position={[5, 5, 5]} intensity={1} castShadow />

          <Center>
            <EarthModel scale={0.6} position={[0, -0.3, 0]} />
          </Center>

          <Satellites
            endpoint={`${API_BASE_URL}/api/positions`}
            limit={2000}
            refreshMs={5000}
            dotScale={0.06}
            onUserSatellitesChange={setUserSatellites}
          />

          <FocusOnSatellite satellite={selectedSatellite} controlsRef={controlsRef} />
          <Environment preset="city" />
          <OrbitControls ref={controlsRef} enableDamping makeDefault />
        </Suspense>
      </Canvas>
    </>
  );
}
