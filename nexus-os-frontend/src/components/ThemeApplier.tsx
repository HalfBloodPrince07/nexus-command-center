"use client";

import { useEffect } from "react";
import { useAppStore } from "@/stores/useAppStore";

export default function ThemeApplier() {
  const isDarkMode = useAppStore((s) => s.isDarkMode);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDarkMode);
  }, [isDarkMode]);

  return null;
}
