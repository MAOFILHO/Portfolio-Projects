"""
SmartClaims - Agent Orchestration Service
==========================================
v2.x - Manual function call handling for custom tools
Manages Foundry agent lifecycle, file uploads, and tool routing.
"""

import os
import json
import csv
from pathlib import Path
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


# --------------------------------------------------
# Function schemas for custom tools
# --------------------------------------------------
CUSTOM_FUNCTION_SCHEMAS = [
    {
        "type": "function",
        "name": "get_claim_status",
        "description": "Look up claim status from uploaded CSV data by claim ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "claim_id": {
                    "type": "string",
                    "description": "Claim ID in CLM-XXXX format"
                }
            },
            "required": ["claim_id"]
        }
    },
    {
        "type": "function",
        "name": "calculate_fraud_risk",
        "description": "Calculate fraud risk score for a new claim.",
        "parameters": {
            "type": "object",
            "properties": {
                "incident_type": {
                    "type": "string",
                    "enum": [
                        "Auto Collision", "Property Damage",
                        "Medical Claim", "Theft",
                        "Natural Disaster", "Liability", "Fire Damage"
                    ]
                },
                "claim_amount": {"type": "number"},
                "region": {
                    "type": "string",
                    "enum": ["North", "South", "East", "West", "Central"]
                },
                "days_since_policy_start": {"type": "integer"}
            },
            "required": [
                "incident_type", "claim_amount",
                "region", "days_since_policy_start"
            ]
        }
    },
]


