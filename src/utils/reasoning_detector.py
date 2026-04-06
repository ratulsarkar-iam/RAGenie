"""
Simple reasoning detection using keyword matching
This can be enhanced with LangChain in the future
"""

def detect_reasoning_needed(message: str) -> bool:
    """
    Detect if a message requires reasoning based on keywords and patterns.
    
    Args:
        message: The user's message
        
    Returns:
        bool: True if reasoning is recommended
    """
    reasoning_keywords = [
        # Step-by-step requests
        'step by step', 'step-by-step', 'explain step by step',
        'break down', 'show steps', 'walk through',
        
        # Analytical requests
        'analyze', 'analysis', 'compare', 'difference between',
        'evaluate', 'assess', 'critique',
        
        # Problem solving
        'solve', 'calculate', 'compute', 'derive',
        'how to solve', 'find the solution',
        
        # Explanations
        'explain why', 'how does', 'why does', 'how do',
        'what causes', 'reason for', 'mechanism of',
        
        # Proofs and demonstrations
        'prove', 'demonstrate', 'show that', 'verify',
        
        # Complex questions
        'what is the process', 'describe the process',
        'how does it work', 'mechanism',
        
        # Mathematical/Scientific
        'formula', 'equation', 'theorem', 'derivation',
        'calculate the', 'find the value',
        
        # Planning/Design
        'design', 'plan', 'strategy', 'approach',
        'method', 'technique', 'algorithm'
    ]
    
    # Check for reasoning keywords
    message_lower = message.lower()
    for keyword in reasoning_keywords:
        if keyword in message_lower:
            return True
    
    # Check for question patterns that suggest reasoning
    reasoning_patterns = [
        'how many', 'how much', 'what is the relationship',
        'what are the advantages', 'what are the disadvantages',
        'pros and cons', 'strengths and weaknesses'
    ]
    
    for pattern in reasoning_patterns:
        if pattern in message_lower:
            return True
    
    # Check for multi-part questions (indicated by "and", "or", "also")
    if message.count('?') > 1 or (' and ' in message_lower and '?' in message):
        return True
    
    return False

# Example usage
if __name__ == "__main__":
    test_messages = [
        "Explain step by step how photosynthesis works",
        "What is the capital of France?",
        "Calculate the area of a circle with radius 5",
        "Tell me a joke",
        "Analyze the pros and cons of renewable energy",
        "Who are you?"
    ]
    
    for msg in test_messages:
        print(f"'{msg}' -> Reasoning: {detect_reasoning_needed(msg)}")
