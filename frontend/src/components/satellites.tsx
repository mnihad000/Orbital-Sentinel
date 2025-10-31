import { useEffect, useMemo, useRef, useState } from "react";
import { InstancedMesh, Object3D } from "three";
import { useFrame } from "@react-three/fiber";

type Sat = { norad_id: string; name?: string; x: number; y: number; z: number };

const EARTH_RADIUS_KM = 6371;   // backend positions are in km (ECEF)
const EARTH_RADIUS_UNITS = 1;   // your Earth mesh radius in scene units
const KM2U = 0.01;

export default function Satellites({
  endpoint = "http://127.0.0.1:8000/api/positions",
  limit = 2000,
  refreshMs = 5000,
  dotScale = 0.006,
}: {
  endpoint?: string; limit?: number; refreshMs?: number; dotScale?: number;
}) {
  const meshRef = useRef<InstancedMesh>(null!);
  const [data, setData] = useState<Sat[]>([]);
  const dummy = useMemo(() => new Object3D(), []);

  useEffect(() => {
    let timer: any;
    const load = async () => {
      try {
        const res = await fetch(`${endpoint}?limit=${limit}`);
        if (!res.ok) return;
        const json: Sat[] = await res.json();
        setData(json);
      } catch {}
    };
    load();
    timer = setInterval(load, refreshMs);
    return () => clearInterval(timer);
  }, [endpoint, limit, refreshMs]);

  useFrame(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    for (let i = 0; i < data.length; i++) {
      const p = data[i];
      dummy.position.set(p.x * KM2U, p.y * KM2U, p.z * KM2U);
      dummy.scale.setScalar(dotScale);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    }
    mesh.count = Math.max(1, data.length);
    mesh.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined as any, undefined as any, Math.max(1, data.length)]}>
      <sphereGeometry args={[1, 8, 8]} />
      <meshBasicMaterial color="white" />
    </instancedMesh>
  );
}