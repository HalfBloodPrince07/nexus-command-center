/**
 * NEXUS OS - Multi-Agent AI Platform Landing Page
 *
 * A stunning, interactive landing page with 3D visualizations, glassmorphism,
 * and smooth animations. Built with Next.js 14 + React Three Fiber + Tailwind CSS.
 */

'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import {
  Float,
  MeshDistortMaterial,
  OrbitControls,
  Stars,
  Sparkles,
  Text as ThreeText,
  PerspectiveCamera,
} from '@react-three/drei';
import { motion, AnimatePresence } from 'framer-motion';
import Link from 'next/link';

// ============================================
// TYPES & INTERFACES
// ============================================

interface AgentCardProps {
  name: string;
  status: 'active' | 'thinking' | 'idle';
  task: string;
  tools: string[];
  index?: number;
}

interface StatBoxProps {
  label: string;
  value: string;
  icon: React.ReactNode;
  trend?: string;
  color: string;
}

// ============================================
// THREE.JS COMPONENTS - 3D VISUALIZATIONS
// ============================================

const NeuralNetwork: React.FC = () => {
  const meshRef = useRef<any>(null);

  useFrame((state) => {
    if (meshRef.current) {
      // Gentle floating animation
      meshRef.current.rotation.x += 0.002;
      meshRef.current.rotation.y += 0.003;
    }
  });

  return (
    <Float speed={2} rotationIntensity={1.5} floatIntensity={2}>
      <mesh ref={meshRef} scale={[2, 2, 2]}>
        {/* Icosahedron - geometric network shape */}
        <icosahedronGeometry args={[1, 0]} />
        <MeshDistortMaterial
          color="#6366f1"
          attach="material"
          distort={0.4}
          speed={2}
          roughness={0.2}
          metalness={0.8}
        />
      </mesh>
    </Float>
  );
};

const OrbitingNodes: React.FC = () => {
  const nodesRef = useRef<any[]>([]);

  useFrame((state) => {
    nodesRef.current.forEach((node, i) => {
      node.position.x += Math.cos(state.clock.elapsedTime + i * 1.3) * 0.02;
      node.position.z += Math.sin(state.clock.elapsedTime + i * 1.7) * 0.02;
    });
  });

  return (
    <>
      {[...Array(6)].map((_, i) => (
        <mesh key={i} ref={(el) => (nodesRef.current[i] = el)}>
          <sphereGeometry args={[0.15, 16, 16]} />
          <meshStandardMaterial color="#8b5cf6" emissive="#8b5cf6" emissiveIntensity={2} />
        </mesh>
      ))}
    </>
  );
};

const HeroScene: React.FC = () => {
  return (
    <>
      <PerspectiveCamera makeDefault position={[0, 0, 8]} fov={50} />
      <ambientLight intensity={0.5} />
      <pointLight position={[10, 10, 10]} intensity={1} color="#a78bfa" />
      <pointLight position={[-10, -10, -5]} intensity={0.8} color="#2dd4bf" />

      {/* Background stars and sparkles */}
      <Stars radius={100} depth={50} count={5000} factor={4} saturation={0} fade speed={1} />
      <Sparkles count={200} scale={[10, 10, 10]} size={2} speed={0.4} opacity={0.5} color="#c4b5fd" />

      {/* Main 3D elements */}
      <group>
        <NeuralNetwork />
        <OrbitingNodes />
      </group>
    </>
  );
};

const ArchitectureScene: React.FC = () => {
  return (
    <>
      <PerspectiveCamera makeDefault position={[0, 0, 12]} fov={45} />
      <ambientLight intensity={0.3} />

      {/* Flow container */}
      <group>
        {[
          { x: -6, y: 0 },
          { x: 0, y: 2 },
          { x: 6, y: 0 },
        ].map((pos, i) => (
          <mesh key={i} position={[pos.x, pos.y, 0]}>
            <boxGeometry args={[1.5, 1.5, 1]} />
            <MeshDistortMaterial
              color={['#2dd4bf', '#8b5cf6', '#fbbf24'][i % 3]}
              attach="material"
              distort={0.2}
              speed={1}
            />
          </mesh>
        ))}

        {/* Connecting lines (simple spheres representing flow) */}
        <mesh position={[-3, 1, 0]}>
          <sphereGeometry args={[0.25]} />
          <meshStandardMaterial color="#ffffff" emissive="#a78bfa" emissiveIntensity={1} />
        </mesh>
      </group>
    </>
  );
};

