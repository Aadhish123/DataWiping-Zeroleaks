
from chatbot_ai import CRABEXChatbot
import sys

try:
    bot = CRABEXChatbot()
    response = bot.get_response('hi')
    with open('debug_output.txt', 'w', encoding='utf-8') as f:
        f.write(repr(response))
    print("Debug output written to debug_output.txt")
except Exception as e:
    print(f"Error: {e}")
