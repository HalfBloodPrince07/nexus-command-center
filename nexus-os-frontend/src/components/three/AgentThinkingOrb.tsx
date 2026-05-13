'use client'

import React, { Suspense, useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { MeshDistortMaterial } from '@react-three/drei'
import * as THREE from 'three'
import { motion } from 'framer-motion'
import dynamic from 'next/dynamic'

type OrbStatus = 'idle' | 'thinking' | 'streaming' | 'error'

interface AgentThinkingOrbProps {
  status: OrbStatus
  size?: number
}

const STATUS_CONFIG: Record<
  OrbStatus,
  { color: string; emissive: string; scale: number; speed: number; distort: number }
> = {
  idle: {
    color: '#818CF8',
    emissive: '#6366F1',
    scale: 1.0,
    speed: 0.6,
    distort: 0.15,
  },
  thinking: {
    color: '#A855F7',
    emissive: '#7C3AED',
    scale: 1.15,
    speed: 2.2,
    distort: 0.35,
  },
  streaming: {
    color: '#6366F1',
    emissive: '#4F46E5',
    scale: 1.1,
    speed: 1.5,
    distort: 0.25,
  },
  error: {
    color: '#F87171',
    emissive: '#EF4444',
    scale: 1.0,
    speed: 5.0,
    distort: 0.6,
  },
}

const Orb = ({ status }: { status: OrbStatus }) => {
  const meshRef = useRef<THREE.Mesh>(null!)
  const glowRef = useRef<THREE.Mesh>(null!)

  const config = STATUS_CONFIG[status]
  const targetColor = useMemo(() => new THREE.Color(config.color), [config.color])
  const targetEmissive = useMemo(() => new THREE.Color(config.emissive), [config.emissive])

  useFrame(state => {
    if (!meshRef.current) return
    const t = state.clock.getElapsedTime()

    const mat = meshRef.current.material as THREE.MeshStandardMaterial
    mat.color.lerp(targetColor, 0.06)
    mat.emissive.lerp(targetEmissive, 0.06)

    const targetScale = config.scale + Math.sin(t * config.speed * 1.5) * 0.03
    meshRef.current.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.06)

    meshRef.current.rotation.y += 0.003
    meshRef.current.rotation.x += 0.001

    if (status === 'error') {
      mat.emissiveIntensity = Math.random() > 0.85 ? 1.0 : 0.35
    } else {
      mat.emissiveIntensity = 0.4 + Math.sin(t * config.speed) * 0.1
    }

    if (glowRef.current) {
      glowRef.current.scale.setScalar(targetScale * 1.3)
      ;(glowRef.current.material as THREE.MeshBasicMaterial).opacity =
        0.06 + Math.sin(t * 0.8) * 0.02
    }
  })

  return (
    <>
      <ambientLight intensity={0.5} />
      <pointLight position={[0, 0, 3]} intensity={2} color="#6366F1" />
      <pointLight position={[2, 2, 2]} intensity={0.5} color="#ffffff" />

      <mesh ref={glowRef} scale={1.3}>
        <sphereGeometry args={[1, 32, 32]} />
        <meshBasicMaterial
          color={config.emissive}
          transparent
          opacity={0.08}
          side={THREE.BackSide}
          depthWrite={false}
        />
      </mesh>

      <mesh ref={meshRef}>
        <sphereGeometry args={[1, 64, 64]} />
        <MeshDistortMaterial
          color={config.color}
          emissive={config.emissive}
          emissiveIntensity={0.4}
          roughness={0.12}
          metalness={0.5}
          distort={config.distort}
          speed={config.speed}
        />
      </mesh>
    </>
  )
}

const AgentThinkingOrb = ({ status, size = 100 }: AgentThinkingOrbProps) => {
  const isVisible = status !== 'idle'

  return (
    <motion.div
      animate={{
        opacity: isVisible ? 1 : 0.4,
        scale: isVisible ? 1 : 0.8,
      }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      style={{ width: size, height: size }}
      className="drop-shadow-[0_8px_32px_rgba(99,102,241,0.25)]"
    >
      <Canvas
        camera={{ position: [0, 0, 3], fov: 50 }}
        gl={{ alpha: true, antialias: true }}
      >
        <Suspense fallback={null}>
          <Orb status={status} />
        </Suspense>
      </Canvas>
    </motion.div>
  )
}

export const AgentThinkingOrbDynamic = dynamic(
  () => Promise.resolve(AgentThinkingOrb),
  { ssr: false }
)

export default AgentThinkingOrb
