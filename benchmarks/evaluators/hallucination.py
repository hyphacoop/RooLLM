"""
Hallucination Detection Metric for RooLLM Benchmarking

This evaluator checks for:
1. Factual accuracy against retrieved context
2. Consistency with tool results
3. Appropriate uncertainty expression
4. Source citation accuracy
"""

import json
import logging
from typing import List, Dict, Any
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

logger = logging.getLogger(__name__)


class HallucinationDetectionMetric(BaseMetric):
    def __init__(self, threshold: float = 0.8):
        """
        Initialize hallucination detection metric.
        
        Args:
            threshold: Minimum score threshold for passing evaluation (0.0-1.0)
        """
        self.threshold = threshold
        self.evaluation_model = None  # Rule-based evaluation
    
    @property
    def __name__(self):
        return "Hallucination Detection"

    def measure(self, test_case: LLMTestCase) -> float:
        """
        Measure hallucination level for the given test case.
        
        Args:
            test_case: DeepEval test case containing input, output, and context
            
        Returns:
            Score between 0.0 and 1.0 (higher = less hallucination)
        """
        try:
            scores = {}
            
            # 1. Factual consistency with context (40%)
            scores['factual_consistency'] = self._check_factual_consistency(
                test_case.actual_output, test_case.retrieval_context or []
            )
            
            # 2. Tool result consistency (30%)
            scores['tool_consistency'] = self._check_tool_consistency(
                test_case.actual_output, test_case.additional_metadata.get('tool_results', [])
            )
            
            # 3. Appropriate uncertainty expression (20%)
            scores['uncertainty'] = self._check_uncertainty_expression(
                test_case.actual_output, test_case.input
            )
            
            # 4. Source citation accuracy (10%)
            scores['citations'] = self._check_citation_accuracy(
                test_case.actual_output, test_case.retrieval_context or []
            )
            
            # Calculate weighted average
            weights = {
                'factual_consistency': 0.40,
                'tool_consistency': 0.30,
                'uncertainty': 0.20,
                'citations': 0.10
            }
            
            total_score = sum(scores[key] * weights[key] for key in scores)
            
            self.score = total_score
            self.success = total_score >= self.threshold
            self.reason = self._generate_hallucination_feedback(scores, weights)
            
            return total_score
            
        except Exception as e:
            logger.error(f"Error measuring hallucination: {e}")
            self.score = 0.0
            self.reason = f"Evaluation error: {str(e)}"
            self.success = False
            return 0.0

    def _check_factual_consistency(self, response: str, context: List[str]) -> float:
        """
        Check if response is factually consistent with provided context.
        
        Args:
            response: LLM response
            context: List of context strings (from RAG or tools)
            
        Returns:
            Consistency score (0.0-1.0)
        """
        if not context:
            # If no context provided, assume response is acceptable
            return 0.8
        
        response_lower = response.lower()
        context_text = ' '.join(context).lower()
        
        # Check for contradictions
        contradiction_indicators = [
            ('yes', 'no'), ('true', 'false'), ('can', 'cannot'),
            ('is', 'is not'), ('will', 'will not'), ('has', 'has not')
        ]
        
        contradiction_count = 0
        for pos, neg in contradiction_indicators:
            if pos in response_lower and neg in context_text:
                contradiction_count += 1
            elif neg in response_lower and pos in context_text:
                contradiction_count += 1
        
        # Check for factual alignment
        # Extract key facts from context and check if they're respected in response
        context_facts = self._extract_key_facts(context_text)
        response_facts = self._extract_key_facts(response_lower)
        
        if context_facts:
            alignment_score = len(context_facts.intersection(response_facts)) / len(context_facts)
        else:
            alignment_score = 0.8  # Neutral if no clear facts
        
        # Penalize contradictions
        consistency_score = alignment_score - (contradiction_count * 0.2)
        
        return max(0.0, min(1.0, consistency_score))

    def _check_tool_consistency(self, response: str, tool_results: List[Dict]) -> float:
        """
        Check if response is consistent with tool execution results.
        
        Args:
            response: LLM response
            tool_results: List of tool execution results
            
        Returns:
            Consistency score (0.0-1.0)
        """
        if not tool_results:
            return 0.9  # High score if no tools were used
        
        consistency_scores = []
        
        for tool_result in tool_results:
            tool_name = tool_result.get('tool_name', '')
            result_data = tool_result.get('result', {})
            
            # Check if response mentions tool results appropriately
            if isinstance(result_data, dict):
                # Look for key data points from tool results in response
                score = self._check_result_integration(response, result_data, tool_name)
                consistency_scores.append(score)
            elif isinstance(result_data, str):
                # For string results, check if content is reflected
                if result_data.lower() in response.lower():
                    consistency_scores.append(0.9)
                else:
                    consistency_scores.append(0.3)
        
        return sum(consistency_scores) / len(consistency_scores) if consistency_scores else 0.9

    def _check_uncertainty_expression(self, response: str, query: str) -> float:
        """
        Check if response appropriately expresses uncertainty when appropriate.
        
        Args:
            response: LLM response
            query: User query
            
        Returns:
            Uncertainty expression score (0.0-1.0)
        """
        response_lower = response.lower()
        
        # Uncertainty indicators (positive)
        uncertainty_phrases = [
            'i think', 'it seems', 'appears to', 'might be', 'could be',
            'not sure', 'unclear', 'uncertain', 'don\'t know',
            'based on available', 'according to'
        ]
        
        # Overconfidence indicators (negative)
        overconfidence_phrases = [
            'definitely', 'absolutely', 'certainly', 'without doubt',
            'guaranteed', 'always', 'never', 'impossible'
        ]
        
        uncertainty_count = sum(1 for phrase in uncertainty_phrases if phrase in response_lower)
        overconfidence_count = sum(1 for phrase in overconfidence_phrases if phrase in response_lower)
        
        # Check if query asks for definitive information
        definitive_query = any(word in query.lower() for word in ['what is', 'how much', 'when', 'where'])
        
        score = 0.7  # Base score
        
        if not definitive_query and uncertainty_count > 0:
            score += 0.2  # Good uncertainty expression
        elif definitive_query and overconfidence_count > 2:
            score -= 0.3  # Too overconfident for uncertain information
        
        return max(0.0, min(1.0, score))

    def _check_citation_accuracy(self, response: str, context: List[str]) -> float:
        """
        Check accuracy of source citations in response.
        
        Args:
            response: LLM response
            context: Available context sources
            
        Returns:
            Citation accuracy score (0.0-1.0)
        """
        # Look for citation patterns
        citation_patterns = ['according to', 'based on', 'from', 'source:', 'ref:']
        
        has_citations = any(pattern in response.lower() for pattern in citation_patterns)
        
        if not has_citations and not context:
            return 1.0  # No citations needed or expected
        elif not has_citations and context:
            return 0.7  # Could have cited sources but didn't (minor issue)
        elif has_citations and not context:
            return 0.3  # Made up citations
        else:
            # Has citations and context - check accuracy
            return 0.9  # Assume accurate for now (would need more sophisticated checking)

    def _extract_key_facts(self, text: str) -> set:
        """
        Extract key factual statements from text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Set of key facts
        """
        # Simple fact extraction based on patterns
        facts = set()
        
        # Look for numerical facts
        import re
        numbers = re.findall(r'\b\d+(?:\.\d+)?\b', text)
        facts.update(numbers)
        
        # Look for proper nouns (simplified)
        words = text.split()
        for word in words:
            if word[0].isupper() and len(word) > 2:
                facts.add(word.lower())
        
        return facts

    def _check_result_integration(self, response: str, result_data: Dict, tool_name: str) -> float:
        """
        Check how well tool results are integrated into the response.
        
        Args:
            response: LLM response
            result_data: Tool execution result
            tool_name: Name of the tool
            
        Returns:
            Integration score (0.0-1.0)
        """
        response_lower = response.lower()
        
        # Check if tool name or results are mentioned
        tool_mentioned = tool_name.lower() in response_lower
        
        # Check if key result data appears in response
        result_integration = 0.0
        if isinstance(result_data, dict):
            for key, value in result_data.items():
                if str(value).lower() in response_lower:
                    result_integration += 0.3
        
        # Combine scores
        integration_score = (0.3 if tool_mentioned else 0.0) + min(0.7, result_integration)
        
        return integration_score

    def _generate_hallucination_feedback(self, scores: dict, weights: dict) -> str:
        """
        Generate feedback about hallucination detection.
        
        Args:
            scores: Individual scores
            weights: Score weights
            
        Returns:
            Feedback string
        """
        issues = []
        
        for metric, score in scores.items():
            if score < 0.6:
                issues.append(f"Low {metric.replace('_', ' ')} ({score:.2f})")
        
        if issues:
            return f"Potential hallucination indicators: {'; '.join(issues)}"
        else:
            return f"Good factual consistency (avg score: {sum(scores.values())/len(scores):.2f})"

    async def a_measure(self, test_case: LLMTestCase) -> float:
        """Async version of measure method."""
        return self.measure(test_case)

    def is_successful(self) -> bool:
        """Check if the evaluation was successful."""
        return self.success 