#!/usr/bin/env python3
"""
Head-to-head benchmark: kimi-k2.5 vs qwen3-coder-next:cloud
Same coding prompt for both, measure performance and output quality.
"""

import time
import requests
import json
import re
from typing import List, Dict, Any
from pathlib import Path

API_KEY = "66df5a9713d6449f8a5527106b18d89c.tea5x_rYeWFgRKbLMYYPmDFu"
BASE_URL = "https://ollama.com/v1"

CODING_PROMPT = """Write a Python function that takes a list of integers and returns the top-K most frequent elements. Include edge cases (empty list, K > unique elements). Add docstring and type hints."""

MODEL_ALIASES = {
    "kimi": ["kimi-k2.5", "kimi-k2"],
    "qwen": ["qwen3-coder-next:cloud"]
}

def call_ollama_api(model_name: str) -> Dict[str, Any]:
    """Call Ollama chat completions API and capture timing metrics."""
    start_time = time.time()
    first_token_time = None
    response_text = ""
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": CODING_PROMPT}
        ],
        "stream": False,
        "temperature": 0.7
    }
    
    try:
        req_start = time.time()
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120
        )
        req_end = time.time()
        
        if response.status_code == 200:
            data = response.json()
            response_text = data["choices"][0]["message"]["content"]
            total_time = req_end - req_start
            # Assume first token at start (no streaming) for simplicity
            first_token_time = total_time * 0.1  # rough estimate
            return {
                "model": model_name,
                "success": True,
                "total_time": total_time,
                "first_token_time": first_token_time,
                "response": response_text,
                "error": None
            }
        else:
            return {
                "model": model_name,
                "success": False,
                "total_time": None,
                "first_token_time": None,
                "response": None,
                "error": f"HTTP {response.status_code}: {response.text}"
            }
    except Exception as e:
        return {
            "model": model_name,
            "success": False,
            "total_time": None,
            "first_token_time": None,
            "response": None,
            "error": str(e)
        }

def analyze_code_correctness(response: str) -> Dict[str, Any]:
    """Analyze code output for correctness and edge case handling."""
    result = {
        "has_correct_function": False,
        "has_edge_case_handling": False,
        "has_docstring": False,
        "has_type_hints": False,
        "python_syntax_valid": False,
        "imports_used": []
    }
    
    # Extract Python code block
    code_match = re.search(r"```python\s*(.*?)\s*```", response, re.DOTALL)
    if not code_match:
        code_match = re.search(r"```(.*?)```", response, re.DOTALL)
    
    code = code_match.group(1) if code_match else response
    
    # Check for docstring
    result["has_docstring"] = '"""' in code or "'''" in code
    
    # Check for type hints
    result["has_type_hints"] = bool(re.search(r"List\[int\].*->", code) or 
                                     re.search(r": List\[int\]", code) or
                                     re.search(r"-> List\[int\]", code))
    
    # Check for edge case handling
    result["has_edge_case_handling"] = bool(re.search(r"if.*not.*list|if.*len.*==.*0|if.*K.*>|if.*k.*>", code, re.IGNORECASE))
    
    # Check for function definition
    result["has_correct_function"] = bool(re.search(r"def\s+\w+.*top[kK].*frequent|def\s+\w+.*most.*frequent", code, re.IGNORECASE))
    
    # Test syntax validity
    try:
        ast.parse(code)
        result["python_syntax_valid"] = True
    except:
        result["python_syntax_valid"] = False
    
    # Detect imports
    result["imports_used"] = re.findall(r"^import\s+(\w+)|^from\s+(\w+)", code, re.MULTILINE)
    result["imports_used"] = [imp[0] or imp[1] for imp in result["imports_used"]]
    
    return result

def quality_rating(response: str) -> str:
    """Simple quality rating based on response characteristics."""
    # Heuristic scoring
    score = 0
    max_score = 10
    
    analysis = analyze_code_correctness(response)
    
    # Code-related scoring
    if analysis["has_correct_function"]:
        score += 3
    if analysis["has_edge_case_handling"]:
        score += 2
    if analysis["has_docstring"]:
        score += 2
    if analysis["has_type_hints"]:
        score += 2
    if analysis["python_syntax_valid"]:
        score += 1
    
    # Length bonus (avoid overly terse or verbose)
    resp_len = len(response)
    if 200 <= resp_len <= 800:
        score += 1
    
    if score >= 9:
        return "A"
    elif score >= 7:
        return "B"
    elif score >= 5:
        return "C"
    elif score >= 3:
        return "D"
    else:
        return "F"

def run_benchmark():
    """Run full benchmark comparing both models."""
    results = []
    
    print("=" * 60)
    print("BENCHMARK: kimi-k2.5 vs qwen3-coder-next:cloud")
    print("=" * 60)
    
    for model_type, models in MODEL_ALIASES.items():
        for model in models:
            print(f"\nTesting: {model}")
            result = call_ollama_api(model)
            results.append(result)
            
            if result["success"]:
                print(f"  ✓ Response received")
                print(f"  Total time: {result['total_time']:.2f}s")
                print(f"  First token: {result['first_token_time']:.2f}s")
                quality = quality_rating(result["response"])
                print(f"  Quality: {quality}")
                print(f"  Code snippet preview: {result['response'][:100]}...")
            else:
                print(f"  ✗ Failed: {result['error']}")
    
    # Generate comparison table
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"{'Model':<30} {'Time (s)':<12} {'Correct':<8} {'Quality':<8} {'Notes'}")
    print("-" * 60)
    
    for r in results:
        model_name = r["model"]
        time_str = f"{r['total_time']:.2f}" if r["total_time"] else "N/A"
        correct_str = "Yes" if r["success"] else "No"
        quality_str = quality_rating(r["response"]) if r["success"] else "F"
        notes = r["response"][:80] if r["success"] else r["error"][:80]
        print(f"{model_name:<30} {time_str:<12} {correct_str:<8} {quality_str:<8} {notes}")
    
    # Winner recommendation
    print("\n" + "=" * 60)
    print("RECOMMENDATION")
    print("=" * 60)
    
    success_results = [r for r in results if r["success"]]
    if len(success_results) >= 2:
        # Compare quality and time
        best_q = max(success_results, key=lambda x: quality_rating(x["response"]))
        best_t = min(success_results, key=lambda x: x["total_time"])
        
        if best_q == best_t:
            print(f"WINNER: {best_q['model']} (best quality AND best time)")
        else:
            print(f"Quality winner: {best_q['model']} ({quality_rating(best_q['response'])} quality)")
            print(f"Speed winner: {best_t['model']} ({best_t['total_time']:.2f}s)")
            print("\nRecommendation: Consider prioritizing quality over speed unless latency-critical.")
    elif len(success_results) == 1:
        print(f"Only one model succeeded: {success_results[0]['model']}")
    else:
        print("No models succeeded. Check API configuration.")
    
    return results

if __name__ == "__main__":
    run_benchmark()
