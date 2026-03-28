"""
Tool definitions and handlers for DeliverAssist.
These are called by Gemini via function calling during live sessions.
"""

from datetime import date
import json

# ── Tool Declarations (sent to Gemini in session config) ─────────────────────

TOOL_DECLARATIONS = [
    {
        "name": "calculate_pay_compliance",
        "description": (
            "Calculate whether a NYC delivery worker's pay meets the legal minimum. "
            "Call this whenever a worker mentions their pay and hours, or when analyzing a pay stub. "
            "Returns whether they are compliant, the shortfall amount, and next steps."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "total_pay_before_tips": {
                    "type": "number",
                    "description": "Total pay received EXCLUDING tips, in USD"
                },
                "total_hours": {
                    "type": "number",
                    "description": "Total hours worked INCLUDING waiting/on-call time"
                },
                "tips": {
                    "type": "number",
                    "description": "Total tips received in USD. Default 0 if unknown."
                },
                "app_name": {
                    "type": "string",
                    "description": "Name of delivery app (DoorDash, UberEats, Grubhub, Relay, etc.)"
                },
                "pay_period_days": {
                    "type": "number",
                    "description": "Number of days in the pay period. Default 7."
                }
            },
            "required": ["total_pay_before_tips", "total_hours"]
        }
    },
    {
        "name": "estimate_weekly_earnings",
        "description": (
            "Estimate a delivery worker's expected weekly earnings based on hours worked. "
            "Call this when a worker asks 'how much should I be making?' or similar."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "hours_per_week": {
                    "type": "number",
                    "description": "Hours worked per week including waiting time"
                },
                "include_typical_tips": {
                    "type": "boolean",
                    "description": "Whether to include average tip estimates. Default true."
                }
            },
            "required": ["hours_per_week"]
        }
    }
]


# ── Tool Handlers ────────────────────────────────────────────────────────────

def get_minimum_rate() -> float:
    """Get the current NYC minimum pay rate for delivery workers."""
    today = date.today()
    if today >= date(2026, 4, 1):
        return 22.13
    return 21.44


def handle_calculate_pay_compliance(params: dict) -> dict:
    """Check if a worker's pay meets NYC minimum requirements."""
    pay = params["total_pay_before_tips"]
    hours = params["total_hours"]
    tips = params.get("tips", 0)
    app_name = params.get("app_name", "Unknown")
    period_days = params.get("pay_period_days", 7)

    if hours <= 0:
        return {"error": "Hours must be greater than zero."}

    min_rate = get_minimum_rate()
    effective_rate = round(pay / hours, 2)
    is_compliant = effective_rate >= min_rate
    shortfall_per_hour = round(max(0, min_rate - effective_rate), 2)
    total_owed = round(shortfall_per_hour * hours, 2)
    total_with_tips = round((pay + tips) / hours, 2)

    result = {
        "effective_hourly_rate": effective_rate,
        "minimum_required_rate": min_rate,
        "is_compliant": is_compliant,
        "shortfall_per_hour": shortfall_per_hour,
        "total_underpayment": total_owed,
        "tips_per_hour": round(tips / hours, 2) if tips else 0,
        "total_with_tips_per_hour": total_with_tips,
        "app_name": app_name,
        "hours_worked": hours,
        "pay_period_days": period_days,
    }

    if is_compliant:
        result["summary"] = (
            f"Good news — your effective rate of ${effective_rate}/hr meets the "
            f"NYC minimum of ${min_rate}/hr."
        )
    else:
        result["summary"] = (
            f"You are being UNDERPAID. Your effective rate is ${effective_rate}/hr, "
            f"but the NYC minimum is ${min_rate}/hr. "
            f"You are owed approximately ${total_owed} for this period "
            f"(${shortfall_per_hour}/hr x {hours} hours). "
            f"File a complaint at nyc.gov/DeliveryApps or call 311."
        )

    return result


def handle_estimate_weekly_earnings(params: dict) -> dict:
    """Estimate expected weekly earnings at minimum rate."""
    hours = params["hours_per_week"]
    include_tips = params.get("include_typical_tips", True)

    min_rate = get_minimum_rate()
    base_earnings = round(min_rate * hours, 2)

    # Average tip rate from DCWP Q1 2024 data: roughly $3-5/hr
    avg_tip_rate = 4.00
    estimated_tips = round(avg_tip_rate * hours, 2) if include_tips else 0

    return {
        "hours_per_week": hours,
        "minimum_rate": min_rate,
        "minimum_base_earnings": base_earnings,
        "estimated_tips": estimated_tips,
        "estimated_total": round(base_earnings + estimated_tips, 2),
        "summary": (
            f"Working {hours} hours/week, you should earn AT LEAST "
            f"${base_earnings} in base pay (at ${min_rate}/hr). "
            f"{'With average tips of about $' + str(estimated_tips) + ', your total should be around $' + str(round(base_earnings + estimated_tips, 2)) + '/week.' if include_tips else ''}"
        )
    }


# ── Dispatcher ───────────────────────────────────────────────────────────────

TOOL_HANDLERS = {
    "calculate_pay_compliance": handle_calculate_pay_compliance,
    "estimate_weekly_earnings": handle_estimate_weekly_earnings,
}


def handle_tool_call(function_name: str, function_args: dict) -> str:
    """Dispatch a tool call and return JSON result string."""
    handler = TOOL_HANDLERS.get(function_name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {function_name}"})

    try:
        result = handler(function_args)
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})
