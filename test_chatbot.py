"""
Test the Advanced AI Chatbot
"""

from chatbot_ai import get_chatbot

def test_chatbot():
    """Test chatbot with various questions"""
    
    print("=" * 60)
    print("CRABEX Advanced AI Chatbot - Test Suite")
    print("=" * 60)
    
    # Get chatbot instance
    chatbot = get_chatbot()
    print(f"\n✓ Chatbot initialized successfully")
    print(f"✓ Backend: {chatbot.backend}")
    print()
    
    # Test questions
    test_questions = [
        "Hello!",
        "How secure is your data wiping process?",
        "What wiping methods do you support?",
        "Are you GDPR compliant?",
        "How can I verify a certificate?",
        "How much does it cost?",
        "How fast is the wiping?",
        "What devices are supported?",
        "Tell me about the anti-misuse features"
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'='*60}")
        print(f"Question {i}: {question}")
        print(f"{'='*60}")
        
        response = chatbot.get_response(question)
        print(response)
        print()
    
    print("=" * 60)
    print("✓ All tests completed successfully!")
    print(f"✓ Conversation history: {len(chatbot.conversation_history)} messages")
    print("=" * 60)

if __name__ == "__main__":
    test_chatbot()
