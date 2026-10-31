"use client";

import { useEffect, useState } from "react";
import { skillsApi } from "@/lib/api/endpoints/skills";
import { SkillCard } from "@/components/skills/skill-card";
import { SkillEditor } from "@/components/skills/skill-editor";

const DEFAULT_SKILLS = [
  {
    name: "brand-voice-audit",
    path: "skills/brand-voice-audit/SKILL.md",
    description: "Audits campaign draft copy against core brand tone, vocabulary prohibitions, and style guidelines. Activate during campaign creative review or when brand compliance scoring is requested.",
    tier: "Tier 1/2/3",
    status: "validated",
    valid: true,
    token_estimate: 349,
    lines_count: 26,
    tier3_resources: ["scripts/check_tone.py"],
    allowed_tools: ["mcp_brand_rag:search_brand_knowledge", "Bash(python3:scripts/check_tone.py)"],
  },
  {
    name: "multi-platform-copy",
    path: "skills/multi-platform-copy/SKILL.md",
    description: "Adapts master brand messaging across 8 social platforms conforming to strict character limits and native hook structures. Activate during creative copywriting and cross-platform adaptation workflows.",
    tier: "Tier 1/2/3",
    status: "validated",
    valid: true,
    token_estimate: 441,
    lines_count: 28,
    tier3_resources: ["references/PLATFORM_LIMITS.md"],
    allowed_tools: [],
  },
  {
    name: "competitor-recon",
    path: "skills/competitor-recon/SKILL.md",
    description: "Gathers competitor positioning, SERP rank signals, and content pillar breakdowns. Activate during research strategy formulation or market intelligence analysis.",
    tier: "Tier 1/2/3",
    status: "validated",
    valid: true,
    token_estimate: 363,
    lines_count: 29,
    tier3_resources: ["scripts/parse_serp.py"],
    allowed_tools: ["Bash(python3:scripts/parse_serp.py)"],
  },
  {
    name: "media-compliance",
    path: "skills/media-compliance/SKILL.md",
    description: "Validates media dimensions, aspect ratios, file sizes, and color palettes against platform rules. Activate during asset staging or media verification before publishing.",
    tier: "Tier 1/2/3",
    status: "validated",
    valid: true,
    token_estimate: 434,
    lines_count: 34,
    tier3_resources: ["assets/aspect_ratio_rules.json"],
    allowed_tools: [],
  },
];

export default function SkillsPage() {
  const [skills, setSkills] = useState<any[]>(DEFAULT_SKILLS);
  const [selectedSkill, setSelectedSkill] = useState<any>(DEFAULT_SKILLS[0]);
  const [skillContent, setSkillContent] = useState<string>("");

  useEffect(() => {
    skillsApi
      .list()
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setSkills(data);
          setSelectedSkill(data[0]);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedSkill?.name) {
      skillsApi
        .get(selectedSkill.name)
        .then((detail) => {
          if (detail?.content) {
            setSkillContent(detail.content);
          } else {
            setSkillContent(
              `---\nname: ${selectedSkill.name}\ndescription: ${selectedSkill.description}\ncompatibility: ${selectedSkill.compatibility || "Universal"}\nallowed-tools: ${(selectedSkill.allowed_tools || []).join(" ") || "none"}\n---\n\n# ${selectedSkill.name}\n\nTier 2 instructions loaded.`
            );
          }
        })
        .catch(() => {
          setSkillContent(
            `---\nname: ${selectedSkill.name}\ndescription: ${selectedSkill.description}\ncompatibility: ${selectedSkill.compatibility || "Universal"}\nallowed-tools: ${(selectedSkill.allowed_tools || []).join(" ") || "none"}\n---\n\n# ${selectedSkill.name}\n\nTier 2 procedural instructions loaded on demand.`
          );
        });
    }
  }, [selectedSkill]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Agent Skills (SKILL.md Packages)</h1>
          <p className="text-slate-400 text-sm">
            Progressive-disclosure domain playbooks adhering to the 3-tier agentskills.io standard.
          </p>
        </div>
        <div className="text-xs bg-indigo-950/60 border border-indigo-800 text-indigo-300 px-3 py-1.5 rounded-lg font-mono">
          Spec: agentskills.io v1.0
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-slate-300">
            Registered Skill Packages ({skills.length})
          </h2>
          {skills.map((s) => (
            <SkillCard
              key={s.name}
              skill={s}
              isSelected={selectedSkill?.name === s.name}
              onSelect={(skill) => setSelectedSkill(skill)}
            />
          ))}
        </div>

        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-slate-300">
            Skill Inspector & CI Validator
          </h2>
          {selectedSkill && (
            <SkillEditor
              skillName={selectedSkill.name}
              initialContent={skillContent}
            />
          )}
        </div>
      </div>
    </div>
  );
}
