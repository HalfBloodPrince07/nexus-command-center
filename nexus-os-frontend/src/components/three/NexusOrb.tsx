'use client'

import React, { Suspense, useMemo, useRef } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import dynamic from 'next/dynamic'

/* ─────────────────────────────────────────────────────────────────────────────
   NexusOrb — fresh iso-surface + particle aura.
   No drei MeshDistortMaterial. Custom GLSL with simplex-3D vertex displacement
   and a fresnel-driven fragment shader. Single accent (electric violet).
   ───────────────────────────────────────────────────────────────────────────── */

interface OrbProps {
  scrollProgress?: number
  cursor?: { x: number; y: number } // normalized [-1, 1]
  className?: string
}

// Ashima 3D simplex noise — compact, well-known. ~120 ALU ops.
const SIMPLEX_3D_GLSL = /* glsl */ `
vec4 mod289(vec4 x){return x-floor(x*(1.0/289.0))*289.0;}
vec3 mod289(vec3 x){return x-floor(x*(1.0/289.0))*289.0;}
vec4 permute(vec4 x){return mod289(((x*34.0)+1.0)*x);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-0.85373472095314*r;}
float snoise(vec3 v){
  const vec2 C=vec2(1.0/6.0,1.0/3.0);
  const vec4 D=vec4(0.0,0.5,1.0,2.0);
  vec3 i=floor(v+dot(v,C.yyy));
  vec3 x0=v-i+dot(i,C.xxx);
  vec3 g=step(x0.yzx,x0.xyz);
  vec3 l=1.0-g;
  vec3 i1=min(g.xyz,l.zxy);
  vec3 i2=max(g.xyz,l.zxy);
  vec3 x1=x0-i1+C.xxx;
  vec3 x2=x0-i2+C.yyy;
  vec3 x3=x0-D.yyy;
  i=mod289(i);
  vec4 p=permute(permute(permute(
    i.z+vec4(0.0,i1.z,i2.z,1.0))
    +i.y+vec4(0.0,i1.y,i2.y,1.0))
    +i.x+vec4(0.0,i1.x,i2.x,1.0));
  float n_=0.142857142857;
  vec3 ns=n_*D.wyz-D.xzx;
  vec4 j=p-49.0*floor(p*ns.z*ns.z);
  vec4 x_=floor(j*ns.z);
  vec4 y_=floor(j-7.0*x_);
  vec4 x=x_*ns.x+ns.yyyy;
  vec4 y=y_*ns.x+ns.yyyy;
  vec4 h=1.0-abs(x)-abs(y);
  vec4 b0=vec4(x.xy,y.xy);
  vec4 b1=vec4(x.zw,y.zw);
  vec4 s0=floor(b0)*2.0+1.0;
  vec4 s1=floor(b1)*2.0+1.0;
  vec4 sh=-step(h,vec4(0.0));
  vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy;
  vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
  vec3 p0=vec3(a0.xy,h.x);
  vec3 p1=vec3(a0.zw,h.y);
  vec3 p2=vec3(a1.xy,h.z);
  vec3 p3=vec3(a1.zw,h.w);
  vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
  p0*=norm.x;p1*=norm.y;p2*=norm.z;p3*=norm.w;
  vec4 m=max(0.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.0);
  m=m*m;
  return 42.0*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
}
`

const ORB_VERT = /* glsl */ `
uniform float uTime;
uniform float uDistort;
uniform float uFreq;
varying vec3 vNormal;
varying float vDisp;
varying vec3 vPos;

${SIMPLEX_3D_GLSL}

void main(){
  vec3 p = position;
  float n = snoise(p * uFreq + vec3(0.0, uTime * 0.35, 0.0));
  float n2 = snoise(p * (uFreq * 2.1) + vec3(uTime * 0.6, 0.0, 0.0)) * 0.45;
  float disp = (n + n2) * uDistort;
  vec3 displaced = p + normal * disp;
  vDisp = disp;
  vNormal = normalize(normalMatrix * normal);
  vPos = displaced;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
}
`

