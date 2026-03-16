import { useEffect, useMemo, useRef, useState } from "react";
import { InstancedMesh, Object3D } from "three";
import { useFrame } from "@react-three/fiber";

export type Sat = {
  norad_id: string;
  name?: string;
  x: number;
  y: number;
  z: number;
  source?: string;
};

const EARTH_RADIUS_KM = 6371;
const EARTH_RADIUS_UNITS = 0.6;
const KM2U = EARTH_RADIUS_UNITS / EARTH_RADIUS_KM;

export default function Satellites({
  endpoint,
  limit = 2000,
  refreshMs = 5000,
  dotScale = 0.06,
  onUserSatellitesChange,
}: {
  endpoint: string;
  limit?: number;
  refreshMs?: number;
  dotScale?: number;
  onUserSatellitesChange?: (sats: Sat[]) => void;
}) {
  const publicMeshRef = useRef<InstancedMesh>(null!);
  const userMeshRef = useRef<InstancedMesh>(null!);
  const [data, setData] = useState<Sat[]>([]);
  const dummy = useMemo(() => new Object3D(), []);

  const publicSats = data.filter((d) => d.source !== "user");
  const userSats = data.filter((d) => d.source === "user");

  useEffect(() => {
    onUserSatellitesChange?.(userSats);
  }, [onUserSatellitesChange, userSats]);

  useEffect(() => {
    let timer: any;
    const load = async () => {
      try {
        const res = await fetch(`${endpoint}?limit=${limit}`);
        if (!res.ok) {
          setData([]);
          return;
        }
        const json: Sat[] = await res.json();
        setData(Array.isArray(json) ? json : []);
      } catch {
        setData([]);
      }
    };

    load();
    timer = setInterval(load, refreshMs);
    return () => clearInterval(timer);
  }, [endpoint, limit, refreshMs]);

  useFrame(() => {
    const publicMesh = publicMeshRef.current;
    const userMesh = userMeshRef.current;
    if (!publicMesh || !userMesh) return;

    for (let i = 0; i < publicSats.length; i++) {
      const p = publicSats[i];
      dummy.position.set(p.x * KM2U, p.y * KM2U, p.z * KM2U);
      dummy.scale.setScalar(dotScale);
      dummy.updateMatrix();
      publicMesh.setMatrixAt(i, dummy.matrix);
    }
    publicMesh.count = Math.max(1, publicSats.length);
    publicMesh.instanceMatrix.needsUpdate = true;

    for (let i = 0; i < userSats.length; i++) {
      const p = userSats[i];
      dummy.position.set(p.x * KM2U, p.y * KM2U, p.z * KM2U);
      dummy.scale.setScalar(dotScale);
      dummy.updateMatrix();
      userMesh.setMatrixAt(i, dummy.matrix);
    }
    userMesh.count = Math.max(1, userSats.length);
    userMesh.instanceMatrix.needsUpdate = true;
  });

  return (
    <>
      <instancedMesh
        ref={publicMeshRef}
        args={[undefined as any, undefined as any, Math.max(1, publicSats.length)]}
      >
        <sphereGeometry args={[1, 8, 8]} />
        <meshBasicMaterial color="white" />
      </instancedMesh>

      <instancedMesh
        ref={userMeshRef}
        args={[undefined as any, undefined as any, Math.max(1, userSats.length)]}
      >
        <sphereGeometry args={[1, 8, 8]} />
        <meshBasicMaterial color="white" />
      </instancedMesh>
    </>
  );
}
