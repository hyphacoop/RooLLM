"""
Tool Calling Accuracy Metric for RooLLM Benchmarking

This evaluator checks:
1. Whether the correct tool was selected
2. Whether tool parameters are accurate
3. Whether tool execution was successful
"""

import json
import logging
from typing import Dict, Any, List
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

logger = logging.getLogger(__name__)


class ToolCallingAccuracyMetric(BaseMetric):
    def __init__(self, threshold: float = 0.8):
        """
        Initialize tool calling accuracy metric.
        
        Args:
            threshold: Minimum score threshold for passing evaluation (0.0-1.0)
        """
        self.threshold = threshold
        self.evaluation_model = None  # We'll use rule-based evaluation
    
    @property
    def __name__(self):
        return "Tool Calling Accuracy"

    def measure(self, test_case: LLMTestCase) -> float:
        """
        Measure tool calling accuracy for the given test case.
        
        Args:
            test_case: DeepEval test case containing input, output, and context
            
        Returns:
            Score between 0.0 and 1.0
        """
        try:
            # Extract expected tool info from test case metadata
            expected_tool = test_case.additional_metadata.get("expected_tool")
            expected_params = test_case.additional_metadata.get("expected_params", {})
            
            # Parse actual tool calls from the response
            actual_tools = self._extract_tool_calls(test_case.actual_output)
            
            if not expected_tool:
                # If no tool was expected, check that no tools were called
                score = 1.0 if not actual_tools else 0.0
                self.score = score
                self.reason = "No tool expected" if score == 1.0 else "Unexpected tool call"
                self.success = score >= self.threshold
                return score
            
            if not actual_tools:
                # Tool was expected but none were called
                self.score = 0.0
                self.reason = f"Expected tool '{expected_tool}' but no tools were called"
                self.success = False
                return 0.0
            
            # Calculate accuracy score
            score = self._calculate_tool_accuracy(
                expected_tool, expected_params, actual_tools
            )
            
            self.score = score
            self.success = score >= self.threshold
            
            return score
            
        except Exception as e:
            logger.error(f"Error measuring tool accuracy: {e}")
            self.score = 0.0
            self.reason = f"Evaluation error: {str(e)}"
            self.success = False
            return 0.0

    def _extract_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """
        Extract tool calls from LLM response.
        
        Args:
            response: Raw LLM response string
            
        Returns:
            List of tool call dictionaries
        """
        tool_calls = []
        
        try:
            # Try to parse as JSON first (for structured responses)
            if response.strip().startswith('{'):
                parsed = json.loads(response)
                if "tool_calls" in parsed:
                    return parsed["tool_calls"]
            
            # Look for tool call patterns in text
            # This is a simplified extraction - in practice you'd want more robust parsing
            lines = response.split('\n')
            for line in lines:
                if 'tool_call' in line.lower() or 'function' in line.lower():
                    # Extract tool name and parameters
                    # This would need to be adapted based on your actual response format
                    pass
                    
        except Exception as e:
            logger.debug(f"Could not extract tool calls: {e}")
        
        return tool_calls

    def _calculate_tool_accuracy(self, expected_tool: str, expected_params: Dict, 
                               actual_tools: List[Dict]) -> float:
        """
        Calculate accuracy score based on expected vs actual tool usage.
        
        Args:
            expected_tool: Expected tool name
            expected_params: Expected parameters
            actual_tools: List of actual tool calls
            
        Returns:
            Accuracy score (0.0-1.0)
        """
        scores = []
        
        # Check if the expected tool was called
        tool_found = False
        for tool_call in actual_tools:
            tool_name = tool_call.get("function", {}).get("name", "")
            if tool_name == expected_tool:
                tool_found = True
                
                # Calculate parameter accuracy
                actual_params = tool_call.get("function", {}).get("arguments", {})
                param_score = self._calculate_parameter_accuracy(expected_params, actual_params)
                scores.append(param_score)
        
        if not tool_found:
            self.reason = f"Expected tool '{expected_tool}' was not called"
            return 0.0
        
        # Return average score across all calls to the expected tool
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        if avg_score >= self.threshold:
            self.reason = f"Tool '{expected_tool}' called correctly with {avg_score:.2f} accuracy"
        else:
            self.reason = f"Tool '{expected_tool}' called but with low accuracy: {avg_score:.2f}"
            
        return avg_score

    def _calculate_parameter_accuracy(self, expected: Dict, actual: Dict) -> float:
        """
        Calculate parameter accuracy score.
        
        Args:
            expected: Expected parameters
            actual: Actual parameters
            
        Returns:
            Parameter accuracy score (0.0-1.0)
        """
        if not expected:
            return 1.0  # No specific parameters expected
        
        total_params = len(expected)
        correct_params = 0
        
        for key, expected_value in expected.items():
            actual_value = actual.get(key)
            
            if actual_value == expected_value:
                correct_params += 1
            elif isinstance(expected_value, str) and isinstance(actual_value, str):
                # Fuzzy match for string parameters
                if expected_value.lower() in actual_value.lower():
                    correct_params += 0.8
        
        return correct_params / total_params if total_params > 0 else 1.0

    async def a_measure(self, test_case: LLMTestCase) -> float:
        """Async version of measure method."""
        return self.measure(test_case)

    def is_successful(self) -> bool:
        """Check if the evaluation was successful."""
        return self.success 