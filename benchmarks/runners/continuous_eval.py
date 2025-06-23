"""
Continuous Evaluation System for RooLLM

This module provides real-time evaluation capabilities that can be
integrated into the normal RooLLM chat flow to provide ongoing
quality assessment without disrupting the user experience.
"""

import asyncio
import logging
import random
import time
from typing import Dict, List, Any, Optional, Callable

try:
    from ..evaluators import ResponseQualityMetric, HallucinationDetectionMetric
    from .benchmark_runner import RooLLMBenchmarkRunner
except ImportError:
    from benchmarks.evaluators import ResponseQualityMetric, HallucinationDetectionMetric
    from benchmarks.runners.benchmark_runner import RooLLMBenchmarkRunner

logger = logging.getLogger(__name__)


class ContinuousEvaluator:
    """
    Continuous evaluation system for real-time quality assessment.
    
    This class provides lightweight evaluation that can run alongside
    normal RooLLM operations without significantly impacting performance.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the continuous evaluator.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # Sampling configuration
        self.sampling_rate = self.config.get('sampling_rate', 0.1)  # 10% of responses
        self.min_response_length = self.config.get('min_response_length', 10)
        
        # Lightweight metrics for continuous evaluation
        self.metrics = {
            'response_quality': ResponseQualityMetric(
                threshold=self.config.get('response_quality_threshold', 0.7)
            ),
            'hallucination': HallucinationDetectionMetric(
                threshold=self.config.get('hallucination_threshold', 0.8)
            )
        }
        
        # Results storage
        self.evaluation_results = []
        self.stats = {
            'total_evaluations': 0,
            'total_responses': 0,
            'avg_quality_score': 0.0,
            'avg_hallucination_score': 0.0,
            'last_evaluation': None
        }
        
        # Callbacks for integration
        self.result_callbacks: List[Callable] = []

    def should_evaluate(self, user: str, content: str, response: Dict[str, Any]) -> bool:
        """
        Determine if a response should be evaluated.
        
        Args:
            user: User identifier
            content: User's input
            response: RooLLM response
            
        Returns:
            True if response should be evaluated
        """
        # Skip evaluation for very short responses
        response_content = response.get('content', '')
        if len(response_content) < self.min_response_length:
            return False
        
        # Skip evaluation for certain users (e.g., test users)
        if user.startswith('test_') or user == 'benchmark_user':
            return False
        
        # Sample based on configured rate
        return random.random() < self.sampling_rate

    async def evaluate_response(self, user: str, content: str, response: Dict[str, Any], 
                              context: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Evaluate a response using lightweight metrics.
        
        Args:
            user: User identifier
            content: User's input
            response: RooLLM response
            context: Optional context for evaluation
            
        Returns:
            Evaluation results or None if not evaluated
        """
        self.stats['total_responses'] += 1
        
        if not self.should_evaluate(user, content, response):
            return None
        
        logger.debug(f"Evaluating response for user {user}: {content[:50]}...")
        
        try:
            start_time = time.time()
            
            # Create simplified test case for evaluation
            from deepeval.test_case import LLMTestCase
            
            test_case = LLMTestCase(
                input=content,
                actual_output=response.get('content', ''),
                retrieval_context=context or [],
                additional_metadata={
                    'user': user,
                    'tool_calls': response.get('tool_calls', []),
                    'timestamp': time.time()
                }
            )
            
            # Run lightweight evaluation
            evaluation_results = {}
            for metric_name, metric in self.metrics.items():
                try:
                    score = await metric.a_measure(test_case)
                    evaluation_results[metric_name] = {
                        'score': score,
                        'success': metric.is_successful(),
                        'reason': getattr(metric, 'reason', 'No reason provided')
                    }
                except Exception as e:
                    logger.error(f"Error in continuous evaluation {metric_name}: {e}")
                    evaluation_results[metric_name] = {
                        'score': 0.0,
                        'success': False,
                        'reason': f"Evaluation error: {str(e)}"
                    }
            
            evaluation_time = time.time() - start_time
            
            # Compile results
            result = {
                'timestamp': time.time(),
                'user': user,
                'input': content,
                'output': response.get('content', ''),
                'evaluations': evaluation_results,
                'evaluation_time': evaluation_time,
                'overall_score': self._calculate_overall_score(evaluation_results)
            }
            
            # Store results
            self.evaluation_results.append(result)
            self._update_stats(result)
            
            # Trigger callbacks
            await self._trigger_callbacks(result)
            
            self.stats['total_evaluations'] += 1
            self.stats['last_evaluation'] = time.time()
            
            logger.debug(f"Continuous evaluation completed in {evaluation_time:.3f}s, "
                        f"overall score: {result['overall_score']:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in continuous evaluation: {e}", exc_info=True)
            return None

    def _calculate_overall_score(self, evaluations: Dict[str, Dict]) -> float:
        """Calculate overall score from evaluations."""
        if not evaluations:
            return 0.0
        
        weights = {
            'response_quality': 0.6,
            'hallucination': 0.4
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

    def _update_stats(self, result: Dict[str, Any]) -> None:
        """Update running statistics."""
        evaluations = result.get('evaluations', {})
        
        # Update quality score average
        if 'response_quality' in evaluations:
            quality_score = evaluations['response_quality'].get('score', 0.0)
            current_avg = self.stats['avg_quality_score']
            total_evals = self.stats['total_evaluations']
            self.stats['avg_quality_score'] = (current_avg * total_evals + quality_score) / (total_evals + 1)
        
        # Update hallucination score average
        if 'hallucination' in evaluations:
            halluc_score = evaluations['hallucination'].get('score', 0.0)
            current_avg = self.stats['avg_hallucination_score']
            total_evals = self.stats['total_evaluations']
            self.stats['avg_hallucination_score'] = (current_avg * total_evals + halluc_score) / (total_evals + 1)

    async def _trigger_callbacks(self, result: Dict[str, Any]) -> None:
        """Trigger registered callbacks with evaluation results."""
        for callback in self.result_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(result)
                else:
                    callback(result)
            except Exception as e:
                logger.error(f"Error in evaluation callback: {e}")

    def add_result_callback(self, callback: Callable) -> None:
        """
        Add a callback to be triggered when evaluation results are available.
        
        Args:
            callback: Function to call with evaluation results
        """
        self.result_callbacks.append(callback)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get current evaluation statistics.
        
        Returns:
            Dictionary of current statistics
        """
        return self.stats.copy()

    def get_recent_results(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent evaluation results.
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            List of recent evaluation results
        """
        return self.evaluation_results[-limit:] if self.evaluation_results else []

    def reset_stats(self) -> None:
        """Reset all statistics and results."""
        self.evaluation_results.clear()
        self.stats = {
            'total_evaluations': 0,
            'total_responses': 0,
            'avg_quality_score': 0.0,
            'avg_hallucination_score': 0.0,
            'last_evaluation': None
        }

    def get_quality_trend(self, window_size: int = 50) -> List[float]:
        """
        Get quality score trend over recent evaluations.
        
        Args:
            window_size: Number of recent evaluations to consider
            
        Returns:
            List of quality scores
        """
        recent_results = self.get_recent_results(window_size)
        quality_scores = []
        
        for result in recent_results:
            evaluations = result.get('evaluations', {})
            if 'response_quality' in evaluations:
                quality_scores.append(evaluations['response_quality'].get('score', 0.0))
        
        return quality_scores

    def detect_quality_issues(self, threshold: float = 0.5, 
                            window_size: int = 10) -> List[Dict[str, Any]]:
        """
        Detect potential quality issues in recent evaluations.
        
        Args:
            threshold: Score threshold below which to flag issues
            window_size: Number of recent evaluations to check
            
        Returns:
            List of flagged evaluation results
        """
        recent_results = self.get_recent_results(window_size)
        issues = []
        
        for result in recent_results:
            overall_score = result.get('overall_score', 1.0)
            if overall_score < threshold:
                issues.append({
                    'timestamp': result.get('timestamp'),
                    'user': result.get('user'),
                    'input': result.get('input', '')[:100],
                    'overall_score': overall_score,
                    'issues': self._identify_specific_issues(result)
                })
        
        return issues

    def _identify_specific_issues(self, result: Dict[str, Any]) -> List[str]:
        """Identify specific quality issues in an evaluation result."""
        issues = []
        evaluations = result.get('evaluations', {})
        
        for metric_name, eval_result in evaluations.items():
            if not eval_result.get('success', True):
                reason = eval_result.get('reason', 'Unknown issue')
                issues.append(f"{metric_name}: {reason}")
        
        return issues


# Integration helper functions
async def setup_continuous_evaluation(roo_instance, config: Optional[Dict] = None) -> ContinuousEvaluator:
    """
    Set up continuous evaluation for a RooLLM instance.
    
    Args:
        roo_instance: RooLLM instance to monitor
        config: Configuration dictionary
        
    Returns:
        Configured ContinuousEvaluator instance
    """
    evaluator = ContinuousEvaluator(config)
    
    # Example callback to log quality issues
    def log_quality_issues(result):
        overall_score = result.get('overall_score', 1.0)
        if overall_score < 0.5:
            logger.warning(f"Low quality response detected: {overall_score:.2f} "
                         f"for input: {result.get('input', '')[:50]}...")
    
    evaluator.add_result_callback(log_quality_issues)
    
    return evaluator 