const ORB_FRAG = /* glsl */ `
uniform vec3 uColorCore;
uniform vec3 uColorEdge;
uniform vec3 uColorDeep;
uniform float uTime;
uniform float uOpacity;
varying vec3 vNormal;
varying float vDisp;
varying vec3 vPos;

void main(){
  vec3 viewDir = normalize(cameraPosition - vPos);
  float fresnel = pow(1.0 - max(dot(normalize(vNormal), viewDir), 0.0), 2.0);

  // Core color modulated by displacement amplitude (high-points glow brighter)
  float pulse = 0.5 + 0.5 * sin(uTime * 0.6 + vDisp * 4.0);
  vec3 core = mix(uColorDeep, uColorCore, smoothstep(-0.15, 0.25, vDisp));
  vec3 edge = mix(core, uColorEdge, fresnel);
  vec3 col = edge + uColorEdge * fresnel * 0.6 * pulse;

  // Soft alpha at silhouette so the orb blends with its glow halo
  float alpha = uOpacity * (0.65 + 0.35 * fresnel);
  gl_FragColor = vec4(col, alpha);
}
`

// ─── Particle aura — instanced points in a spherical shell ──────────────────

const PARTICLES_VERT = /* glsl */ `
uniform float uTime;
uniform float uSize;
attribute float aSeed;
attribute float aRadius;
varying float vSeed;
varying float vAlpha;

void main(){
  float t = uTime * 0.08 + aSeed * 6.2831;
  // Drift each particle around its own circular path on a varying axis
  vec3 axis = normalize(vec3(sin(aSeed * 17.0), cos(aSeed * 23.0), sin(aSeed * 11.0)));
  float angle = t;
  float c = cos(angle); float s = sin(angle);
  // Rodrigues rotation
  vec3 p = position;
  vec3 rotated = p * c + cross(axis, p) * s + axis * dot(axis, p) * (1.0 - c);
  rotated *= aRadius;

  vec4 mv = modelViewMatrix * vec4(rotated, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = uSize * (300.0 / -mv.z);

  // Fade based on depth so the back-half doesn't overwhelm
  vAlpha = smoothstep(-3.0, 1.0, mv.z);
  vSeed = aSeed;
}
`

const PARTICLES_FRAG = /* glsl */ `
uniform vec3 uColor;
varying float vAlpha;
varying float vSeed;

void main(){
  vec2 uv = gl_PointCoord - 0.5;
  float d = length(uv);
  float a = smoothstep(0.5, 0.0, d);
  // Soft twinkle per-particle
  float twinkle = 0.6 + 0.4 * sin(vSeed * 31.0);
  gl_FragColor = vec4(uColor, a * vAlpha * twinkle * 0.55);
}
`

// ─── Iso-surface mesh ────────────────────────────────────────────────────────

function IsoOrb({ scrollProgress = 0, cursor = { x: 0, y: 0 } }: OrbProps) {
  const meshRef = useRef<THREE.Mesh>(null!)
  const matRef = useRef<THREE.ShaderMaterial>(null!)

  // Cursor proximity: how centered the cursor is (1 = center, 0 = edges)
  const targetProximity = useRef(0)
  const proximity = useRef(0)

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uDistort: { value: 0.18 },
      uFreq: { value: 1.05 },
      uColorCore: { value: new THREE.Color('#7C5CFF') },
      uColorEdge: { value: new THREE.Color('#B6A6FF') },
      uColorDeep: { value: new THREE.Color('#3B2599') },
      uOpacity: { value: 1.0 },
    }),
    [],
  )

  useFrame((state, delta) => {
    if (!meshRef.current || !matRef.current) return
    const t = state.clock.getElapsedTime()
    uniforms.uTime.value = t

    // Cursor proximity: closer to center = stronger distortion
    const dx = cursor.x
    const dy = cursor.y
    const dist = Math.hypot(dx, dy)
    targetProximity.current = THREE.MathUtils.clamp(1 - dist, 0, 1)
    proximity.current = THREE.MathUtils.lerp(
      proximity.current,
      targetProximity.current,
      0.04,
    )

    uniforms.uDistort.value = 0.16 + proximity.current * 0.18 + scrollProgress * 0.05
    uniforms.uFreq.value = 1.0 + scrollProgress * 0.3

    // Idle rotation, parallaxed by scroll, tilted by cursor
    meshRef.current.rotation.y = t * 0.12 + scrollProgress * Math.PI * 0.6
    meshRef.current.rotation.x =
      Math.sin(t * 0.15) * 0.08 + dy * 0.15 + scrollProgress * 0.25
    meshRef.current.rotation.z = dx * 0.08

    // Subtle breath
    const breathe = 1 + Math.sin(t * 0.5) * 0.025
    meshRef.current.scale.setScalar(breathe)
  })

  return (
    <mesh ref={meshRef}>
      <icosahedronGeometry args={[1, 6]} />
      <shaderMaterial
        ref={matRef}
        uniforms={uniforms}
        vertexShader={ORB_VERT}
        fragmentShader={ORB_FRAG}
        transparent
        depthWrite={false}
      />
    </mesh>
  )
}

