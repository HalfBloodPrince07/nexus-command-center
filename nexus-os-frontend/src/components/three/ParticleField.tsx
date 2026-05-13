'use client'

import React, { Suspense, useMemo, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import dynamic from 'next/dynamic'

const PALETTE = [
  new THREE.Color('#818CF8'), // indigo-400
  new THREE.Color('#A78BFA'), // violet-400
  new THREE.Color('#C084FC'), // purple-400
  new THREE.Color('#F0ABFC'), // fuchsia-300
  new THREE.Color('#67E8F9'), // cyan-300
  new THREE.Color('#2DD4BF'), // teal-400
]

const Particles = () => {
  const mesh = useRef<THREE.Points>(null!)
  const count = 350

  const { positions, colors, velocities, bases, opacities } = useMemo(() => {
    const positions = new Float32Array(count * 3)
    const colors = new Float32Array(count * 3)
    const velocities = new Float32Array(count * 3)
    const bases = new Float32Array(count * 2)
    const opacities = new Float32Array(count)

    const aspect = typeof window !== 'undefined' ? window.innerWidth / window.innerHeight : 1.78

    for (let i = 0; i < count; i++) {
      const i3 = i * 3
      positions[i3] = (Math.random() - 0.5) * 18 * aspect
      positions[i3 + 1] = (Math.random() - 0.5) * 14
      positions[i3 + 2] = (Math.random() - 0.5) * 4

      velocities[i3] = (Math.random() - 0.5) * 0.0006
      velocities[i3 + 1] = 0.001 + Math.random() * 0.0015
      velocities[i3 + 2] = (Math.random() - 0.5) * 0.0003

      const color = PALETTE[Math.floor(Math.random() * PALETTE.length)]
      colors[i3] = color.r
      colors[i3 + 1] = color.g
      colors[i3 + 2] = color.b

      bases[i * 2] = Math.random() * Math.PI * 2
      bases[i * 2 + 1] = 0.001 + Math.random() * 0.002
      opacities[i] = 0.15 + Math.random() * 0.25
    }

    return { positions, colors, velocities, bases, opacities }
  }, [])

  useFrame(state => {
    if (!mesh.current) return
    const posAttr = mesh.current.geometry.attributes.position as THREE.BufferAttribute
    const arr = posAttr.array as Float32Array
    const t = state.clock.getElapsedTime()

    const aspect = typeof window !== 'undefined' ? window.innerWidth / window.innerHeight : 1.78
    const xBound = 9 * aspect
    const yBound = 7

    for (let i = 0; i < count; i++) {
      const i3 = i * 3
      const phase = bases[i * 2]
      const amp = bases[i * 2 + 1]

      arr[i3] += velocities[i3] + Math.sin(t * 0.4 + phase) * amp
      arr[i3 + 1] += velocities[i3 + 1]
      arr[i3 + 2] += velocities[i3 + 2]

      if (arr[i3 + 1] > yBound) {
        arr[i3 + 1] = -yBound
        arr[i3] = (Math.random() - 0.5) * 2 * xBound
      }
      if (arr[i3] > xBound) arr[i3] = -xBound
      if (arr[i3] < -xBound) arr[i3] = xBound
    }

    posAttr.needsUpdate = true
  })

  return (
    <points ref={mesh}>
      <bufferGeometry attach="geometry">
        <bufferAttribute
          attach="attributes-position"
          count={positions.length / 3}
          array={positions}
          itemSize={3}
        />
        <bufferAttribute
          attach="attributes-color"
          count={colors.length / 3}
          array={colors}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        attach="material"
        size={0.05}
        transparent
        opacity={0.3}
        vertexColors
        sizeAttenuation
        depthWrite={false}
        blending={THREE.NormalBlending}
      />
    </points>
  )
}

const ParticleField = () => {
  return (
    <Canvas
      camera={{ position: [0, 0, 5], fov: 75 }}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        zIndex: 0,
        pointerEvents: 'none',
      }}
      gl={{ antialias: false, alpha: true }}
      frameloop="always"
    >
      <Suspense fallback={null}>
        <Particles />
      </Suspense>
    </Canvas>
  )
}

export const ParticleFieldDynamic = dynamic(() => Promise.resolve(ParticleField), {
  ssr: false,
})

export default ParticleField
