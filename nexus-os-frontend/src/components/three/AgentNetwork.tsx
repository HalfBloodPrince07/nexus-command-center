"use client";

import React, { useState, useEffect, useRef, Suspense } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import type { ThreeEvent } from '@react-three/fiber';
import { OrbitControls, Sphere, Text, Points, shaderMaterial } from '@react-three/drei';
import * as THREE from 'three';
import { ForceGraph3D } from 'react-force-graph-3d';

// Particle shader for animated edges
const ParticleMaterial = shaderMaterial(
  {
    uTime: 0,
    uSize: 2.0,
    uColor: new THREE.Color(0xffffff)
  },
  // Vertex shader
  `attribute float size;
   attribute vec3 aColor;
   uniform float uTime;
   uniform float uSize;
   
   void main() {
     vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
     
     // Animate particles along the edge
     float progress = mod(uTime * 0.005 + position.z * 0.01, 1.0);
     vec3 animatedPosition = mix(position, vec3(0.0, 0.0, 0.0), progress);
     
     gl_Position = projectionMatrix * modelViewMatrix * vec4(animatedPosition, 1.0);
     gl_PointSize = size * uSize * (300.0 / -mvPosition.z);
   }`,
  // Fragment shader
  `uniform vec3 uColor;
   
   void main() {
     float distanceToCenter = distance(gl_PointCoord, vec2(0.5));
     if (distanceToCenter > 0.5) discard;
     
     float alpha = 1.0 - (distanceToCenter * 2.0);
     gl_FragColor = vec4(uColor, alpha);
   }`
);

interface AgentNode {
  id: string;
  name: string;
  cluster: 'knowledge' | 'research' | 'journal' | 'memory' | 'custom';
  activity: number; // 0-1 scale
  last_active: string;
  color: string;
}

interface AgentMessage {
  from: string;
  to: string;
  message_type: string;
  timestamp: string;
  payload?: any;
}

interface AgentNetworkProps {
  onAgentClick?: (agent: AgentNode) => void; // Click to inspect callback
  maxNodes?: number;
  maxEdges?: number;
}

// -- Agency colors (matches personality YAML)
const AGENT_COLORS: Record<string, string> = {
  supervisor: '#3B82F6',
  journal_lead: '#8B5CF6',
  knowledge_lead: '#F59E0B',
  memory_archivist: '#FB923C',
  research_lead: '#E11D48',
  fact_checker: '#06B6D4',
  scraper_agent: '#10B981',
  web_scout: '#14B8A6',
  mood_analyst: '#C084FC',
  outline_architect: '#F59E0B',
  section_drafter: '#EC4899',
  synthesis_director: '#A78BFA',
  rag_retriever: '#7C2D12',
  query_architect: '#F59E0B',
  user: '#94A3B8',
  unknown: '#6B7280'
};

