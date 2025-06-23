import os
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from .tools.tool_registry import ToolRegistry
except ImportError:
    from tools.tool_registry import ToolRegistry

# Determine log file path based on environment
SERVER_LOG_PATH = "/home/sysadmin/maubot/llm_usage.json"
LOCAL_LOG_PATH = os.path.expanduser("~/maubot/llm_usage.json")

LLM_LOG_FILE = SERVER_LOG_PATH if os.path.exists(os.path.dirname(SERVER_LOG_PATH)) else LOCAL_LOG_PATH

# Ensure the directory exists
os.makedirs(os.path.dirname(LLM_LOG_FILE), exist_ok=True)

# Instantiate the Tools class
tools_instance = ToolRegistry()

def log_llm_usage(user, request_event_id: str = None, response_event_id: str = None, 
                  emoji=None, tool_used=None, subtool_used=None, response_time=None,
                  benchmark_scores: Optional[Dict[str, Any]] = None):
    """Log LLM usage, user, tool calls, response time, and event IDs (if available) for quality assessment."""

    # Semi-anonymized username by hashing
    hashed_username = hashlib.sha256(user.encode()).hexdigest()[:8]  # Use first 8 chars for brevity

    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user": hashed_username,
        "tool_used": tool_used,
        "subtool_used": subtool_used,
        "response_time": response_time,
        "quality_assessment": None  # Placeholder for 👍/👎 feedback
    }

    # Add benchmark scores if available
    if benchmark_scores:
        entry["benchmark_scores"] = benchmark_scores
        entry["automated_quality"] = _calculate_automated_quality_score(benchmark_scores)

    if request_event_id:
        entry["request_event_id"] = request_event_id
    if response_event_id:
        entry["response_event_id"] = response_event_id
        # Quality assessment is only relevant if there's a response event to react to
    else:
        # If there's no response_event_id, quality assessment can't be linked
        entry["quality_assessment"] = "N/A"

    try:
        # Ensure the log file exists
        if not os.path.exists(LLM_LOG_FILE):
            with open(LLM_LOG_FILE, "w") as f:
                json.dump([], f)

        # Load existing log
        with open(LLM_LOG_FILE, "r") as f:
            logs = json.load(f)

        # Append new entry
        logs.append(entry)

        # Save updated log
        with open(LLM_LOG_FILE, "w") as f:
            json.dump(logs, f, indent=4)

    except Exception as e:
        print(f"Error writing LLM log: {e}")

def update_llm_log_quality(response_event_id: str, quality_assessment: str) -> bool:
    """Update the quality assessment for a given bot's response_event_id in the LLM log."""
    if not os.path.exists(LLM_LOG_FILE):
        print(f"Error: LLM log file not found at {LLM_LOG_FILE}")
        return False

    try:
        with open(LLM_LOG_FILE, "r") as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                print(f"Error: LLM log file {LLM_LOG_FILE} is not valid JSON or is empty.")
                return False
        
        updated = False
        for entry in logs:
            if entry.get("response_event_id") == response_event_id: # Match on response_event_id
                entry["quality_assessment"] = quality_assessment
                updated = True
                break
        
        if updated:
            with open(LLM_LOG_FILE, "w") as f:
                json.dump(logs, f, indent=4)
            print(f"Successfully updated quality assessment for response_event_id {response_event_id} to {quality_assessment}")
            return True
        else:
            print(f"Warning: response_event_id {response_event_id} not found in LLM log for quality update.")
            return False

    except Exception as e:
        print(f"Error updating LLM log quality: {e}")
        return False

def _calculate_automated_quality_score(benchmark_scores: Dict[str, Any]) -> float:
    """
    Calculate an overall automated quality score from benchmark results.
    
    Args:
        benchmark_scores: Dictionary containing benchmark evaluation results
        
    Returns:
        Overall quality score (0.0-1.0)
    """
    if not benchmark_scores:
        return 0.0
    
    # Extract scores from benchmark results
    scores = []
    weights = {
        'tool_accuracy': 0.4,
        'response_quality': 0.3,
        'hallucination': 0.3
    }
    
    total_score = 0.0
    total_weight = 0.0
    
    for metric_name, weight in weights.items():
        if metric_name in benchmark_scores:
            score_data = benchmark_scores[metric_name]
            if isinstance(score_data, dict) and 'score' in score_data:
                score = score_data['score']
                total_score += score * weight
                total_weight += weight
            elif isinstance(score_data, (int, float)):
                total_score += score_data * weight
                total_weight += weight
    
    return total_score / total_weight if total_weight > 0 else 0.0

