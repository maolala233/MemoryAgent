"use client";

import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";

const FAQS = [
  {
    q: "How does the memory vault work?",
    a: "The vault is a directory of Markdown files with YAML frontmatter. Each file is indexed into SQLite with FTS5 for keyword search and embedded for semantic search. Files are scanned on startup and can be rescanned any time.",
  },
  {
    q: "What retrieval strategies are available?",
    a: "Three: keyword (BM25 via FTS5), semantic (cosine similarity over embeddings), and hybrid (weighted merge of both). Configure weights in retrieval.yaml.",
  },
  {
    q: "How do I add a new agent?",
    a: "Edit backend/config/agents.yaml. Each agent defines a name, role, system prompt, LLM provider, memory strategy, and tools. Restart the backend to pick up changes.",
  },
  {
    q: "What LLM providers are supported?",
    a: "Three out of the box: Mock (offline, deterministic), Ollama (local), and OpenAI (cloud). Add API keys in .env or via environment variables.",
  },
  {
    q: "Can I import documents?",
    a: "Yes. The Import Document page accepts PDF, DOCX, MD, and TXT files. They are parsed into chunks, converted to memory format with auto-extracted frontmatter, and saved to the vault.",
  },
];

export default function SupportPage() {
  return (
    <AppShell title="Support" subtitle="Help & documentation">
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="max-w-3xl mx-auto px-panel-padding py-8 space-y-6">
          <div className="bg-gradient-to-br from-primary to-primary-container text-on-primary rounded-xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <Icon name="help" filled className="text-[28px]" />
              <h2 className="text-headline-md font-headline-md font-bold">
                How can we help?
              </h2>
            </div>
            <p className="text-body-md opacity-90">
              Codex Memory is a self-hosted memory platform for AI agents. Browse
              the FAQs below or check the design document for full architecture
              details.
            </p>
          </div>

          <div className="space-y-3">
            <h3 className="text-body-lg font-bold text-on-surface">
              Frequently Asked Questions
            </h3>
            {FAQS.map((faq, i) => (
              <details
                key={i}
                className="bg-surface border border-border rounded-xl p-4 group"
              >
                <summary className="cursor-pointer flex items-center justify-between">
                  <span className="text-body-md font-bold text-on-surface">
                    {faq.q}
                  </span>
                  <Icon
                    name="expand_more"
                    className="text-on-surface-variant group-open:rotate-180 transition-transform"
                  />
                </summary>
                <p className="text-body-md text-on-surface-variant mt-3 leading-relaxed">
                  {faq.a}
                </p>
              </details>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Link
              href="/"
              className="bg-surface border border-border rounded-xl p-5 hover:border-primary transition-colors flex items-center gap-3"
            >
              <Icon
                name="dashboard"
                filled
                className="text-primary text-[24px]"
              />
              <div>
                <p className="text-body-md font-bold text-on-surface">
                  Go to Dashboard
                </p>
                <p className="text-body-sm text-on-surface-variant">
                  View your vault statistics
                </p>
              </div>
            </Link>
            <Link
              href="/settings"
              className="bg-surface border border-border rounded-xl p-5 hover:border-primary transition-colors flex items-center gap-3"
            >
              <Icon
                name="settings"
                filled
                className="text-primary text-[24px]"
              />
              <div>
                <p className="text-body-md font-bold text-on-surface">
                  System Settings
                </p>
                <p className="text-body-sm text-on-surface-variant">
                  Check configuration & providers
                </p>
              </div>
            </Link>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
