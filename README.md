# ⚖️ LegalTech AI Engine — DoraHacks 2025

**Experimental Submission for the DoraHacks Legal Hack 2025**

 
**Goal:** Ship a working LegalTech MVP integrating **Story**, **ICP**, and **Constellation**.

---

## 🚀 Overview

The LegalTech AI Engine is a **FastAPI-based orchestration layer** that transforms legal workflows into verifiable, AI-generated digital assets.  
It combines **AI reasoning**, **document automation**, and **blockchain-anchored proofs** to bring **transparency** and **ownership** to legal intelligence.

---

## 🌐 Hackathon Scope

| Track      | Focus                                     |
|-----------|-------------------------------------------|
| AI × Law   | Automate drafting, review, and analysis  |
| Story Protocol | Register authored outputs as verifiable IP |
| ICP        | Immutable metadata ledger                 |
| Constellation DAG | Record reasoning and audit trail     |

---

## 🧩 System Overview

User → Frontend UI
↓
Django Backend
↓
FastAPI AI Engine
↓
┌──────────────┬──────────────┬──────────────┐
│ Story Protocol │ ICP Ledger │ Constellation DAG │
└──────────────┴──────────────┴──────────────┘

yaml
Copy code

Each document passes through AI agents for **drafting**, **review**, and **summarization**.  
All results are **registered on-chain** for **proof-of-authorship** and **reasoning traceability**.

---

## 🏗️ Directory Structure

.
├── main.py
├── utils.py
├── requirements.txt
│
├── services/
│ ├── router.py
│ ├── lens.py
│ ├── draft.py
│ ├── review.py
│ ├── docs.py
│ └── integration/
│ ├── story.py
│ ├── icp.py
│ └── constellation.py
└── README.md

yaml
Copy code

---

## 🧠 Core Agents

| Agent | Function | Blockchain Output |
|-------|---------|------------------|
| Lens  | Summarize & interpret documents | DAG reasoning trace |
| Draft | Generate legal drafts/contracts   | Story IP record |
| Review | Evaluate & annotate legal text   | ICP proof metadata |
| Docs  | Embed & classify legal files      | Cross-layer registry entry |

---

## 🔗 Blockchain Integration

| Layer          | Purpose                        | Example |
|----------------|--------------------------------|---------|
| Story Protocol | IP registration for AI-generated outputs | `story.register_asset(title, hash)` |
| ICP            | Store immutable metadata       | `icp.store_metadata({...})` |
| Constellation  | Record reasoning audit trail   | `dag.submit_proof(trace)` |

---

## ⚙️ Setup & Run

### 1️⃣ Clone the Repo
```bash
git clone https://github.com/HakiChain-Main/hakichain-dorahacks-legaltech.git
cd hakichain-dorahacks-legaltech
2️⃣ Create .env
bash
Copy code
STORY_API_KEY=...
ICP_AGENT_KEY=...
CONSTELLATION_NODE_URL=...
DJANGO_API_URL=http://localhost:8000
3️⃣ Install Dependencies
bash
Copy code
pip install -r requirements.txt
4️⃣ Run FastAPI
bash
Copy code
uvicorn main:app --reload --port 8001
🧩 Integration with Django
Django handles users, cases, and documents.

It calls FastAPI endpoints:

/draft

/review

/summarize

/proof/register

FastAPI performs AI processing and blockchain registration.

Django updates its database with Story / ICP / DAG identifiers.