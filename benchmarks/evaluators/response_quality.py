"""
Response Quality Metric for RooLLM Benchmarking

This evaluator assesses:
1. Relevance to user query
2. Helpfulness and completeness
3. Clarity and coherence
4. Appropriate use of Roo's personality
"""

import logging
from typing import Optional
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

logger = logging.getLogger(__name__)


class ResponseQualityMetric(BaseMetric):
    def __init__(self, threshold: float = 0.7, evaluation_model: str = None):
        """
        Initialize response quality metric.
        
        Args:
            threshold: Minimum score threshold for passing evaluation (0.0-1.0)
            evaluation_model: Optional LLM model for evaluation (defaults to rule-based)
        """
        self.threshold = threshold
        self.evaluation_model = evaluation_model
    
    @property
    def __name__(self):
        return "Response Quality"

    def measure(self, test_case: LLMTestCase) -> float:
        """
        Measure response quality for the given test case.
        
        Args:
            test_case: DeepEval test case containing input, output, and context
            
        Returns:
            Score between 0.0 and 1.0
        """
        try:
            scores = {}
            
            # 1. Relevance to query (30%)
            scores['relevance'] = self._evaluate_relevance(
                test_case.input, test_case.actual_output
            )
            
            # 2. Helpfulness and completeness (30%)
            scores['helpfulness'] = self._evaluate_helpfulness(
                test_case.input, test_case.actual_output, test_case.expected_output
            )
            
            # 3. Clarity and coherence (25%)
            scores['clarity'] = self._evaluate_clarity(test_case.actual_output)
            
            # 4. Roo personality appropriateness (15%)
            scores['personality'] = self._evaluate_personality(test_case.actual_output)
            
            # Calculate weighted average
            weights = {
                'relevance': 0.30,
                'helpfulness': 0.30,
                'clarity': 0.25,
                'personality': 0.15
            }
            
            total_score = sum(scores[key] * weights[key] for key in scores)
            
            self.score = total_score
            self.success = total_score >= self.threshold
            self.reason = self._generate_feedback(scores, weights)
            
            return total_score
            
        except Exception as e:
            logger.error(f"Error measuring response quality: {e}")
            self.score = 0.0
            self.reason = f"Evaluation error: {str(e)}"
            self.success = False
            return 0.0

    def _evaluate_relevance(self, query: str, response: str) -> float:
        """
        Evaluate how relevant the response is to the user query.
        
        Args:
            query: User's input query
            response: LLM's response
            
        Returns:
            Relevance score (0.0-1.0)
        """
        # Simple keyword-based relevance check
        query_words = set(query.lower().split())
        response_words = set(response.lower().split())
        
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        query_words = query_words - stop_words
        response_words = response_words - stop_words
        
        if not query_words:
            return 0.5  # Neutral score for empty query
        
        # Calculate overlap
        overlap = len(query_words.intersection(response_words))
        relevance = min(1.0, overlap / len(query_words))
        
        # Boost score if response directly addresses the query
        if any(word in response.lower() for word in ['here', 'answer', 'help', 'provide']):
            relevance = min(1.0, relevance * 1.2)
        
        return relevance

    def _evaluate_helpfulness(self, query: str, response: str, expected: Optional[str] = None) -> float:
        """
        Evaluate how helpful and complete the response is.
        
        Args:
            query: User's input query
            response: LLM's response
            expected: Expected response (if available)
            
        Returns:
            Helpfulness score (0.0-1.0)
        """
        score = 0.5  # Base score
        
        # Check for helpful indicators
        helpful_indicators = [
            'here', 'help', 'provide', 'show', 'explain', 'details',
            'information', 'answer', 'result', 'found', 'available'
        ]
        
        response_lower = response.lower()
        indicator_count = sum(1 for indicator in helpful_indicators if indicator in response_lower)
        score += min(0.3, indicator_count * 0.1)
        
        # Check response length appropriateness
        if len(response) < 10:
            score -= 0.2  # Too short
        elif len(response) > 1000:
            score -= 0.1  # Potentially too verbose
        
        # Compare with expected output if available
        if expected:
            # Simple similarity check
            expected_words = set(expected.lower().split())
            response_words = set(response.lower().split())
            similarity = len(expected_words.intersection(response_words)) / len(expected_words.union(response_words))
            score = (score + similarity) / 2
        
        return max(0.0, min(1.0, score))

    def _evaluate_clarity(self, response: str) -> float:
        """
        Evaluate clarity and coherence of the response.
        
        Args:
            response: LLM's response
            
        Returns:
            Clarity score (0.0-1.0)
        """
        score = 0.7  # Base score
        
        # Check for clear structure
        if '\n' in response:
            score += 0.1  # Bonus for structured formatting
        
        # Penalize excessive repetition
        words = response.lower().split()
        if len(words) > 0:
            unique_words = len(set(words))
            repetition_ratio = unique_words / len(words)
            if repetition_ratio < 0.5:
                score -= 0.2
        
        # Check for grammatical indicators
        if response.endswith('.') or response.endswith('!') or response.endswith('?'):
            score += 0.1  # Proper sentence ending
        
        # Penalize very short or very long responses
        if len(response) < 5:
            score -= 0.3
        elif len(response) > 2000:
            score -= 0.1
        
        return max(0.0, min(1.0, score))

    def _evaluate_personality(self, response: str) -> float:
        """
        Evaluate appropriate use of Roo's personality.
        
        Args:
            response: LLM's response
            
        Returns:
            Personality score (0.0-1.0)
        """
        score = 0.6  # Base score
        
        # Check for Roo characteristics
        response_lower = response.lower()
        
        # Positive indicators
        if any(phrase in response for phrase in ['I can help', 'Let me', 'Here\'s']):
            score += 0.2
        
        # Check for appropriate emoji use (sparingly, at the end)
        emoji_count = sum(1 for char in response if ord(char) > 127)  # Simple emoji detection
        if emoji_count == 0:
            score += 0.1  # Good, no excessive emoji
        elif emoji_count <= 2 and response.rstrip()[-1:] in '😊👍✨🎯':
            score += 0.2  # Appropriate emoji use
        elif emoji_count > 3:
            score -= 0.2  # Too many emojis
        
        # Penalize prohibited emoji
        if '🎉' in response:
            score -= 0.3  # Specifically prohibited
        
        # Check for conciseness (Roo should be concise)
        if len(response.split()) <= 50:
            score += 0.1
        elif len(response.split()) > 200:
            score -= 0.1
        
        return max(0.0, min(1.0, score))

    def _generate_feedback(self, scores: dict, weights: dict) -> str:
        """
        Generate human-readable feedback based on scores.
        
        Args:
            scores: Dictionary of individual scores
            weights: Score weights
            
        Returns:
            Feedback string
        """
        feedback_parts = []
        
        for metric, score in scores.items():
            weight = weights[metric]
            if score < 0.5:
                feedback_parts.append(f"Low {metric} ({score:.2f}, weight {weight:.1%})")
            elif score > 0.8:
                feedback_parts.append(f"Excellent {metric} ({score:.2f}, weight {weight:.1%})")
        
        if feedback_parts:
            return "; ".join(feedback_parts)
        else:
            return f"Good overall quality (scores: {', '.join(f'{k}={v:.2f}' for k, v in scores.items())})"

    async def a_measure(self, test_case: LLMTestCase) -> float:
        """Async version of measure method."""
        return self.measure(test_case)

    def is_successful(self) -> bool:
        """Check if the evaluation was successful."""
        return self.success 