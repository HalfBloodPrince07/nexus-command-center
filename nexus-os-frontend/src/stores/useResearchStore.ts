"use client";

import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import { devtools } from "zustand/middleware";
import type {
  ResearchJob,
  ResearchReport,
  ResearchSource,
  PipelineAgentState,
  PipelineLogEntry,
  SectionProgress,
  ClaimProgress,
  OutputPaths,
} from "@/types/research";

interface ResearchState {
  activeJob: ResearchJob | null;
  reports: ResearchReport[];
  sources: ResearchSource[];
  activeSubTab: "new" | "library" | "sources";
  viewingSlug: string | null;
  viewingReport: { content: string; metadata: ResearchReport } | null;
  isLoading: boolean;

  startJob: (topic: string, jobId: string, slug: string) => void;
  updatePipelineAgent: (agentId: string, updates: Partial<PipelineAgentState>) => void;
  markAgentComplete: (agentId: string, badge?: string) => void;
  completeJob: (report: ResearchReport) => void;
  failJob: (error: string) => void;
  addLog: (agent: string, detail: string) => void;
  setSectionProgress: (progress: Partial<SectionProgress>) => void;
  setClaimProgress: (progress: Partial<ClaimProgress>) => void;
  setOutputPaths: (paths: OutputPaths) => void;
  setOutlineSections: (count: number) => void;
  setReports: (reports: ResearchReport[]) => void;
  setSources: (sources: ResearchSource[]) => void;
  setActiveSubTab: (tab: "new" | "library" | "sources") => void;
  openReport: (slug: string, content: string, metadata: ResearchReport) => void;
  closeReport: () => void;
  setLoading: (loading: boolean) => void;
  removeReport: (slug: string) => void;
}

const INITIAL_PIPELINE: PipelineAgentState[] = [
  { id: "Atlas",             label: "Research Lead",    stage: "idle", detail: "", status: "idle" },
  { id: "Vector",            label: "Web Scout",        stage: "idle", detail: "", status: "idle" },
  { id: "Fetch",             label: "Scraper",          stage: "idle", detail: "", status: "idle" },
  { id: "OutlineArchitect",  label: "Outline Builder",  stage: "idle", detail: "", status: "idle" },
  { id: "SectionDrafter",   label: "Section Drafter",  stage: "idle", detail: "", status: "idle" },
  { id: "SynthesisDirector", label: "Synthesizer",      stage: "idle", detail: "", status: "idle" },
  { id: "Verity",            label: "Fact Checker",     stage: "idle", detail: "", status: "idle" },
  { id: "Scribe",            label: "Report Builder",   stage: "idle", detail: "", status: "idle" },
  { id: "Exporter",          label: "Output Formatter", stage: "idle", detail: "", status: "idle" },
];

const EMPTY_SECTION_PROGRESS: SectionProgress = { total: 0, done: 0, currentTitle: "" };
const EMPTY_CLAIM_PROGRESS: ClaimProgress = { total: 0, verified: 0, hallucinated: 0, unverified: 0 };

function nowHHMMSS(): string {
  return new Date().toTimeString().slice(0, 8);
}

export const useResearchStore = create<ResearchState>()(
  devtools(
    immer((set) => ({
      activeJob: null,
      reports: [],
      sources: [],
      activeSubTab: "new",
      viewingSlug: null,
      viewingReport: null,
      isLoading: false,

      startJob: (topic, jobId, slug) =>
        set((s) => {
          s.activeJob = {
            job_id: jobId,
            topic,
            slug,
            status: "running",
            pipeline: INITIAL_PIPELINE.map((a) => ({ ...a })),
            logs: [],
            sectionProgress: { ...EMPTY_SECTION_PROGRESS },
            claimProgress: { ...EMPTY_CLAIM_PROGRESS },
            outputPaths: {},
            outlineSections: 0,
          };
        }),

      updatePipelineAgent: (agentId, updates) =>
        set((s) => {
          if (!s.activeJob) return;
          const agent = s.activeJob.pipeline.find((a) => a.id === agentId);
          if (agent) Object.assign(agent, updates);
        }),

      markAgentComplete: (agentId, badge) =>
        set((s) => {
          if (!s.activeJob) return;
          const agent = s.activeJob.pipeline.find((a) => a.id === agentId);
          if (agent) {
            agent.status = "complete";
            agent.stage = "complete";
            if (badge !== undefined) agent.badge = badge;
          }
        }),

      completeJob: (report) =>
        set((s) => {
          if (s.activeJob) {
            s.activeJob.status = "complete";
            s.activeJob.report = report;
            s.activeJob.pipeline.forEach((a) => {
              if (a.status !== "error") { a.status = "complete"; a.stage = "complete"; }
            });
          }
          const exists = s.reports.some((r) => r.slug === report.slug);
          if (!exists) s.reports.unshift(report);
        }),

      failJob: (error) =>
        set((s) => {
          if (s.activeJob) {
            s.activeJob.status = "failed";
            s.activeJob.error = error;
            s.activeJob.pipeline.forEach((a) => {
              if (a.status === "active") a.status = "error";
            });
          }
        }),

      addLog: (agent, detail) =>
        set((s) => {
          if (!s.activeJob) return;
          s.activeJob.logs.push({ ts: nowHHMMSS(), agent, detail });
          if (s.activeJob.logs.length > 20) s.activeJob.logs.shift();
        }),

      setSectionProgress: (progress) =>
        set((s) => {
          if (!s.activeJob) return;
          Object.assign(s.activeJob.sectionProgress, progress);
        }),

      setClaimProgress: (progress) =>
        set((s) => {
          if (!s.activeJob) return;
          Object.assign(s.activeJob.claimProgress, progress);
        }),

      setOutputPaths: (paths) =>
        set((s) => {
          if (!s.activeJob) return;
          s.activeJob.outputPaths = paths;
        }),

      setOutlineSections: (count) =>
        set((s) => {
          if (!s.activeJob) return;
          s.activeJob.outlineSections = count;
          s.activeJob.sectionProgress.total = count;
        }),

      setReports: (reports) => set((s) => { s.reports = reports; }),
      setSources: (sources) => set((s) => { s.sources = sources; }),

      setActiveSubTab: (tab) => set((s) => { s.activeSubTab = tab; }),

      openReport: (slug, content, metadata) =>
        set((s) => {
          s.viewingSlug = slug;
          s.viewingReport = { content, metadata };
        }),

      closeReport: () =>
        set((s) => {
          s.viewingSlug = null;
          s.viewingReport = null;
        }),

      setLoading: (loading) => set((s) => { s.isLoading = loading; }),

      removeReport: (slug) =>
        set((s) => {
          s.reports = s.reports.filter((r) => r.slug !== slug);
          if (s.viewingSlug === slug) { s.viewingSlug = null; s.viewingReport = null; }
        }),
    })),
    { name: "ResearchStore", enabled: process.env.NODE_ENV === "development" }
  )
);