// ============================================
// UI COMPONENTS - GLASSMORPHISM & CARDS
// ============================================

const GlassCard: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => (
  <div
    className={`backdrop-blur-xl bg-gradient-to-br from-white/10 to-white/5 border border-white/20 rounded-3xl shadow-2xl ${className}`}
  >
    {children}
  </div>
);

const GlassPanel: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => (
  <div
    className={`backdrop-blur-md bg-black/40 border border-white/10 rounded-2xl ${className}`}
  >
    {children}
  </div>
);

const StatusDot: React.FC<{ status: AgentCardProps['status'] }> = ({ status }) => {
  const colors = {
    active: 'bg-emerald-500',
    thinking: 'bg-amber-400',
    idle: 'bg-red-500',
  };

  return (
    <span className="flex items-center gap-2">
      <span
        className={`${colors[status]} w-2 h-2 rounded-full animate-pulse`}
        style={{ animationDuration: '1.5s' }}
      />
      <span className={`text-xs font-medium capitalize ${status === 'active' ? 'text-emerald-400' : status === 'thinking' ? 'text-amber-400' : 'text-red-400'}`}>
        {status}
      </span>
    </span>
  );
};

const ToolBadge: React.FC<{ tool: string }> = ({ tool }) => (
  <span className="px-2 py-1 text-xs font-medium bg-white/10 border border-white/10 rounded-md text-gray-300">
    {tool}
  </span>
);

// ============================================
// FEATURE COMPONENTS
// ============================================

const AgentCard: React.FC<AgentCardProps> = ({ name, status, task, tools }) => {
  return (
    <GlassCard className="p-5 hover:border-white/30 transition-all duration-300 hover:bg-gradient-to-br hover:from-white/15 hover:to-white/8 group">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          {/* Avatar with glow effect */}
          <div className="relative">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-lg shadow-lg group-hover:shadow-purple-500/50 transition-shadow duration-300">
              {name.charAt(0)}
            </div>
            <StatusDot status={status} />
          </div>

          <div>
            <h3 className="font-semibold text-white">{name}</h3>
            <p className="text-xs text-gray-400 mt-1 truncate max-w-[120px]">{task}</p>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {tools.map((tool) => (
          <ToolBadge key={tool} tool={tool} />
        ))}
      </div>
    </GlassCard>
  );
};

const StatBox: React.FC<StatBoxProps> = ({ label, value, icon, trend, color }) => {
  return (
    <GlassPanel className="p-5 hover:bg-white/10 transition-colors duration-300">
      <div className="flex items-center gap-4 mb-2">
        <div className={`w-10 h-10 rounded-xl ${color} bg-opacity-20 flex items-center justify-center`}>
          {icon}
        </div>
        <span className="text-gray-400 text-sm">{label}</span>
      </div>

      <div className="flex items-end justify-between">
        <span className="text-2xl font-bold text-white">{value}</span>
        {trend && (
          <span className={`text-xs ${trend.startsWith('+') ? 'text-emerald-400' : 'text-red-400'}`}>
            {trend}
          </span>
        )}
      </div>
    </GlassPanel>
  );
};

const FeatureCard: React.FC<{ title: string; description: string; icon: React.ReactNode; delay?: number }> = ({
  title,
  description,
  icon,
  delay = 0,
}) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    whileInView={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.5, delay }}
    viewport={{ once: true }}
  >
    <GlassCard className="p-6 hover:border-white/30 transition-all duration-300 h-full">
      <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center mb-4 shadow-lg shadow-cyan-500/20">
        {icon}
      </div>
      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      <p className="text-gray-400 leading-relaxed">{description}</p>
    </GlassCard>
  </motion.div>
);

// ============================================
// LANDING PAGE MAIN COMPONENT
// ============================================