// ─── Particle aura ───────────────────────────────────────────────────────────

function ParticleAura({ count = 800, scrollProgress = 0 }: { count?: number; scrollProgress?: number }) {
  const ref = useRef<THREE.Points>(null!)

  const { positions, seeds, radii } = useMemo(() => {
    const positions = new Float32Array(count * 3)
    const seeds = new Float32Array(count)
    const radii = new Float32Array(count)
    for (let i = 0; i < count; i++) {
      // Random point on unit sphere, then push out by 1.6–2.6
      const u = Math.random() * 2 - 1
      const theta = Math.random() * Math.PI * 2
      const r = Math.sqrt(1 - u * u)
      positions[i * 3 + 0] = r * Math.cos(theta)
      positions[i * 3 + 1] = u
      positions[i * 3 + 2] = r * Math.sin(theta)
      seeds[i] = Math.random()
      radii[i] = 1.6 + Math.random() * 1.0
    }
    return { positions, seeds, radii }
  }, [count])

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uColor: { value: new THREE.Color('#9B82FF') },
      uSize: { value: 6.0 },
    }),
    [],
  )

  useFrame((state) => {
    uniforms.uTime.value = state.clock.getElapsedTime()
    if (ref.current) {
      ref.current.rotation.y += 0.0015
      ref.current.rotation.x = scrollProgress * 0.4
    }
  })

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
        <bufferAttribute
          attach="attributes-aSeed"
          args={[seeds, 1]}
        />
        <bufferAttribute
          attach="attributes-aRadius"
          args={[radii, 1]}
        />
      </bufferGeometry>
      <shaderMaterial
        uniforms={uniforms}
        vertexShader={PARTICLES_VERT}
        fragmentShader={PARTICLES_FRAG}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  )
}

// ─── Soft halo (sprite-like back-side sphere) ────────────────────────────────

function Halo() {
  return (
    <mesh scale={1.9}>
      <sphereGeometry args={[1, 32, 32]} />
      <meshBasicMaterial
        color="#7C5CFF"
        transparent
        opacity={0.06}
        side={THREE.BackSide}
        depthWrite={false}
      />
    </mesh>
  )
}

// ─── Scene ───────────────────────────────────────────────────────────────────

function Scene({ scrollProgress, cursor }: OrbProps) {
  const { gl } = useThree()
  // Ensure premultiplied alpha for clean fresnel halos
  React.useEffect(() => {
    gl.setClearColor(0x000000, 0)
  }, [gl])

  return (
    <>
      <ambientLight intensity={0.5} />
      <pointLight position={[3, 3, 3]} intensity={1.1} color="#9B82FF" />
      <pointLight position={[-3, -2, 2]} intensity={0.6} color="#5E3FE6" />
      <Halo />
      <IsoOrb scrollProgress={scrollProgress} cursor={cursor} />
      <ParticleAura count={800} scrollProgress={scrollProgress} />
    </>
  )
}

// ─── Public component ───────────────────────────────────────────────────────

function NexusOrbScene({ scrollProgress = 0, cursor = { x: 0, y: 0 }, className }: OrbProps) {
  return (
    <div className={className} style={{ width: '100%', height: '100%' }} aria-hidden>
      <Canvas
        camera={{ position: [0, 0, 4.4], fov: 42 }}
        gl={{ alpha: true, antialias: true, powerPreference: 'high-performance' }}
        dpr={[1, 1.5]}
      >
        <Suspense fallback={null}>
          <Scene scrollProgress={scrollProgress} cursor={cursor} />
        </Suspense>
      </Canvas>
    </div>
  )
}

export const NexusOrb = dynamic(() => Promise.resolve(NexusOrbScene), {
  ssr: false,
})

export default NexusOrbScene
