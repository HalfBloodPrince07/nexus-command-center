'use client'

import React, { Suspense, useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { MeshDistortMaterial } from '@react-three/drei'
import * as THREE from 'three'
import { motion } from 'framer-motion'
import dynamic from 'next/dynamic'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type ResourceKey = 'cpu' | 'ram' | 'gpu' | 'vram'

interface ResourceAvatarOrbProps {
  value: number | null
  resourceKey: ResourceKey
  size?: number
}

/* ------------------------------------------------------------------ */
/*  Identity color map                                                 */
/* ------------------------------------------------------------------ */

const IDENTITY: Record<ResourceKey, [identityHex: string, emissiveHex: string]> = {
  cpu:  ['#818cf8', '#6366f1'],
  ram:  ['#a78bfa', '#8b5cf6'],
  gpu:  ['#2dd4bf', '#14b8a6'],
  vram: ['#f472b6', '#ec4899'],
}

const IDENTITY_NAMES: Record<ResourceKey, string> = {
  cpu:  'CPU',
  ram:  'RAM',
  gpu:  'GPU',
  vram: 'VRAM',
}

/* ------------------------------------------------------------------ */
/*  Shared color-lerp helper (zero allocations)                        */
/* ------------------------------------------------------------------ */

function applyLoadColor(
  out: THREE.Color,
  v: number,
  id: THREE.Color,
  amber: THREE.Color,
  red: THREE.Color,
) {
  if (v < 50) {
    out.copy(id)
  } else if (v < 80) {
    const a = (v - 50) / 30
    out.setRGB(
      id.r + (amber.r - id.r) * a,
      id.g + (amber.g - id.g) * a,
      id.b + (amber.b - id.b) * a,
    )
  } else {
    const a = Math.min((v - 80) / 20, 1)
    out.setRGB(
      amber.r + (red.r - amber.r) * a,
      amber.g + (red.g - amber.g) * a,
      amber.b + (red.b - amber.b) * a,
    )
  }
}

/* ------------------------------------------------------------------ */
/*  CoreOrb                                                            */
/* ------------------------------------------------------------------ */

function CoreOrb({ value, resourceKey }: { value: number; resourceKey: ResourceKey }) {
  const meshRef = useRef<THREE.Mesh>(null!)
  const glowRef = useRef<THREE.Mesh>(null!)
  const valueRef = useRef(value)
  valueRef.current = value

  const [identityHex, emissiveHex] = IDENTITY[resourceKey]

  const palette = useMemo(() => ({
    identity: new THREE.Color(identityHex),
    identityEmissive: new THREE.Color(emissiveHex),
    amber: new THREE.Color('#f59e0b'),
    red: new THREE.Color('#ef4444'),
    target: new THREE.Color(identityHex),
    emissiveTarget: new THREE.Color(emissiveHex),
  }), [identityHex, emissiveHex])

  useFrame((state) => {
    const v = valueRef.current
    const t = state.clock.getElapsedTime()
    const mat = meshRef.current?.material as THREE.MeshStandardMaterial & {
      distort: number
      speed: number
    }
    if (!mat || !meshRef.current) return

    // Color lerp
    applyLoadColor(palette.target, v, palette.identity, palette.amber, palette.red)
    mat.color.lerp(palette.target, 0.05)
    applyLoadColor(palette.emissiveTarget, v, palette.identityEmissive, palette.amber, palette.red)
    mat.emissive.lerp(palette.emissiveTarget, 0.05)

    // Distort + speed
    const targetDistort = 0.08 + (v / 100) * 0.48
    const targetSpeed = 0.4 + (v / 100) * 3.5
    mat.distort = THREE.MathUtils.lerp(mat.distort ?? 0.08, targetDistort, 0.04)
    mat.speed = THREE.MathUtils.lerp(mat.speed ?? 0.4, targetSpeed, 0.04)

    // Emissive intensity pulses faster with load
    const pulseSpeed = 0.6 + (v / 100) * 3.5
    mat.emissiveIntensity = 0.25 + (v / 100) * 0.85 + Math.sin(t * pulseSpeed) * 0.12

    // Breathing scale
    const breathAmp = 0.018 + (v / 100) * 0.045
    const breathSpeed = 0.7 + (v / 100) * 3
    meshRef.current.scale.setScalar(1 + Math.sin(t * breathSpeed) * breathAmp)

    // Rotation
    meshRef.current.rotation.y += 0.004 + (v / 100) * 0.014
    meshRef.current.rotation.x += 0.001 + (v / 100) * 0.005

    // Glow shell
    if (glowRef.current) {
      glowRef.current.scale.setScalar(1 + Math.sin(t * breathSpeed) * breathAmp * 0.8)
      const gmat = glowRef.current.material as THREE.MeshBasicMaterial
      gmat.color.lerp(palette.target, 0.05)
      gmat.opacity = 0.04 + (v / 100) * 0.14 + Math.sin(t * 0.7) * 0.02
    }
  })

  const useIcosahedron = resourceKey === 'gpu'

  return (
    <>
      {/* Glow shell */}
      <mesh ref={glowRef} scale={1.1}>
        <sphereGeometry args={[0.72, 32, 32]} />
        <meshBasicMaterial
          color={emissiveHex}
          transparent
          opacity={0.06}
          side={THREE.BackSide}
          depthWrite={false}
        />
      </mesh>

      {/* Core mesh */}
      <mesh ref={meshRef}>
        {useIcosahedron ? (
          <icosahedronGeometry args={[0.72, 1]} />
        ) : (
          <sphereGeometry args={[0.72, 32, 32]} />
        )}
        <MeshDistortMaterial
          color={identityHex}
          emissive={emissiveHex}
          emissiveIntensity={0.25}
          roughness={0.1}
          metalness={0.6}
          distort={0.08}
          speed={0.4}
        />
      </mesh>
    </>
  )
}

/* ------------------------------------------------------------------ */
/*  CPUOrbit — two concentric tori                                     */
/* ------------------------------------------------------------------ */

function CPUOrbit({ value }: { value: number }) {
  const torus1Ref = useRef<THREE.Mesh>(null!)
  const torus2Ref = useRef<THREE.Mesh>(null!)
  const valueRef = useRef(value)
  valueRef.current = value

  const [identityHex, emissiveHex] = IDENTITY.cpu

  const palette = useMemo(() => ({
    identity: new THREE.Color(identityHex),
    identityEmissive: new THREE.Color(emissiveHex),
    amber: new THREE.Color('#f59e0b'),
    red: new THREE.Color('#ef4444'),
    target: new THREE.Color(identityHex),
  }), [identityHex, emissiveHex])

  useFrame((state, delta) => {
    const v = valueRef.current
    const speed = 0.5 + (v / 100) * 3.5

    applyLoadColor(palette.target, v, palette.identity, palette.amber, palette.red)
    const emissiveIntensity = 0.4 + (v / 100) * 1.1

    if (torus1Ref.current) {
      torus1Ref.current.rotation.x += delta * speed * 1.1
      torus1Ref.current.rotation.y += delta * speed * 0.7
      const mat1 = torus1Ref.current.material as THREE.MeshStandardMaterial
      mat1.color.lerp(palette.target, 0.05)
      mat1.emissive.lerp(palette.target, 0.05)
      mat1.emissiveIntensity = emissiveIntensity
    }

    if (torus2Ref.current) {
      torus2Ref.current.rotation.y += delta * speed * 1.1
      torus2Ref.current.rotation.x += delta * speed * 0.7
      const mat2 = torus2Ref.current.material as THREE.MeshStandardMaterial
      mat2.color.lerp(palette.target, 0.05)
      mat2.emissive.lerp(palette.target, 0.05)
      mat2.emissiveIntensity = emissiveIntensity
    }
  })

  return (
    <>
      <mesh ref={torus1Ref} rotation={[0.4, 0, 0]}>
        <torusGeometry args={[0.82, 0.032, 8, 52]} />
        <meshStandardMaterial
          color={identityHex}
          emissive={emissiveHex}
          emissiveIntensity={0.4}
          transparent
          opacity={0.85}
          roughness={0.3}
          metalness={0.5}
        />
      </mesh>
      <mesh ref={torus2Ref} rotation={[0, 0.4, 0]}>
        <torusGeometry args={[0.65, 0.018, 6, 40]} />
        <meshStandardMaterial
          color={identityHex}
          emissive={emissiveHex}
          emissiveIntensity={0.4}
          transparent
          opacity={0.85}
          roughness={0.3}
          metalness={0.5}
        />
      </mesh>
    </>
  )
}

/* ------------------------------------------------------------------ */
/*  RAMOrbit — 4 cubes in a ring around Y                             */
/* ------------------------------------------------------------------ */

function RAMOrbit({ value }: { value: number }) {
  const groupRef = useRef<THREE.Group>(null!)
  const cubeRefs = useRef<(THREE.Mesh | null)[]>([null, null, null, null])
  const valueRef = useRef(value)
  valueRef.current = value

  const [identityHex, emissiveHex] = IDENTITY.ram

  const palette = useMemo(() => ({
    identity: new THREE.Color(identityHex),
    identityEmissive: new THREE.Color(emissiveHex),
    amber: new THREE.Color('#f59e0b'),
    red: new THREE.Color('#ef4444'),
    target: new THREE.Color(identityHex),
  }), [identityHex, emissiveHex])

  const cubeAngles = useMemo(() => [0, Math.PI / 2, Math.PI, (3 * Math.PI) / 2], [])

  useFrame((state) => {
    const v = valueRef.current
    const t = state.clock.getElapsedTime()
    const rotSpeed = 0.35 + (v / 100) * 2.2

    if (groupRef.current) {
      groupRef.current.rotation.y += rotSpeed * (1 / 60)
      groupRef.current.rotation.x = Math.sin(t * 0.3) * 0.12 + (v / 100) * 0.28
    }

    applyLoadColor(palette.target, v, palette.identity, palette.amber, palette.red)
    const emissiveIntensity = 0.35 + (v / 100) * 0.9

    for (let i = 0; i < 4; i++) {
      const cube = cubeRefs.current[i]
      if (!cube) continue
      const mat = cube.material as THREE.MeshStandardMaterial
      mat.color.lerp(palette.target, 0.05)
      mat.emissive.lerp(palette.target, 0.05)
      mat.emissiveIntensity = emissiveIntensity
    }
  })

  return (
    <group ref={groupRef}>
      {cubeAngles.map((angle, i) => (
        <mesh
          key={i}
          ref={(el) => { cubeRefs.current[i] = el }}
          position={[Math.cos(angle) * 0.85, 0, Math.sin(angle) * 0.85]}
        >
          <boxGeometry args={[0.1, 0.1, 0.1]} />
          <meshStandardMaterial
            color={identityHex}
            emissive={emissiveHex}
            emissiveIntensity={0.35}
            roughness={0.3}
            metalness={0.5}
          />
        </mesh>
      ))}
    </group>
  )
}

/* ------------------------------------------------------------------ */
/*  GPUCorona — energy spike rods radiating outward                    */
/* ------------------------------------------------------------------ */

function GPUCorona({ value }: { value: number }) {
  const groupRef = useRef<THREE.Group>(null!)
  const spikeRefs = useRef<(THREE.Mesh | null)[]>([])
  const valueRef = useRef(value)
  valueRef.current = value

  const [identityHex, emissiveHex] = IDENTITY.gpu

  const palette = useMemo(() => ({
    identity: new THREE.Color(identityHex),
    identityEmissive: new THREE.Color(emissiveHex),
    amber: new THREE.Color('#f59e0b'),
    red: new THREE.Color('#ef4444'),
    target: new THREE.Color(identityHex),
  }), [identityHex, emissiveHex])

  const spikeCount = value >= 80 ? 8 : value >= 50 ? 6 : 4
  const spikeLen = 0.14 + (value / 100) * 0.32

  const spikeData = useMemo(() => {
    const data: { angle: number; x: number; z: number; rotZ: number }[] = []
    for (let i = 0; i < spikeCount; i++) {
      const angle = (i / spikeCount) * Math.PI * 2
      data.push({
        angle,
        x: Math.cos(angle) * 0.78,
        z: Math.sin(angle) * 0.78,
        rotZ: -angle + Math.PI / 2,
      })
    }
    return data
  }, [spikeCount])

  useFrame((state) => {
    const v = valueRef.current
    const t = state.clock.getElapsedTime()

    if (groupRef.current) {
      groupRef.current.rotation.y = t * (0.2 + (v / 100) * 0.9)
      groupRef.current.rotation.x = Math.sin(t * 0.45) * 0.18
    }

    applyLoadColor(palette.target, v, palette.identity, palette.amber, palette.red)

    for (let i = 0; i < spikeRefs.current.length; i++) {
      const spike = spikeRefs.current[i]
      if (!spike) continue
      const mat = spike.material as THREE.MeshStandardMaterial
      mat.color.lerp(palette.target, 0.05)
      mat.emissive.lerp(palette.target, 0.05)
      mat.emissiveIntensity =
        v >= 80
          ? 0.8 + Math.sin(t * 5 + i) * 0.4
          : 0.4 + (v / 100) * 0.6
    }
  })

  return (
    <group ref={groupRef}>
      {spikeData.map((spike, i) => (
        <mesh
          key={`${spikeCount}-${i}`}
          ref={(el) => { spikeRefs.current[i] = el }}
          position={[spike.x, 0, spike.z]}
          rotation={[0, 0, spike.rotZ]}
        >
          <cylinderGeometry args={[0.012, 0.035, spikeLen, 4]} />
          <meshStandardMaterial
            color={identityHex}
            emissive={emissiveHex}
            emissiveIntensity={0.4}
            roughness={0.3}
            metalness={0.5}
          />
        </mesh>
      ))}
    </group>
  )
}

/* ------------------------------------------------------------------ */
/*  VRAMOrbit — 3 micro-spheres in loose orbit                        */
/* ------------------------------------------------------------------ */

function VRAMOrbit({ value }: { value: number }) {
  const groupRef = useRef<THREE.Group>(null!)
  const sphereRefs = useRef<(THREE.Mesh | null)[]>([null, null, null])
  const valueRef = useRef(value)
  valueRef.current = value

  const [identityHex, emissiveHex] = IDENTITY.vram

  const palette = useMemo(() => ({
    identity: new THREE.Color(identityHex),
    identityEmissive: new THREE.Color(emissiveHex),
    amber: new THREE.Color('#f59e0b'),
    red: new THREE.Color('#ef4444'),
    target: new THREE.Color(identityHex),
  }), [identityHex, emissiveHex])

  const orbitAngles = useMemo(
    () => [0, (2 * Math.PI) / 3, (4 * Math.PI) / 3],
    [],
  )

  useFrame((state) => {
    const v = valueRef.current
    const t = state.clock.getElapsedTime()
    const orbitSpeed = 0.55 + (v / 100) * 2.8

    if (groupRef.current) {
      groupRef.current.rotation.y += orbitSpeed * (1 / 60)
      if (v >= 80) {
        groupRef.current.rotation.x = Math.sin(t * 5) * 0.35
        groupRef.current.rotation.z = Math.cos(t * 4) * 0.25
      } else {
        groupRef.current.rotation.x = Math.sin(t * 0.5) * 0.1
        groupRef.current.rotation.z *= 0.95
      }
    }

    applyLoadColor(palette.target, v, palette.identity, palette.amber, palette.red)

    const sphereRadius = 0.07 + (v / 100) * 0.07

    for (let i = 0; i < 3; i++) {
      const sphere = sphereRefs.current[i]
      if (!sphere) continue

      const angle = orbitAngles[i]
      sphere.position.set(
        Math.cos(angle) * 0.82,
        Math.sin(angle * 2 + t * orbitSpeed) * 0.15,
        Math.sin(angle) * 0.82,
      )
      sphere.scale.setScalar(sphereRadius / 0.07)

      const mat = sphere.material as THREE.MeshStandardMaterial
      mat.color.lerp(palette.target, 0.05)
      mat.emissive.lerp(palette.target, 0.05)
      mat.emissiveIntensity = 0.4 + (v / 100) * 0.8
    }
  })

  return (
    <group ref={groupRef}>
      {orbitAngles.map((angle, i) => (
        <mesh
          key={i}
          ref={(el) => { sphereRefs.current[i] = el }}
          position={[Math.cos(angle) * 0.82, 0, Math.sin(angle) * 0.82]}
        >
          <sphereGeometry args={[0.07, 10, 10]} />
          <meshStandardMaterial
            color={identityHex}
            emissive={emissiveHex}
            emissiveIntensity={0.4}
            roughness={0.3}
            metalness={0.5}
          />
        </mesh>
      ))}
    </group>
  )
}

/* ------------------------------------------------------------------ */
/*  AvatarScene — composes lights + core + orbiter per resource key     */
/* ------------------------------------------------------------------ */

function AvatarScene({ value, resourceKey }: { value: number; resourceKey: ResourceKey }) {
  const [identityHex] = IDENTITY[resourceKey]

  const pointLightColor =
    value >= 80 ? '#ef4444' : value >= 50 ? '#f59e0b' : identityHex

  return (
    <>
      <ambientLight intensity={0.4} />
      <pointLight
        position={[0, 0, 2.5]}
        intensity={1.4 + (value / 100) * 1.2}
        color={pointLightColor}
      />
      <pointLight position={[1.5, 1.5, 1]} intensity={0.3} color="#ffffff" />
      <CoreOrb value={value} resourceKey={resourceKey} />
      {resourceKey === 'cpu' && <CPUOrbit value={value} />}
      {resourceKey === 'ram' && <RAMOrbit value={value} />}
      {resourceKey === 'gpu' && <GPUCorona value={value} />}
      {resourceKey === 'vram' && <VRAMOrbit value={value} />}
    </>
  )
}

/* ------------------------------------------------------------------ */
/*  ResourceAvatarOrb — the outer React component with Canvas + labels */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  ArcRing — SVG progress arc overlaid on the orb canvas             */
/* ------------------------------------------------------------------ */

function ArcRing({
  pct,
  size,
  identityHex,
}: {
  pct: number
  size: number
  identityHex: string
}) {
  const strokeW   = 2.5
  const padding   = strokeW / 2 + 1          // keep ring inside svg bounds
  const r         = (size / 2) - padding
  const cx        = size / 2
  const cy        = size / 2
  const circumference = 2 * Math.PI * r

  const isHigh = pct >= 80
  const isMid  = pct >= 50

  const arcColor = isHigh ? '#f87171' : isMid ? '#fbbf24' : identityHex

  // track fill: 0 → 100 % of circumference, starting from top (rotate -90°)
  const fillOffset = circumference - (pct / 100) * circumference

  // tick marks at 50 % and 80 %
  function tickDashArray(tickPct: number) {
    const pos = (tickPct / 100) * circumference
    // 2 px tick, rest invisible
    return `1.5 ${circumference - 1.5}`
  }
  function tickDashOffset(tickPct: number) {
    return circumference - (tickPct / 100) * circumference
  }

  return (
    <svg
      className="pointer-events-none absolute inset-0"
      width={size}
      height={size}
      style={{ transform: 'rotate(-90deg)' }}
    >
      {/* track ring */}
      <circle
        cx={cx} cy={cy} r={r}
        fill="none"
        stroke="rgba(255,255,255,0.07)"
        strokeWidth={strokeW}
      />

      {/* filled arc — animated via framer-motion */}
      <motion.circle
        cx={cx} cy={cy} r={r}
        fill="none"
        stroke={arcColor}
        strokeWidth={strokeW}
        strokeLinecap="round"
        strokeDasharray={circumference}
        initial={{ strokeDashoffset: circumference }}
        animate={{
          strokeDashoffset: fillOffset,
          stroke: arcColor,
        }}
        transition={{
          strokeDashoffset: { duration: 0.75, ease: [0.16, 1, 0.3, 1] },
          stroke:           { duration: 0.45 },
        }}
        style={{ filter: `drop-shadow(0 0 3px ${arcColor}80)` }}
      />

      {/* 50 % tick */}
      <circle
        cx={cx} cy={cy} r={r}
        fill="none"
        stroke="rgba(255,255,255,0.18)"
        strokeWidth={strokeW + 0.5}
        strokeDasharray={tickDashArray(50)}
        strokeDashoffset={tickDashOffset(50)}
        strokeLinecap="butt"
      />

      {/* 80 % tick */}
      <circle
        cx={cx} cy={cy} r={r}
        fill="none"
        stroke="rgba(255,255,255,0.22)"
        strokeWidth={strokeW + 0.5}
        strokeDasharray={tickDashArray(80)}
        strokeDashoffset={tickDashOffset(80)}
        strokeLinecap="butt"
      />
    </svg>
  )
}

/* ------------------------------------------------------------------ */
/*  ResourceAvatarOrb                                                  */
/* ------------------------------------------------------------------ */

const ResourceAvatarOrb = ({
  value,
  resourceKey,
  size = 60,
}: ResourceAvatarOrbProps) => {
  const pct    = Math.min(Math.max(value ?? 0, 0), 100)
  const isHigh = pct >= 80
  const isMid  = pct >= 50

  const [identityHex] = IDENTITY[resourceKey]
  const displayColor  = isHigh ? '#f87171' : isMid ? '#fbbf24' : identityHex

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>

        {/* Critical pulse halo */}
        {isHigh && (
          <motion.div
            className="absolute inset-0 rounded-full bg-red-500/20"
            animate={{ scale: [1, 1.6, 1], opacity: [0.5, 0, 0.5] }}
            transition={{ duration: 1, repeat: Infinity, ease: 'easeInOut' }}
          />
        )}

        {/* 3-D orb canvas */}
        <Canvas
          camera={{ position: [0, 0, 2.8], fov: 50 }}
          gl={{ alpha: true, antialias: true, powerPreference: 'high-performance' }}
          dpr={[1, 1.5]}
          style={{ width: size, height: size }}
        >
          <Suspense fallback={null}>
            <AvatarScene value={pct} resourceKey={resourceKey} />
          </Suspense>
        </Canvas>

        {/* SVG arc progress ring — sits on top of the canvas */}
        <ArcRing pct={pct} size={size} identityHex={identityHex} />
      </div>

      <div className="text-center leading-tight">
        <p className="text-[9px] font-medium uppercase tracking-wide text-ink-muted">
          {IDENTITY_NAMES[resourceKey]}
        </p>
        <motion.p
          key={Math.round(pct)}
          initial={{ scale: 0.85, opacity: 0.6 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.25 }}
          className="mt-0.5 text-[11px] font-bold tabular-nums"
          style={{ color: displayColor }}
        >
          {value !== null ? `${Math.round(pct)}%` : '--'}
        </motion.p>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Exports                                                            */
/* ------------------------------------------------------------------ */

export const ResourceAvatarOrbDynamic = dynamic(
  () => Promise.resolve(ResourceAvatarOrb),
  { ssr: false },
)

export default ResourceAvatarOrb
