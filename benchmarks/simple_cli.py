#!/usr/bin/env python3
"""
Simple RooLLM Benchmark CLI

A simpler command-line interface that avoids asyncio complications.
For full benchmarking, use the REPL interface: python repl.py
"""

import argparse
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def show_analytics(days=30):
    """Show quality analytics (synchronous)."""
    try:
        from stats import get_quality_analytics, get_tool_usage_analytics
        
        print(f"📈 Quality Analytics (Last {days} days):")
        
        # Get quality analytics
        quality_data = get_quality_analytics(days)
        
        if "error" in quality_data:
            print(f"❌ Error: {quality_data['error']}")
            return 1
        
        # Display quality analytics
        print(f"Total interactions: {quality_data.get('total_interactions', 0)}")
        
        manual_feedback = quality_data.get("manual_feedback", {})
        print(f"Manual feedback: {manual_feedback.get('positive', 0)}👍 / "
              f"{manual_feedback.get('negative', 0)}👎 ({manual_feedback.get('feedback_rate', 0.0):.1%} response rate)")
        
        automated_scores = quality_data.get("automated_scores", {})
        if automated_scores.get("count", 0) > 0:
            print(f"Automated evaluations: {automated_scores.get('count', 0)}")
            print(f"Average quality score: {automated_scores.get('average', 0.0):.2f}")
            
            # Show distribution
            distribution = automated_scores.get("distribution", {})
            if distribution:
                print(f"Score distribution:")
                for range_key, count in distribution.items():
                    print(f"  {range_key}: {count} responses")
        
        # Get tool usage analytics
        tool_data = get_tool_usage_analytics(days)
        
        if "error" not in tool_data:
            print(f"\n🛠️ Tool Usage Analytics:")
            print(f"Total tool interactions: {tool_data.get('total_tool_interactions', 0)}")
            print(f"Unique tools used: {tool_data.get('unique_tools_used', 0)}")
            
            # Show top tools
            tool_usage = tool_data.get("tool_usage", {})
            if tool_usage:
                print(f"Top 5 tools:")
                for i, (tool_name, stats) in enumerate(list(tool_usage.items())[:5]):
                    print(f"  {i+1}. {tool_name}: {stats.get('count', 0)} uses "
                          f"({stats.get('usage_percentage', 0.0):.1f}%)")
        
        return 0
        
    except ImportError:
        print(f"❌ Error: Analytics not available")
        return 1
    except Exception as e:
        print(f"❌ Error getting analytics: {str(e)}")
        return 1

def run_benchmark_info(dataset="all"):
    """Show info about running benchmarks."""
    print(f"🧪 Benchmark Information")
    print(f"Dataset requested: {dataset}")
    print()
    print("📋 Available Test Cases:")
    
    datasets_dir = Path(__file__).parent / "datasets"
    if datasets_dir.exists():
        for dataset_file in datasets_dir.glob("*.json"):
            try:
                import json
                with open(dataset_file, 'r') as f:
                    data = json.load(f)
                count = 0
                if isinstance(data, dict):
                    for category, cases in data.items():
                        if isinstance(cases, list):
                            count += len(cases)
                elif isinstance(data, list):
                    count = len(data)
                print(f"  📁 {dataset_file.stem}: {count} test cases")
            except Exception as e:
                print(f"  📁 {dataset_file.stem}: Error reading file")
    
    print()
    print("🚀 To run benchmarks:")
    print("1. Use the interactive REPL:")
    print("   python repl.py")
    print("   Then type: /benchmark")
    print()
    print("2. Or run individual test cases:")
    print("   python repl.py 'Create an issue titled Test Issue'")
    print()
    print("💡 The REPL interface provides full benchmarking capabilities")
    print("   with proper async handling and real-time results.")
    
    return 0

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Simple RooLLM Benchmarking CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python benchmarks/simple_cli.py analytics --days 7
  python benchmarks/simple_cli.py benchmark-info --dataset tool
  
For full benchmarking, use: python repl.py
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Analytics command (works synchronously)
    analytics_parser = subparsers.add_parser('analytics', help='Show quality analytics')
    analytics_parser.add_argument('--days', '-d', type=int, default=30,
                                help='Number of days to analyze (default: 30)')
    
    # Benchmark info command (doesn't run actual benchmarks)
    benchmark_parser = subparsers.add_parser('benchmark-info', help='Show benchmark information')
    benchmark_parser.add_argument('--dataset', '-d', default='all',
                                help='Dataset to show info for (tool, rag, conversation_flows, all)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        print()
        print("💡 For full benchmarking capabilities, use:")
        print("   python repl.py")
        print("   Then type: /benchmark")
        return 1
    
    try:
        if args.command == 'analytics':
            result = show_analytics(args.days)
        elif args.command == 'benchmark-info':
            result = run_benchmark_info(args.dataset)
        else:
            parser.print_help()
            result = 1
        
        return result
        
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
        return 130
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 