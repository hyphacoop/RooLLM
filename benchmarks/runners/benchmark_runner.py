"""
Main Benchmark Runner for RooLLM

This module provides the core benchmarking functionality, orchestrating
test case execution and evaluation using DeepEval metrics.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from deepeval import evaluate
from deepeval.test_case import LLMTestCase

try:
    from ..evaluators import (
        ToolCallingAccuracyMetric,
        ResponseQualityMetric,
        HallucinationDetectionMetric
    )
except ImportError:
    from benchmarks.evaluators import (
        ToolCallingAccuracyMetric,
        ResponseQualityMetric,
        HallucinationDetectionMetric
    )

logger = logging.getLogger(__name__)


class RooLLMBenchmarkRunner:
    """
    Main benchmark runner for RooLLM evaluation.
    
    This class orchestrates the execution of benchmark tests,
    evaluates responses using various metrics, and generates reports.
    """
    
    def __init__(self, roo_instance, config: Optional[Dict] = None):
        """
        Initialize the benchmark runner.
        
        Args:
            roo_instance: RooLLM instance to benchmark
            config: Optional configuration dictionary
        """
        self.roo = roo_instance
        self.config = config or {}
        
        # Initialize metrics
        self.metrics = {
            'tool_accuracy': ToolCallingAccuracyMetric(
                threshold=self.config.get('tool_accuracy_threshold', 0.8)
            ),
            'response_quality': ResponseQualityMetric(
                threshold=self.config.get('response_quality_threshold', 0.7)
            ),
            'hallucination': HallucinationDetectionMetric(
                threshold=self.config.get('hallucination_threshold', 0.8)
            )
        }
        
        # Results storage
        self.results = []
        self.summary_stats = {}
        
    async def run_benchmark(self, dataset_name: str = "all", 
                          output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Run benchmark evaluation on specified dataset.
        
        Args:
            dataset_name: Name of dataset to evaluate ("all", "tools", "rag", etc.)
            output_file: Optional file path to save results
            
        Returns:
            Benchmark results dictionary
        """
        logger.info(f"Starting benchmark run for dataset: {dataset_name}")
        start_time = time.time()
        
        try:
            # Load test cases
            test_cases = await self._load_test_cases(dataset_name)
            logger.info(f"Loaded {len(test_cases)} test cases")
            
            if not test_cases:
                logger.warning(f"No test cases found for dataset: {dataset_name}")
                return {"error": "No test cases found"}
            
            # Execute benchmark
            results = await self._execute_benchmark(test_cases)
            
            # Generate summary
            summary = self._generate_summary(results)
            
            # Save results if output file specified
            if output_file:
                await self._save_results(results, summary, output_file)
            
            execution_time = time.time() - start_time
            logger.info(f"Benchmark completed in {execution_time:.2f} seconds")
            
            return {
                "summary": summary,
                "results": results,
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error running benchmark: {e}", exc_info=True)
            return {"error": str(e)}

    async def evaluate_single_response(self, user_input: str, 
                                     expected_output: Optional[str] = None,
                                     expected_tool: Optional[str] = None,
                                     expected_params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Evaluate a single response from RooLLM.
        
        Args:
            user_input: User's input query
            expected_output: Expected response (optional)
            expected_tool: Expected tool to be called (optional)
            expected_params: Expected tool parameters (optional)
            
        Returns:
            Evaluation results
        """
        logger.debug(f"Evaluating single response for input: {user_input[:50]}...")
        
        try:
            # Get RooLLM response
            start_time = time.time()
            response = await self.roo.chat("benchmark_user", user_input, [])
            response_time = time.time() - start_time
            
            # Extract response content and tool calls
            response_content = response.get('content', '')
            tool_calls = self._extract_tool_calls_from_response(response)
            
            # Create test case
            test_case = LLMTestCase(
                input=user_input,
                actual_output=response_content,
                expected_output=expected_output,
                additional_metadata={
                    "expected_tool": expected_tool,
                    "expected_params": expected_params or {},
                    "actual_tool_calls": tool_calls,
                    "response_time": response_time
                }
            )
            
            # Evaluate with all metrics
            evaluation_results = {}
            for metric_name, metric in self.metrics.items():
                try:
                    score = await metric.a_measure(test_case)
                    evaluation_results[metric_name] = {
                        "score": score,
                        "success": metric.is_successful(),
                        "reason": getattr(metric, 'reason', 'No reason provided')
                    }
                except Exception as e:
                    logger.error(f"Error evaluating {metric_name}: {e}")
                    evaluation_results[metric_name] = {
                        "score": 0.0,
                        "success": False,
                        "reason": f"Evaluation error: {str(e)}"
                    }
            
            return {
                "input": user_input,
                "output": response_content,
                "response_time": response_time,
                "tool_calls": tool_calls,
                "evaluations": evaluation_results,
                "overall_score": self._calculate_overall_score(evaluation_results)
            }
            
        except Exception as e:
            logger.error(f"Error evaluating response: {e}", exc_info=True)
            return {
                "input": user_input,
                "error": str(e),
                "evaluations": {},
                "overall_score": 0.0
            }

    async def _load_test_cases(self, dataset_name: str) -> List[Dict[str, Any]]:
        """
        Load test cases from dataset files.
        
        Args:
            dataset_name: Name of the dataset to load
            
        Returns:
            List of test case dictionaries
        """
        datasets_dir = Path(__file__).parent.parent / "datasets"
        test_cases = []
        
        if dataset_name == "all":
            # Load all datasets
            dataset_files = list(datasets_dir.glob("*.json"))
        else:
            # Load specific dataset
            dataset_file = datasets_dir / f"{dataset_name}_test_cases.json"
            dataset_files = [dataset_file] if dataset_file.exists() else []
        
        for dataset_file in dataset_files:
            try:
                with open(dataset_file, 'r') as f:
                    data = json.load(f)
                    
                # Flatten nested structure if needed
                if isinstance(data, dict):
                    for category, cases in data.items():
                        if isinstance(cases, list):
                            for case in cases:
                                case['category'] = category
                                test_cases.append(case)
                        else:
                            test_cases.append(cases)
                elif isinstance(data, list):
                    test_cases.extend(data)
                    
                logger.debug(f"Loaded {len(data)} test cases from {dataset_file.name}")
                
            except Exception as e:
                logger.error(f"Error loading dataset {dataset_file}: {e}")
                continue
        
        return test_cases

    async def _execute_benchmark(self, test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute benchmark on all test cases.
        
        Args:
            test_cases: List of test case dictionaries
            
        Returns:
            List of evaluation results
        """
        results = []
        
        for i, test_case in enumerate(test_cases):
            logger.info(f"Processing test case {i+1}/{len(test_cases)}: {test_case.get('input', '')[:50]}...")
            
            try:
                result = await self.evaluate_single_response(
                    user_input=test_case.get('input', ''),
                    expected_output=test_case.get('expected_output'),
                    expected_tool=test_case.get('expected_tool'),
                    expected_params=test_case.get('expected_params', {})
                )
                
                # Add test case metadata
                result['test_case_id'] = test_case.get('id', i)
                result['category'] = test_case.get('category', 'unknown')
                result['description'] = test_case.get('description', '')
                
                results.append(result)
                
                # Brief pause to avoid overwhelming the system
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error processing test case {i}: {e}")
                results.append({
                    "test_case_id": test_case.get('id', i),
                    "error": str(e),
                    "overall_score": 0.0
                })
        
        return results

    def _extract_tool_calls_from_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract tool calls from RooLLM response.
        
        Args:
            response: RooLLM response dictionary
            
        Returns:
            List of tool call dictionaries
        """
        tool_calls = []
        
        # Check if response has tool_calls directly
        if "tool_calls" in response:
            tool_calls = response["tool_calls"]
        
        # Also check for tool calls in content (for text-based responses)
        content = response.get('content', '')
        if 'tool_call' in content.lower():
            # This would need to be adapted based on your actual response format
            # For now, we'll keep it simple
            pass
        
        return tool_calls

    def _calculate_overall_score(self, evaluations: Dict[str, Dict]) -> float:
        """
        Calculate overall score from individual evaluation scores.
        
        Args:
            evaluations: Dictionary of evaluation results
            
        Returns:
            Overall score (0.0-1.0)
        """
        if not evaluations:
            return 0.0
        
        # Weighted average of scores
        weights = {
            'tool_accuracy': 0.4,
            'response_quality': 0.3,
            'hallucination': 0.3
        }
        
        total_score = 0.0
        total_weight = 0.0
        
        for metric_name, result in evaluations.items():
            if metric_name in weights and 'score' in result:
                weight = weights[metric_name]
                score = result['score']
                total_score += score * weight
                total_weight += weight
        
        return total_score / total_weight if total_weight > 0 else 0.0

    def _generate_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate summary statistics from benchmark results.
        
        Args:
            results: List of evaluation results
            
        Returns:
            Summary statistics dictionary
        """
        if not results:
            return {"error": "No results to summarize"}
        
        # Calculate overall statistics
        overall_scores = [r.get('overall_score', 0.0) for r in results if 'overall_score' in r]
        
        summary = {
            "total_test_cases": len(results),
            "successful_evaluations": len([r for r in results if 'error' not in r]),
            "failed_evaluations": len([r for r in results if 'error' in r]),
            "overall_score": {
                "mean": sum(overall_scores) / len(overall_scores) if overall_scores else 0.0,
                "min": min(overall_scores) if overall_scores else 0.0,
                "max": max(overall_scores) if overall_scores else 0.0
            }
        }
        
        # Calculate metric-specific statistics
        metric_stats = {}
        for metric_name in self.metrics.keys():
            scores = []
            success_count = 0
            
            for result in results:
                if 'evaluations' in result and metric_name in result['evaluations']:
                    eval_result = result['evaluations'][metric_name]
                    if 'score' in eval_result:
                        scores.append(eval_result['score'])
                        if eval_result.get('success', False):
                            success_count += 1
            
            if scores:
                metric_stats[metric_name] = {
                    "mean_score": sum(scores) / len(scores),
                    "success_rate": success_count / len(scores),
                    "total_cases": len(scores)
                }
        
        summary["metric_stats"] = metric_stats
        
        # Category breakdown
        category_stats = {}
        for result in results:
            category = result.get('category', 'unknown')
            if category not in category_stats:
                category_stats[category] = {"count": 0, "scores": []}
            
            category_stats[category]["count"] += 1
            if 'overall_score' in result:
                category_stats[category]["scores"].append(result['overall_score'])
        
        # Calculate category averages
        for category, stats in category_stats.items():
            if stats["scores"]:
                stats["average_score"] = sum(stats["scores"]) / len(stats["scores"])
            else:
                stats["average_score"] = 0.0
        
        summary["category_stats"] = category_stats
        
        return summary

    async def _save_results(self, results: List[Dict], summary: Dict, 
                          output_file: str) -> None:
        """
        Save benchmark results to file.
        
        Args:
            results: Evaluation results
            summary: Summary statistics
            output_file: Output file path
        """
        try:
            output_data = {
                "timestamp": datetime.now().isoformat(),
                "summary": summary,
                "results": results
            }
            
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            logger.info(f"Results saved to {output_file}")
            
        except Exception as e:
            logger.error(f"Error saving results: {e}")


# Standalone function for easy CLI usage
async def run_benchmark_from_cli(dataset: str = "all", 
                                config_file: Optional[str] = None,
                                output_file: Optional[str] = None):
    """
    Run benchmark from command line interface.
    
    Args:
        dataset: Dataset name to evaluate
        config_file: Optional config file path
        output_file: Optional output file path
    """
    # This would be imported and used by the CLI interface
    # For now, it's a placeholder for the actual implementation
    pass 