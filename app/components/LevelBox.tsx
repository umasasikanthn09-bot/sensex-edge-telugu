import React from "react";

interface LevelBoxProps {
  title: string;
  value: string;
  type?: "ce" | "pe";
}

export default function LevelBox({
  title,
  value,
  type = "ce",
}: LevelBoxProps) {
  return (
    <div
      className={`
        w-full
        rounded-2xl
        border
        p-5
        backdrop-blur-xl
        shadow-lg
        transition-all
        duration-300
        hover:scale-105
        ${
          type === "ce"
            ? "border-green-400/40 bg-green-500/10"
            : "border-red-400/40 bg-red-500/10"
        }
      `}
    >
      <h3 className="text-center text-sm font-semibold uppercase tracking-wider text-yellow-300">
        {title}
      </h3>

      <p className="mt-3 text-center text-3xl font-bold text-white">
        {value}
      </p>
    </div>
  );
}