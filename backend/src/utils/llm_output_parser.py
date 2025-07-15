# FILE: backend/src/utils/llm_output_parser.py

import re
import json

def extract_json_from_llm_output(text: str) -> str:
    """
    A robust helper to find a JSON object `{...}` or array `[...]` within
    the LLM's potentially conversational output. It handles markdown code fences.

    Args:
        text: The raw output string from the LLM.

    Returns:
        A string containing only the JSON part of the input, or an empty string if no JSON is found.
    """
    if not isinstance(text, str):
        return ""

    # Look for a JSON block wrapped in markdown ```json ... ```
    match = re.search(r'```(json)?\s*([\s\S]*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(2).strip()

    # If no markdown, find the first '{' or '[' and its corresponding closing '}' or ']'
    start_brace = text.find('{')
    start_bracket = text.find('[')

    # Determine the starting position and the type of brackets
    start_pos = -1
    if start_bracket != -1 and (start_bracket < start_brace or start_brace == -1):
        start_pos = start_bracket
        opener, closer = '[', ']'
    elif start_brace != -1:
        start_pos = start_brace
        opener, closer = '{', '}'
    else:
        return "" # No JSON object or array found

    # Find the matching closing bracket
    balance = 0
    for i, char in enumerate(text[start_pos:]):
        if char == opener:
            balance += 1
        elif char == closer:
            balance -= 1
        if balance == 0:
            return text[start_pos : start_pos + i + 1]
    
    return "" # Fallback if no complete JSON object is found