// ----- HOOK: Agent Network WebSocket -----
function useAgentNetworkWebSocket(onMessage: (msg: AgentMessage) => void, onHistory?: (messages: AgentMessage[]) => void) {
  const ws = useRef<WebSocket | null>(null);
  const clientId = useRef(`web_${Math.random().toString(36).substring(7)}`);

  useEffect(() => {
    const connect = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/agent-network?client_id=${clientId.current}`;
      
      ws.current = new WebSocket(wsUrl);

      ws.current.onopen = () => {
        console.log('Agent network WebSocket connected');
      };

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'agent_message' && data.data) {
            onMessage(data.data as AgentMessage);
          } else if (data.type === 'history' && onHistory) {
            onHistory(data.messages as AgentMessage[]);
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.current.onerror = (error) => {
        console.error('Agent network WebSocket error:', error);
      };

      ws.current.onclose = () => {
        console.log('Agent network WebSocket disconnected');
        // Attempt to reconnect after 5 seconds
        setTimeout(connect, 5000);
      };
    };

    connect();

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [onMessage, onHistory]);

  return ws.current;
}

// ----- 3D Network Scene Component -----
function NetworkScene({ onAgentClick, maxEdges = 50 }: AgentNetworkProps) {
  const [nodes, setNodes] = useState<AgentNode[]>([]);
  const [edges, setEdges] = useState<Array<{ source: string; target: string; intensity: number }>>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentNode | null>(null);
  
  // Use WebSocket to get real-time agent messages
  const handleNewMessage = (msg: AgentMessage) => {
    const now = new Date().toISOString();
    
    // Ensure both nodes exist
    const fromNode = ensureNode(msg.from, now);
    const toNode = ensureNode(msg.to, now);
    
    // Update activity levels
    updateNodeActivity(fromNode, 0.3);
    updateNodeActivity(toNode, 0.5);
    
    // Add or update edge
    setEdges(prevEdges => {
      const existingIndex = prevEdges.findIndex(
        e => e.source === msg.from && e.target === msg.to
      );
      
      let newEdges;
      if (existingIndex >= 0) {
        // Update existing edge intensity
        newEdges = [...prevEdges];
        newEdges[existingIndex] = {
          ...newEdges[existingIndex],
          intensity: Math.min(prevEdges[existingIndex].intensity + 0.1, 1.0)
        };
      } else {
        // Add new edge
        newEdges = [...prevEdges, { source: msg.from, target: msg.to, intensity: 0.5 }];
        // Keep only the most recent edges
        newEdges = newEdges.slice(-maxEdges);
      }
      return newEdges;
    });
  };

  const handleHistory = (messages: AgentMessage[]) => {
    // Initialize graph with historical messages
    messages.forEach(handleNewMessage);
  };

  useAgentNetworkWebSocket(handleNewMessage, handleHistory);

  const ensureNode = (agentId: string, timestamp: string): AgentNode => {
    setNodes(prevNodes => {
      const existing = prevNodes.find(n => n.id === agentId);
      if (existing) return existing;
      
      const cluster = inferCluster(agentId);
      return {
        id: agentId,
        name: agentId.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()),
        cluster,
        activity: 0.1,
        last_active: timestamp,
        color: AGENT_COLORS[agentId] || AGENT_COLORS.unknown
      };
    });
    
    return nodes.find(n => n.id === agentId) || {
      id: agentId,
      name: agentId.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()),
      cluster: inferCluster(agentId),
      activity: 0.1,
      last_active: timestamp,
      color: AGENT_COLORS[agentId] || AGENT_COLORS.unknown
    };
  };

  const updateNodeActivity = (agentId: string, delta: number) => {
    setNodes(prevNodes => 
      prevNodes.map(n => 
        n.id === agentId
          ? { ...n, activity: Math.min(1.0, n.activity + delta) }
          : n
      )
    );
    
    // Gradually decay activity over time
    setTimeout(() => {
      setNodes(prevNodes =>
        prevNodes.map(n =>
          n.id === agentId
            ? { ...n, activity: Math.max(0.1, n.activity * 0.5) }
            : n
        )
      );
    }, 5000);
  };

  const onNodeClick = (event: ThreeEvent<MouseEvent>, nodeData: any) => {
    event.stopPropagation();
    const agent = nodes.find(n => n.id === nodeData.id);
    if (agent) {
      setSelectedAgent(agent);
      onAgentClick?.(agent);
    }
  };

  // Create a simple force-directed graph using Custom shader particles for edges
  const data = {
    nodes: nodes.map(n => ({ id: n.id, name: n.name, color: n.color, val: 5 + n.activity * 20 })),
    links: edges.map(e => ({ source: e.source, target: e.target, value: e.intensity }))
  } as any;

  return (
    <group>
      {/* Center particle field for all agent communications */}
      <PointsMaterial
        attach="material"
        color={new THREE.Color(0xffffff)}
        size={2}
        sizeAttenuation
        transparent
        opacity={0.8}
      />
      
      {/* Use react-force-graph-3d for main visualization */}
      <ForceGraph3D
        graphData={data}
        nodeLabel="name"
        nodeColor="color"
        nodeRelSize={6}
        nodeVal="val"
        linkColor={() => 'rgba(148, 163, 184, 0.6)'}
        linkWidth={2}
        linkDirectionalParticles={2}
        linkDirectionalParticleColor={() => '#3B82F6'}
        linkDirectionalParticleWidth={3}
        onNodeClick={onNodeClick}
        backgroundColor="rgba(0, 0, 0, 0)"
        enableNodeDrag={false}
        enableZoomInteraction={true}
        enablePanInteraction={true}
        enableRotationInteraction={true}
        width={window.innerWidth}
        height={window.innerHeight}
      />
    </group>
  );
}

// Utility to infer agent cluster based on name
function inferCluster(agentId: string): AgentNode['cluster'] {
  if (agentId.includes('journal') || agentId.includes('mood') || agentId.includes('life')) {
    return 'journal';
  }
  if (agentId.includes('research') || agentId.includes('scraper') || agentId.includes('scout')) {
    return 'research';
  }
  if (agentId.includes('memory') || agentId.includes('archivist') || agentId.includes('knowledge')) {
    return 'memory';
  }
  if (agentId.includes('custom')) {
    return 'custom';
  }
  return 'knowledge';
}

// ----- Main AgentNetwork Component -----
export default function AgentNetwork(props: AgentNetworkProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Visibility optimization via Intersection Observer
    if (!canvasRef.current) return;
    
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        setIsVisible(entry.isIntersecting);
      });
    }, { threshold: 0.1 });
    
    observer.observe(canvasRef.current);
    
    return () => observer.disconnect();
  }, []);

  if (!isVisible) {
    return  null; // Offscreen performance optimization
  }

  return (
    <Suspe promise fallback={<LoadingFallback />}>
      <div ref={canvasRef} className="w-full h-full relative">
        <Canvas
          camera={{ position: [0, 0, 500], fov: 75 }}
          performance={{ maxPixelRatio: 2 }}
          frameloop="always"
        >
          <ambientLight intensity={0.5} />
          <pointLight position={[10, 10, 10]} intensity={0.8} />
          <NetworkScene {...props} />
          <OrbitControls
            enablePan={true}
            enableZoom={true}
            enableRotate={true}
            minDistance={100}
            maxDistance={1000}
          />
        </Canvas>
      </div>
    </Suspe
  );
}

function LoadingFallback() {
  return (
    <div className="w-full h-full flex items-center justify-center text-sm text-gray-500">
      <div className="flex items-center gap-2">
        <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
        Loading agent network...
      </div>
    </div>
  );
}