class AgentService:
    """Manages SmartClaims agent and resources."""

    def __init__(self):
        self.endpoint = os.environ.get("PROJECT_ENDPOINT", "")
        self.model = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")

        # Lazy-load clients to prevent startup crash
        self._project_client = None
        self._openai_client = None

        # State
        self.vector_store_id = None
        self.csv_file_id = None
        self.agent = None
        self.claims_data = []
        self.uploaded_files_info = []
        self.all_tools = []

        # Function registry for custom tools
        self.function_map = {
            "get_claim_status": self._get_claim_status,
            "calculate_fraud_risk": self._calculate_fraud_risk,
        }

    # --- Lazy Client Properties ---
    @property
    def project_client(self):
        if self._project_client is None:
            self._project_client = AIProjectClient(
                endpoint=self.endpoint,
                credential=DefaultAzureCredential(),
            )
        return self._project_client

    @property
    def openai_client(self):
        if self._openai_client is None:
            self._openai_client = self.project_client.get_openai_client()
        return self._openai_client

    # --- File Upload -----------------------------------
    def upload_files(self, file_paths: list[dict]) -> dict:
        """Upload files for the agent."""
        csv_ids = []
        results = []

        if not self.vector_store_id:
            vs = self.openai_client.vector_stores.create(
                name="SmartClaims-UserDocs"
            )
            self.vector_store_id = vs.id

        for item in file_paths:
            fpath = item["path"]
            fname = item["filename"]
            ftype = item["type"]

            if ftype == "csv":
                f = self.openai_client.files.create(
                    purpose="assistants",
                    file=open(fpath, "rb"),
                )
                csv_ids.append(f.id)
                self.csv_file_id = f.id

                with open(fpath, "r", encoding="utf-8") as csvf:
                    self.claims_data = list(csv.DictReader(csvf))

                results.append({"file": fname, "type": "csv", "id": f.id,
                                "records": len(self.claims_data)})

            elif ftype == "doc":
                f = self.openai_client.vector_stores.files.upload_and_poll(
                    vector_store_id=self.vector_store_id,
                    file=open(fpath, "rb"),
                )
                results.append({"file": fname, "type": "doc", "id": f.id})

        self._create_agent(csv_ids)

        self.uploaded_files_info = results
        return {
            "status": "ok",
            "files": results,
        }

    # --- Agent Creation --------------------------------
    def _create_agent(self, csv_file_ids: list[str] = None):
        """Create the unified agent with all available tools as plain dicts."""

        tools = []

        # In v2.x, native tools are plain dicts — NO .definitions attribute
        if csv_file_ids:
            tools.append({
                "type": "code_interpreter",
                "container": {
                    "type": "auto",
                    "file_ids": csv_file_ids,
                }
            })

        if self.vector_store_id:
            tools.append({
                "type": "file_search",
                "vector_store_ids": [self.vector_store_id],
            })

        # Add custom function schemas
        tools.extend(CUSTOM_FUNCTION_SCHEMAS)

        self.all_tools = tools

        try:
            self.project_client.agents.delete_agent("smartclaims-webapp")
        except Exception:
            pass

        self.agent = self.project_client.agents.create_version(
            agent_name="smartclaims-webapp",
            definition=PromptAgentDefinition(
                model=self.model,
                instructions=(
                    "You are SmartClaims, an AI insurance agent. "
                    "Tools: FILE SEARCH for policy docs, "
                    "CODE INTERPRETER for CSV analytics, "
                    "FUNCTIONS: get_claim_status(claim_id), "
                    "calculate_fraud_risk(incident_type, claim_amount, "
                    "region, days_since_policy_start). "
                    "Always pick the right tool. Be precise."
                ),
                tools=tools,
            ),
        )

    # --- Analytics Chat (inlines CSV data directly) ----
    def analytics_chat(self, message: str) -> dict:
        """
        For analytics queries: pre-aggregate CSV data in Python, get a
        text response from the model, and also return structured chart_data
        so the frontend can render Chart.js visualizations directly.
        Returns a dict: {"response": str, "chart": {...} or None}
        """
        if not self.agent:
            return {"response": "Please upload files first before chatting.", "chart": None}

        if not self.claims_data:
            return {"response": "No CSV data found. Please upload a claims CSV file first.", "chart": None}

        rows = self.claims_data
        total = len(rows)

        # --- Pre-aggregate in Python ---

        status_counts: dict = {}
        for r in rows:
            s = r.get("status", "Unknown")
            status_counts[s] = status_counts.get(s, 0) + 1

        incident_amounts: dict = {}
        incident_counts: dict = {}
        for r in rows:
            it = r.get("incident_type", "Unknown")
            try:
                amt = float(r.get("claim_amount", 0))
            except (ValueError, TypeError):
                amt = 0.0
            incident_amounts[it] = incident_amounts.get(it, 0.0) + amt
            incident_counts[it] = incident_counts.get(it, 0) + 1
        incident_avg = {
            k: round(incident_amounts[k] / incident_counts[k], 2)
            for k in incident_counts
        }

        region_counts: dict = {}
        region_fraud: dict = {}
        for r in rows:
            reg = r.get("region", "Unknown")
            region_counts[reg] = region_counts.get(reg, 0) + 1
            try:
                ff = str(r.get("fraud_flag", "0")).strip().lower()
                is_fraud = ff in ("1", "true", "yes")
            except Exception:
                is_fraud = False
            if is_fraud:
                region_fraud[reg] = region_fraud.get(reg, 0) + 1
        region_fraud_rate = {
            k: round(region_fraud.get(k, 0) / region_counts[k] * 100, 1)
            for k in region_counts
        }

        policy_counts: dict = {}
        for r in rows:
            pt = r.get("policy_type", "Unknown")
            policy_counts[pt] = policy_counts.get(pt, 0) + 1

        fraud_total = sum(region_fraud.values())
        overall_fraud_rate = round(fraud_total / total * 100, 1) if total else 0

        all_amounts = []
        for r in rows:
            try:
                all_amounts.append(float(r.get("claim_amount", 0)))
            except (ValueError, TypeError):
                pass
        total_amount = round(sum(all_amounts), 2)
        avg_amount = round(total_amount / len(all_amounts), 2) if all_amounts else 0

        # --- Decide which chart to render based on the question ---
        msg_lower = message.lower()
        chart = None

        COLORS = [
            "#2E86C1","#E74C3C","#27AE60","#F39C12","#8E44AD",
            "#16A085","#D35400","#2C3E50","#C0392B","#1ABC9C"
        ]

        # --- Detect chart type override (bar/pie explicitly requested) ---
        force_bar = any(w in msg_lower for w in ["bar", "bar chart", "bar graph", "column"])
        force_pie = any(w in msg_lower for w in ["pie", "pie chart", "donut"])

        # --- Detect topic ---
        if any(w in msg_lower for w in ["fraud rate", "fraud by region", "fraud region", "fraud pie", "fraud"]):
            labels = list(region_fraud_rate.keys())
            values = [region_fraud_rate[k] for k in labels]
            chart_type = "bar" if force_bar else "pie"
            chart = {
                "type": chart_type,
                "title": "Fraud Rate by Region (%)",
                "labels": labels,
                "data": values,
                "colors": COLORS[:len(labels)],
            }
        elif any(w in msg_lower for w in ["region", "claims by region", "region breakdown"]):
            labels = list(region_counts.keys())
            values = [region_counts[k] for k in labels]
            chart_type = "pie" if force_pie else "bar"
            chart = {
                "type": chart_type,
                "title": "Claims by Region",
                "labels": labels,
                "data": values,
                "colors": COLORS[:len(labels)],
            }
        elif any(w in msg_lower for w in ["status", "status breakdown", "claim status"]):
            labels = list(status_counts.keys())
            values = [status_counts[k] for k in labels]
            chart_type = "bar" if force_bar else "pie"
            chart = {
                "type": chart_type,
                "title": "Claims by Status",
                "labels": labels,
                "data": values,
                "colors": COLORS[:len(labels)],
            }
        elif any(w in msg_lower for w in ["incident", "incident type", "coverage type"]):
            labels = list(incident_counts.keys())
            values = [incident_counts[k] for k in labels]
            chart_type = "pie" if force_pie else "bar"
            chart = {
                "type": chart_type,
                "title": "Claims by Incident Type",
                "labels": labels,
                "data": values,
                "colors": COLORS[:len(labels)],
            }
        elif any(w in msg_lower for w in ["avg", "average", "amount", "claim amount"]):
            labels = list(incident_avg.keys())
            values = [incident_avg[k] for k in labels]
            chart_type = "pie" if force_pie else "bar"
            chart = {
                "type": chart_type,
                "title": "Average Claim Amount by Incident Type ($)",
                "labels": labels,
                "data": values,
                "colors": COLORS[:len(labels)],
            }
        elif any(w in msg_lower for w in ["policy type", "policy breakdown", "policy"]):
            labels = list(policy_counts.keys())
            values = [policy_counts[k] for k in labels]
            chart_type = "bar" if force_bar else "pie"
            chart = {
                "type": chart_type,
                "title": "Claims by Policy Type",
                "labels": labels,
                "data": values,
                "colors": COLORS[:len(labels)],
            }
        elif any(w in msg_lower for w in ["executive", "summary", "overview"]):
            labels = list(status_counts.keys())
            values = [status_counts[k] for k in labels]
            chart_type = "bar" if force_bar else "pie"
            chart = {
                "type": chart_type,
                "title": "Claims Status Overview",
                "labels": labels,
                "data": values,
                "colors": COLORS[:len(labels)],
            }
        elif force_bar or force_pie:
            # User asked for a chart but no specific topic — default to status
            labels = list(status_counts.keys())
            values = [status_counts[k] for k in labels]
            chart = {
                "type": "bar" if force_bar else "pie",
                "title": "Claims Status Overview",
                "labels": labels,
                "data": values,
                "colors": COLORS[:len(labels)],
            }

        # --- Save chart as PNG to outputs/ folder using matplotlib ---
        if chart:
            self._save_chart_png(chart)

        # --- Get text response from model ---
        summary = f"""CLAIMS DATA SUMMARY ({total} total records)

STATUS BREAKDOWN:
{chr(10).join(f"  {k}: {v} ({round(v/total*100,1)}%)" for k, v in sorted(status_counts.items(), key=lambda x: -x[1]))}

INCIDENT TYPE (count | avg claim amount):
{chr(10).join(f"  {k}: {incident_counts[k]} claims | avg ${incident_avg[k]:,.2f}" for k in sorted(incident_counts, key=lambda x: -incident_counts[x]))}

REGION BREAKDOWN (count | fraud rate):
{chr(10).join(f"  {k}: {region_counts[k]} claims | fraud rate {region_fraud_rate[k]}%" for k in sorted(region_counts, key=lambda x: -region_counts[x]))}

POLICY TYPE BREAKDOWN:
{chr(10).join(f"  {k}: {v}" for k, v in sorted(policy_counts.items(), key=lambda x: -x[1]))}

FINANCIAL SUMMARY:
  Total claim amount: ${total_amount:,.2f}
  Average claim amount: ${avg_amount:,.2f}
  Overall fraud rate: {overall_fraud_rate}% ({fraud_total} flagged)
"""
        augmented_message = (
            f"{message}\n\nUse this pre-computed summary to answer clearly with numbers and percentages.\n\n{summary}"
        )
        text_response = self.chat(augmented_message)
        return {"response": text_response, "chart": chart}

    # --- Chat with Function Call Loop ------------------
    def chat(self, message: str) -> str:
        """Send message to agent with v2.x function call handling."""
        if not self.agent:
            return "Please upload files first before chatting."

        # Fresh conversation per message — avoids call_id conflicts
        conv = self.openai_client.conversations.create()
        conversation_id = conv.id

        try:
            # First call — use conversation, no tools=, no previous_response_id
            response = self.openai_client.responses.create(
                conversation=conversation_id,
                extra_body={"agent_reference": {
                    "name": self.agent.name,
                    "version": self.agent.version,
                    "type": "agent_reference",
                }},
                input=message,
            )

            # Function call loop
            max_rounds = 10
            for _ in range(max_rounds):
                function_calls = [
                    item for item in response.output
                    if item.type == "function_call"
                ]

                if not function_calls:
                    return response.output_text

                tool_outputs = []
                for fc in function_calls:
                    func = self.function_map.get(fc.name)
                    if func:
                        try:
                            args = json.loads(fc.arguments)
                            result = func(**args)
                        except Exception as e:
                            result = json.dumps({"error": str(e)})
                    else:
                        result = json.dumps({"error": f"Unknown: {fc.name}"})

                    tool_outputs.append({
                        "type": "function_call_output",
                        "call_id": fc.call_id,
                        "output": result,
                    })

                # Follow-up call — use previous_response_id, NOT conversation
                response = self.openai_client.responses.create(
                    extra_body={"agent_reference": {
                        "name": self.agent.name,
                        "version": self.agent.version,
                        "type": "agent_reference",
                    }},
                    input=tool_outputs,
                    previous_response_id=response.id,
                )

            return response.output_text

        except Exception as e:
            return f"Error: {str(e)}"

    # --- Function Tool Implementations -----------------
    def _get_claim_status(self, claim_id: str) -> str:
        """Look up claim status from uploaded CSV data."""
        for row in self.claims_data:
            if row.get("claim_id") == claim_id:
                return json.dumps({
                    "claim_id": row.get("claim_id"),
                    "status": row.get("status"),
                    "incident_type": row.get("incident_type"),
                    "claim_amount": row.get("claim_amount"),
                    "approved_amount": row.get("approved_amount"),
                    "fraud_score": row.get("fraud_score"),
                    "region": row.get("region"),
                    "processing_days": row.get("processing_days"),
                }, indent=2)
        return json.dumps({"error": f"Claim '{claim_id}' not found"})

    def _calculate_fraud_risk(
        self, incident_type: str, claim_amount: float,
        region: str, days_since_policy_start: int,
    ) -> str:
        """Calculate fraud risk for a new claim."""
        base = {"Auto Collision": 0.15, "Property Damage": 0.10,
                "Medical Claim": 0.12, "Theft": 0.25,
                "Natural Disaster": 0.05, "Liability": 0.18,
                "Fire Damage": 0.20}.get(incident_type, 0.15)
        if claim_amount > 100000: base += 0.15
        elif claim_amount > 50000: base += 0.08
        base += {"North": 0, "South": 0.03, "East": -0.02,
                 "West": 0.05, "Central": 0.01}.get(region, 0)
        if days_since_policy_start < 90: base += 0.10
        score = max(0, min(1, round(base, 2)))
        level = "HIGH" if score >= 0.5 else "MEDIUM" if score >= 0.3 else "LOW"
        return json.dumps({"score": score, "level": level})

    # --- Save Chart PNG to outputs/ folder ------------
    def _save_chart_png(self, chart: dict):
        """Save chart as PNG to outputs/ folder using matplotlib."""
        try:
            import matplotlib
            matplotlib.use("Agg")  # non-interactive backend, safe for server
            import matplotlib.pyplot as plt
            import re
            from pathlib import Path

            outputs_dir = Path(__file__).resolve().parent.parent / "outputs"
            outputs_dir.mkdir(exist_ok=True)

            # Sanitize title for filename
            safe_title = re.sub(r"[^\w\s-]", "", chart["title"]).strip()
            safe_title = re.sub(r"\s+", "_", safe_title).lower()
            filepath = outputs_dir / f"{safe_title}.png"

            labels = chart["labels"]
            data = chart["data"]
            colors = chart["colors"]

            fig, ax = plt.subplots(figsize=(8, 5))
            fig.patch.set_facecolor("white")

            if chart["type"] == "pie":
                wedges, texts, autotexts = ax.pie(
                    data, labels=labels, colors=colors,
                    autopct="%1.1f%%", startangle=140,
                    textprops={"fontsize": 11}
                )
                for at in autotexts:
                    at.set_fontsize(10)
            else:
                bars = ax.bar(labels, data, color=colors, edgecolor="white", linewidth=0.8)
                ax.set_ylabel("Value", fontsize=11)
                ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=10)
                ax.yaxis.grid(True, linestyle="--", alpha=0.5)
                ax.set_axisbelow(True)
                for bar in bars:
                    h = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width() / 2, h * 1.01,
                            f"{h:,.1f}", ha="center", va="bottom", fontsize=9)

            ax.set_title(chart["title"], fontsize=13, fontweight="bold", pad=14)
            plt.tight_layout()
            plt.savefig(str(filepath), dpi=150, bbox_inches="tight")
            plt.close(fig)

        except Exception as e:
            # Non-fatal — chart still renders in browser via Chart.js
            print(f"[warn] Could not save chart PNG: {e}")

    # --- Cleanup ---------------------------------------
    def cleanup(self):
        """Delete all agent resources."""
        try:
            self.project_client.agents.delete_agent("smartclaims-webapp")
        except Exception:
            pass
        if self.vector_store_id:
            try:
                self.openai_client.vector_stores.delete(self.vector_store_id)
            except Exception:
                pass