def get_quality_analytics(days: int = 30) -> Dict[str, Any]:
    """
    Get quality analytics for the specified number of days.
    
    Args:
        days: Number of days to analyze
        
    Returns:
        Dictionary containing quality analytics
    """
    if not os.path.exists(LLM_LOG_FILE):
        return {"error": "Log file not found"}
    
    try:
        with open(LLM_LOG_FILE, "r") as f:
            logs = json.load(f)
        
        # Filter logs by date
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        recent_logs = []
        for log in logs:
            try:
                log_date = datetime.fromisoformat(log['timestamp'].replace('Z', '+00:00'))
                if log_date >= cutoff_date:
                    recent_logs.append(log)
            except (ValueError, KeyError):
                continue
        
        if not recent_logs:
            return {"error": "No recent logs found"}
        
        # Calculate analytics
        analytics = {
            "total_interactions": len(recent_logs),
            "period_days": days,
            "manual_feedback": {
                "positive": len([l for l in recent_logs if l.get("quality_assessment") == "👍"]),
                "negative": len([l for l in recent_logs if l.get("quality_assessment") == "👎"]),
                "total": len([l for l in recent_logs if l.get("quality_assessment") in ["👍", "👎"]])
            },
            "automated_scores": {
                "count": len([l for l in recent_logs if "automated_quality" in l]),
                "average": 0.0,
                "distribution": {}
            }
        }
        
        # Calculate automated score analytics
        automated_scores = [l["automated_quality"] for l in recent_logs if "automated_quality" in l]
        if automated_scores:
            analytics["automated_scores"]["average"] = sum(automated_scores) / len(automated_scores)
            
            # Score distribution
            score_ranges = [(0.0, 0.3), (0.3, 0.6), (0.6, 0.8), (0.8, 1.0)]
            for low, high in score_ranges:
                range_key = f"{low:.1f}-{high:.1f}"
                count = len([s for s in automated_scores if low <= s < high])
                analytics["automated_scores"]["distribution"][range_key] = count
        
        # Calculate manual feedback rate
        if analytics["total_interactions"] > 0:
            feedback_rate = analytics["manual_feedback"]["total"] / analytics["total_interactions"]
            analytics["manual_feedback"]["feedback_rate"] = feedback_rate
        
        # Calculate positive feedback rate
        if analytics["manual_feedback"]["total"] > 0:
            positive_rate = analytics["manual_feedback"]["positive"] / analytics["manual_feedback"]["total"]
            analytics["manual_feedback"]["positive_rate"] = positive_rate
        
        return analytics
        
    except Exception as e:
        return {"error": f"Error analyzing logs: {str(e)}"}

def get_tool_usage_analytics(days: int = 30) -> Dict[str, Any]:
    """
    Get tool usage analytics for the specified number of days.
    
    Args:
        days: Number of days to analyze
        
    Returns:
        Dictionary containing tool usage analytics
    """
    if not os.path.exists(LLM_LOG_FILE):
        return {"error": "Log file not found"}
    
    try:
        with open(LLM_LOG_FILE, "r") as f:
            logs = json.load(f)
        
        # Filter logs by date and tool usage
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        tool_usage = {}
        total_with_tools = 0
        
        for log in logs:
            try:
                log_date = datetime.fromisoformat(log['timestamp'].replace('Z', '+00:00'))
                if log_date >= cutoff_date and log.get('tool_used'):
                    tool_name = log['tool_used']
                    if tool_name not in tool_usage:
                        tool_usage[tool_name] = {
                            "count": 0,
                            "success_rate": 0.0,
                            "avg_response_time": 0.0,
                            "response_times": []
                        }
                    
                    tool_usage[tool_name]["count"] += 1
                    total_with_tools += 1
                    
                    # Track response times
                    if log.get('response_time'):
                        tool_usage[tool_name]["response_times"].append(log['response_time'])
                    
            except (ValueError, KeyError):
                continue
        
        # Calculate averages and rates
        for tool_name, data in tool_usage.items():
            if data["response_times"]:
                data["avg_response_time"] = sum(data["response_times"]) / len(data["response_times"])
                del data["response_times"]  # Remove raw data from output
            
            # Calculate usage percentage
            data["usage_percentage"] = (data["count"] / total_with_tools) * 100 if total_with_tools > 0 else 0
        
        # Sort by usage count
        sorted_tools = dict(sorted(tool_usage.items(), key=lambda x: x[1]["count"], reverse=True))
        
        return {
            "period_days": days,
            "total_tool_interactions": total_with_tools,
            "unique_tools_used": len(tool_usage),
            "tool_usage": sorted_tools
        }
        
    except Exception as e:
        return {"error": f"Error analyzing tool usage: {str(e)}"}

# Convenience function for benchmark integration
def log_benchmark_result(user: str, input_text: str, response: str, 
                        benchmark_scores: Dict[str, Any], response_time: float = None,
                        tool_used: str = None):
    """
    Log a benchmark evaluation result.
    
    Args:
        user: User identifier
        input_text: Input query
        response: Response text
        benchmark_scores: Benchmark evaluation scores
        response_time: Response time in seconds
        tool_used: Tool that was used (if any)
    """
    log_llm_usage(
        user=user,
        tool_used=tool_used,
        response_time=response_time,
        benchmark_scores=benchmark_scores
    )
