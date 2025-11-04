import { Canvas } from "@react-three/fiber";
import { OrbitControls, Center, Environment, useGLTF } from "@react-three/drei";
import { Suspense } from "react";
import Satellites from "./satellites"; // 👈 import your satellites component
import DeploySatelliteBox from "./DeploySatelliteBox";
import CollisionMonitor from "./collisionmonitor";

function EarthModel(props: any) {
  const gltf = useGLTF("/models/earth_mr.glb");
  return <primitive object={gltf.scene} {...props} />;
}
useGLTF.preload("/models/earth_mr.glb");

export default function EarthScene() {
  return (
    <>

    <DeploySatelliteBox />
    <CollisionMonitor />
    <Canvas
      camera={{ position: [15, 15, 25], fov: 50, near: 0.1, far: 50000}}
      dpr={[1, 2]}
      shadows
      style={{ width: "100vw", height: "100vh", background: "#0b0b0b" }}
    >
      <Suspense fallback={null}>
        <hemisphereLight intensity={0.6} />
        <directionalLight position={[5, 5, 5]} intensity={1} castShadow />

        {/* center your earth */}
        <Center>
          <EarthModel scale={0.6} position={[0, -0.3, 0]} />
        </Center>

        {/* 🌍 add satellites right here */}
        <Satellites
          endpoint="http://127.0.0.1:8000/api/positions"
          limit={2000}
          refreshMs={5000}
          dotScale={0.9}
        />

        <Environment preset="city" />
        <OrbitControls enableDamping makeDefault />
      </Suspense>
    </Canvas>
    </>
  );
}