export default function LandingPage() {
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePosition({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  const agents = [
    { name: 'Research Agent', status: 'active', task: 'Analyzing market trends...', tools: ['RAG', 'Web Search'] },
    { name: 'Code Reviewer', status: 'thinking', task: 'Reviewing PR #42...', tools: ['Git', 'TypeScript'] },
    { name: 'Data Analyst', status: 'idle', task: 'Awaiting new dataset...', tools: ['Pandas', 'Visualization'] },
    { name: 'QA Bot', status: 'active', task: 'Running test suite...', tools: ['Playwright', 'Pytest'] },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0a0a0f] via-[#12121a] to-[#0d0d14] text-white overflow-x-hidden">
      {/* Dynamic background gradient based on mouse position */}
      <div
        className="fixed inset-0 pointer-events-none opacity-30"
        style={{
          background: `radial-gradient(600px circle at ${mousePosition.x}px ${mousePosition.y}px, rgba(99, 102, 241, 0.15), transparent 40%)`,
        }}
      />

      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl bg-black/30 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center font-bold text-white shadow-lg">
              N
            </div>
            <span className="font-semibold text-xl tracking-tight group-hover:text-transparent group-hover:bg-clip-text group-hover:bg-gradient-to-r group-hover:from-indigo-400 group-hover:to-purple-400 transition-all">
              Nexus OS
            </span>
          </Link>

          <div className="hidden md:flex items-center gap-8 text-sm">
            {['Features', 'Agents', 'Documentation', 'Pricing'].map((item) => (
              <a key={item} href={`#${item.toLowerCase()}`} className="text-gray-400 hover:text-white transition-colors">
                {item}
              </a>
            ))}
          </div>

          <Link href="/deploy" className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 font-medium text-sm hover:shadow-lg hover:shadow-indigo-500/30 transition-all">
            Deploy Agents
          </Link>
        </div>
      </nav>

      <main className="pt-24">
        {/* Hero Section */}
        <section className="min-h-[90vh] flex items-center justify-center relative px-6">
          {/* Canvas for 3D visualization */}
          <div className="absolute inset-0 z-0 opacity-50">
            <Canvas>
              <HeroScene />
            </Canvas>
          </div>

          {/* Hero Content */}
          <div className="relative z-10 text-center max-w-4xl mx-auto py-20">
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8 }}
            >
              {/* Badge */}
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 mb-6">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-sm text-gray-300">v2.0 Now Available</span>
              </div>

              {/* Headline */}
              <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold tracking-tight mb-6 leading-tight">
                <span className="bg-gradient-to-r from-white via-gray-200 to-gray-400 bg-clip-text text-transparent">
                  Local Multi-Agent{' '}
                </span>
                <span className="bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
                  Orchestration
                </span>
              </h1>

              {/* Subheadline */}
              <p className="text-lg md:text-xl text-gray-400 max-w-2xl mx-auto mb-8 leading-relaxed">
                Deploy powerful AI agents locally with enterprise-grade orchestration.
                No cloud dependencies, full data privacy, unlimited scale.
              </p>

              {/* CTAs */}
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link href="/deploy" className="group px-8 py-4 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 font-semibold text-white hover:shadow-xl hover:shadow-indigo-500/30 transition-all flex items-center gap-2">
                  <span>Deploy Agents</span>
                  <svg className="w-4 h-4 group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                  </svg>
                </Link>
                <Link href="/docs" className="px-8 py-4 rounded-xl bg-white/5 border border-white/20 font-medium text-gray-300 hover:bg-white/10 transition-all">
                  View Documentation
                </Link>
              </div>

              {/* Stats Preview */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4, duration: 0.6 }}
                className="mt-16 grid grid-cols-3 gap-4 max-w-lg mx-auto"
              >
                {[
                  { value: '99.9%', label: 'Uptime' },
                  { value: '<50ms', label: 'Latency' },
                  { value: '∞', label: 'Scalability' },
                ].map((stat) => (
                  <div key={stat.label} className="text-center p-4 rounded-xl bg-white/5 border border-white/10">
                    <div className="text-2xl font-bold text-indigo-400">{stat.value}</div>
                    <div className="text-xs text-gray-500">{stat.label}</div>
                  </div>
                ))}
              </motion.div>
            </motion.div>

            {/* Scroll indicator */}
            <motion.div
              animate={{ y: [0, 10, 0] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="absolute bottom-8 left-1/2 -translate-x-1/2"
            >
              <div className="w-6 h-10 rounded-full border-2 border-white/30 flex justify-center pt-2">
                <div className="w-1.5 h-3 bg-gradient-to-b from-indigo-400 to-purple-400 rounded-full" />
              </div>
            </motion.div>
          </div>
        </section>

        {/* Stats Dashboard - Bento Grid */}
        <section id="features" className="py-24 px-6 relative">
          <div className="max-w-7xl mx-auto">
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-5xl font-bold tracking-tight mb-4">
                System Performance
              </h2>
              <p className="text-gray-400 max-w-xl mx-auto">
                Real-time metrics from our production environment. Built for scale, designed for reliability.
              </p>
            </div>

            {/* Bento Grid Stats */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-16">
              <StatBox
                label="Tokens Processed"
                value="348M+"
                icon={
                  <svg className="w-5 h-5 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                }
                trend="+18.4%"
                color="bg-indigo-500/30 border-indigo-500/50 text-indigo-400"
              />
              <StatBox
                label="Avg Latency"
                value="42ms"
                icon={
                  <svg className="w-5 h-5 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                }
                trend="-12%"
                color="bg-cyan-500/30 border-cyan-500/50 text-cyan-400"
              />
              <StatBox
                label="Active Sessions"
                value="8,247"
                icon={
                  <svg className="w-5 h-5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                }
                color="bg-purple-500/30 border-purple-500/50 text-purple-400"
              />
              <StatBox
                label="Agent Handoffs"
                value="98.7%"
                icon={
                  <svg className="w-5 h-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                  </svg>
                }
                color="bg-emerald-500/30 border-emerald-500/50 text-emerald-400"
              />
            </div>

            {/* VRAM Usage Panel */}
            <GlassCard className="p-8">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
                <div>
                  <h3 className="text-xl font-semibold mb-6 flex items-center gap-3">
                    <svg className="w-6 h-6 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                    </svg>
                    VRAM Utilization
                  </h3>
                  <div className="space-y-4">
                    {[
                      { label: 'Primary GPU (RTX 4090)', used: 12, total: 16 },
                      { label: 'Secondary GPU', used: 8.5, total: 16 },
                      { label: 'System RAM Spill', used: 3.2, total: 32 },
                    ].map((gpu) => (
                      <div key={gpu.label}>
                        <div className="flex justify-between text-sm mb-1">
                          <span>{gpu.label}</span>
                          <span className="text-gray-400">{gpu.used}GB / {gpu.total}GB</span>
                        </div>
                        <div className="h-2 rounded-full bg-white/10 overflow-hidden">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${(gpu.used / gpu.total) * 100}%` }}
                            transition={{ duration: 1, delay: 0.5 }}
                            className="h-full rounded-full bg-gradient-to-r from-violet-500 to-purple-600"
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Mini 3D visualization */}
                <div className="h-48">
                  <Canvas camera={{ position: [0, 0, 4], fov: 50 }}>
                    <ambientLight intensity={0.5} />
                    <pointLight position={[2, 2, 2]} intensity={1} />
                    <Float speed={3}>
                      <mesh>
                        <octahedronGeometry args={[1, 0]} />
                        <MeshDistortMaterial color="#a78bfa" distort={0.5} speed={2} />
                      </mesh>
                    </Float>
                  </Canvas>
                </div>
              </div>
            </GlassCard>

            {/* Active Agents Grid */}
            <div className="mt-16">
              <h3 className="text-2xl font-bold mb-8 flex items-center gap-3">
                <svg className="w-7 h-7 text-pink-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                Active Agents Overview
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {agents.map((agent, index) => (
                  <AgentCard key={index} {...agent} index={index} />
                ))}
              </div>
            </div>

            {/* Architecture Section */}
            <div className="mt-24 grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
              <GlassCard className="p-8 h-full flex flex-col justify-center">
                <h3 className="text-2xl font-bold mb-6">System Architecture</h3>

                {/* Flow diagram using CSS */}
                <div className="flex items-start gap-4 mb-12 relative">
                  {/* Connecting line */}
                  <svg className="absolute left-[50%] top-8 w-full h-1 -translate-x-1/2 pointer-events-none" style={{ zIndex: 0 }}>
                    <path d="M0,32 C60,32 60,-8 140,-8 C220,-8 220,32 280,32" fill="none" stroke="url(#flowGradient)" strokeWidth={2} />
                    <defs>
                      <linearGradient id="flowGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="#2dd4bf" />
                        <stop offset="50%" stopColor="#8b5cf6" />
                        <stop offset="100%" stopColor="#fbbf24" />
                      </linearGradient>
                    </defs>
                  </svg>

                  {/* User Prompt */}
                  <GlassPanel className="px-6 py-4 flex items-center gap-3 relative z-10">
                    <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-400 font-bold text-sm">U</div>
                    <div>
                      <p className="text-xs text-gray-400">User Prompt</p>
                      <p className="font-mono text-sm">"Research quantum computing"</p>
                    </div>
                  </GlassPanel>

                  {/* Orchestrator */}
                  <GlassPanel className="px-6 py-4 flex items-center gap-3 relative z-10 bg-gradient-to-r from-cyan-500/20 to-blue-500/20">
                    <div className="w-8 h-8 rounded-full bg-cyan-500 flex items-center justify-center text-white font-bold text-sm">O</div>
                    <div>
                      <p className="text-xs text-gray-400">Orchestrator</p>
                      <p className="font-mono text-sm">Task Planner</p>
                    </div>
                  </GlassPanel>

                  {/* Sub-tasks */}
                  <GlassPanel className="px-6 py-4 flex items-center gap-3 relative z-10 bg-gradient-to-r from-purple-500/20 to-pink-500/20">
                    <div className="w-8 h-8 rounded-full bg-purple-500 flex items-center justify-center text-white font-bold text-sm">S</div>
                    <div>
                      <p className="text-xs text-gray-400">Sub-tasks</p>
                      <p className="font-mono text-sm">Plan Generation</p>
                    </div>
                  </GlassPanel>

                  {/* Agents */}
                  <GlassPanel className="px-6 py-4 flex items-center gap-3 relative z-10 bg-gradient-to-r from-emerald-500/20 to-green-500/20">
                    <div className="w-8 h-8 rounded-full bg-emerald-500 flex items-center justify-center text-white font-bold text-sm">A</div>
                    <div>
                      <p className="text-xs text-gray-400">Agents</p>
                      <p className="font-mono text-sm">Execute & Report</p>
                    </div>
                  </GlassPanel>

                  {/* Response */}
                  <GlassPanel className="px-6 py-4 flex items-center gap-3 relative z-10">
                    <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center text-green-400 font-bold text-sm">R</div>
                    <div>
                      <p className="text-xs text-gray-400">Response</p>
                      <p className="font-mono text-sm">Structured Output</p>
                    </div>
                  </GlassPanel>
                </div>

                {/* Features list */}
                <ul className="space-y-3">
                  {[
                    { icon: '🧠', text: 'Context-aware task decomposition' },
                    { icon: '⚡', text: 'Distributed execution across agents' },
                    { icon: '🔒', text: 'Local-first, privacy-preserving' },
                    { icon: '🔄', text: 'Self-correcting feedback loops' },
                  ].map((feature) => (
                    <li key={feature.text} className="flex items-center gap-3">
                      <span className="text-lg">{feature.icon}</span>
                      <span className="text-gray-400">{feature.text}</span>
                    </li>
                  ))}
                </ul>
              </GlassCard>

              {/* Mini 3D Architecture Scene */}
              <div className="h-[500px]">
                <Canvas>
                  <ArchitectureScene />
                </Canvas>
              </div>
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section id="features" className="py-24 px-6 bg-gradient-to-b from-transparent via-indigo-950/30 to-transparent">
          <div className="max-w-7xl mx-auto">
            <h2 className="text-3xl md:text-5xl font-bold text-center tracking-tight mb-4">
              Built for Developers
            </h2>
            <p className="text-gray-400 text-center max-w-xl mx-auto mb-16">
              Powerful features designed to help you orchestrate complex AI workflows with ease.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <FeatureCard
                title="Local Orchestration"
                description="Run your entire agent infrastructure locally. No cloud dependencies, no data leaks, complete control."
                icon={
                  <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
                  </svg>
                }
                delay={0}
              />

              <FeatureCard
                title="Multi-Agent Coordination"
                description="Coordinate dozens of specialized agents with intelligent routing, context sharing, and handoff management."
                icon={
                  <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                }
                delay={0.1}
              />

              <FeatureCard
                title="RAG Integration"
                description="Connect agents to your knowledge base with vector search, document chunking, and citation tracking."
                icon={
                  <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                }
                delay={0.2}
              />

              <FeatureCard
                title="Tool Execution"
                description="Agents can interact with APIs, filesystems, databases, and external services through safe, sandboxed execution."
                icon={
                  <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                  </svg>
                }
                delay={0.3}
              />

              <FeatureCard
                title="Persistent Memory"
                description="Long-term context storage for agents with semantic search, embeddings, and memory consolidation."
                icon={
                  <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                }
                delay={0.4}
              />

              <FeatureCard
                title="Observability Dashboard"
                description="Real-time monitoring of agent activity, token usage, latency metrics, and system health."
                icon={
                  <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                }
                delay={0.5}
              />
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="py-32 px-6">
          <GlassCard className="p-16 text-center relative overflow-hidden">
            {/* Background effects */}
            <div className="absolute inset-0 bg-gradient-to-r from-indigo-600/20 to-purple-600/20" />
            <div className="absolute top-0 left-0 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl -translate-x-1/2 -translate-y-1/2" />
            <div className="absolute bottom-0 right-0 w-96 h-96 bg-pink-500/10 rounded-full blur-3xl translate-x-1/2 translate-y-1/2" />

            <div className="relative z-10">
              <h2 className="text-4xl md:text-6xl font-bold tracking-tight mb-6">
                Ready to Deploy?
              </h2>
              <p className="text-lg text-gray-300 max-w-xl mx-auto mb-10">
                Start orchestrating your AI agents today. Local-first, privacy-preserving, and built for scale.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link href="/deploy" className="w-full sm:w-auto px-8 py-4 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 font-semibold text-white hover:shadow-xl hover:shadow-indigo-500/30 transition-all flex items-center justify-center gap-2">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Deploy Agents Now
                </Link>
                <a href="/docs" className="w-full sm:w-auto px-8 py-4 rounded-xl bg-white/5 border border-white/20 font-medium text-gray-300 hover:bg-white/10 transition-all">
                  Read the Docs
                </a>
              </div>
            </div>
          </GlassCard>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-[#0a0a0f] border-t border-white/10 py-16 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-12">
            <div className="md:col-span-2">
              <Link href="/" className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center font-bold text-white shadow-lg">
                  N
                </div>
                <span className="font-semibold text-xl tracking-tight">Nexus OS</span>
              </Link>
              <p className="text-gray-400 max-w-sm mb-6">
                Local multi-agent orchestration platform. Build powerful AI systems that respect your data and run entirely offline.
              </p>

              {/* Social links */}
              <div className="flex gap-4">
                {['GitHub', 'Twitter', 'Discord'].map((social) => (
                  <a key={social} href="#" className="w-10 h-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-gray-400 hover:bg-white/10 hover:text-white transition-all">
                    {/* Social icon placeholder */}
                    <span className="text-xs">{social.charAt(0)}</span>
                  </a>
                ))}
              </div>
            </div>

            <div>
              <h4 className="font-semibold mb-4 text-white">Product</h4>
              <ul className="space-y-2">
                {['Features', 'Integrations', 'Pricing', 'Changelog'].map((item) => (
                  <li key={item}>
                    <a href="#" className="text-gray-400 hover:text-white transition-colors text-sm">
                      {item}
                    </a>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h4 className="font-semibold mb-4 text-white">Resources</h4>
              <ul className="space-y-2">
                {['Documentation', 'API Reference', 'Community', 'Help Center'].map((item) => (
                  <li key={item}>
                    <a href="#" className="text-gray-400 hover:text-white transition-colors text-sm">
                      {item}
                    </a>
                  </li>
                ))}
              </ul>

              {/* System Status */}
              <div className="mt-6 pt-6 border-t border-white/10 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-sm text-gray-400">System Status: Operational</span>
              </div>
            </div>
          </div>

          <div className="pt-8 border-t border-white/10 flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-gray-500 text-sm">© 2026 Nexus OS. All rights reserved.</p>
            <div className="flex items-center gap-6 text-sm text-gray-500">
              <a href="#" className="hover:text-white transition-colors">Privacy</a>
              <a href="#" className="hover:text-white transition-colors">Terms</a>
              <a href="#" className="hover:text-white transition-colors">Security</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

/*
 * Installation & Usage:
 *
 * npm install three @react-three/fiber @react-three/drei framer-motion
 *
 * Copy the CSS/Tailwind classes as needed. This uses Tailwind CSS - ensure it's configured with dark mode and extended color palette for optimal results.
 */
