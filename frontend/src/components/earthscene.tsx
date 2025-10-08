import {Canvas} from '@react-three/fiber'
import {OrbitControls, Center, Environment, useGLTF} from '@react-three/drei'
import { Suspense } from 'react'

function EarthModel(props: any) {
  const gltf = useGLTF('/models/earth_mr.glb') // put your file name here
  return <primitive object={gltf.scene} {...props} />
}
useGLTF.preload('/models/earth_mr.glb')

export default function EarthScene() {
  return (
    <Canvas
      camera={{ position: [2, 2, 4], fov: 50 }}
      dpr={[1, 2]}
      shadows
      style={{ width: '100vw', height: '100vh', background: '#0b0b0b' }}
    >
      <Suspense fallback={null}>
        <hemisphereLight intensity={0.6} />
        <directionalLight position={[5, 5, 5]} intensity={1} castShadow />

        <Center>
          <EarthModel scale={1} position={[0, -0.3, 0]} />
        </Center>

        <Environment preset="city" />
        <OrbitControls enableDamping makeDefault />
      </Suspense>
    </Canvas>
  )
}