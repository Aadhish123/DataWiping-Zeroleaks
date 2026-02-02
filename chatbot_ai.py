"""
Advanced AI Chatbot System for CRABEX
Supports multiple backends: OpenAI GPT, Local NLP, Pattern Matching
"""

import os
import json
from datetime import datetime
import re

# Try to import optional AI libraries (disabled by default to avoid conflicts)
OPENAI_AVAILABLE = False
TRANSFORMERS_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except (ImportError, Exception):
    pass

# Transformers disabled by default due to heavy dependencies
# Uncomment below to enable:
# try:
#     from transformers import pipeline
#     TRANSFORMERS_AVAILABLE = True
# except (ImportError, Exception):
#     pass


class CRABEXChatbot:
    """
    Advanced chatbot with multiple intelligence levels
    """
    
    def __init__(self):
        self.conversation_history = []
        self.context = self._load_knowledge_base()
        self.openai_api_key = os.getenv('OPENAI_API_KEY', '')
        
        # Initialize AI backend
        if self.openai_api_key and OPENAI_AVAILABLE:
            self.backend = 'openai'
            openai.api_key = self.openai_api_key
            print("[OK] Chatbot using OpenAI GPT backend")
        elif TRANSFORMERS_AVAILABLE:
            self.backend = 'transformers'
            try:
                self.qa_pipeline = pipeline("question-answering", model="distilbert-base-cased-distilled-squad")
                print("[OK] Chatbot using Transformers backend")
            except:
                self.backend = 'advanced_pattern'
                print("[OK] Chatbot using Advanced Pattern Matching")
        else:
            self.backend = 'advanced_pattern'
            print("[OK] Chatbot using Advanced Pattern Matching")
    
    def _load_knowledge_base(self):
        """Load comprehensive knowledge base about CRABEX"""
        return {
            'company_info': {
                'name': 'CRABEX - Zero Leaks Data Wiping Service',
                'description': 'Professional data destruction service with military-grade security',
                'mission': 'Provide secure, compliant, and verifiable data destruction'
            },
            'security': {
                'encryption': 'AES-256 military-grade encryption',
                'standards': ['DoD 5220.22-M', 'NIST SP 800-88 Rev. 1', 'ISO 27001', 'SOC 2 Type II'],
                'features': [
                    'Multiple overwrite passes (1-35 passes)',
                    'Cryptographically secure random data',
                    'Hardware-based secure erase for SSDs',
                    'Digital signatures (RSA-2048)',
                    'Complete audit trail',
                    'Forensically unrecoverable'
                ]
            },
            'wiping_methods': {
                'clear': 'NIST Clear - Single pass with zeros/ones',
                'purge': 'DoD 3-pass - Zeros, ones, random data',
                'destroy': 'DoD 7-pass - Maximum security overwrite',
                'gutmann': 'Gutmann 35-pass - Legacy magnetic storage',
                'ata': 'ATA Secure Erase - Hardware-based SSD wiping'
            },
            'compliance': {
                'gdpr': 'Article 17 - Right to Erasure compliance',
                'hipaa': 'HIPAA Security Rule compliant',
                'sox': 'Sarbanes-Oxley Section 404 compliant',
                'iso27001': 'ISO 27001 Information Security certified',
                'soc2': 'SOC 2 Type II Security & Privacy certified'
            },
            'verification': {
                'method': 'Third-party verification codes',
                'format': 'VERIFY-XXXX-XXXX-XXXX',
                'features': [
                    'No login required',
                    'Tamper detection',
                    'Complete certificate details',
                    'Verification audit trail',
                    'Independent validation'
                ]
            },
            'pricing': {
                'free': '3 wipes per day, basic methods',
                'professional': 'Unlimited wipes, all methods, priority support',
                'enterprise': 'White-label, API access, custom compliance'
            },
            'performance': {
                'buffer_size': '16MB for optimal throughput',
                'workers': '32 parallel workers',
                'io': 'Memory-mapped I/O',
                'speed': '3-6x faster than traditional methods'
            },
            'anti_misuse': [
                '2FA authentication via SMS',
                'Hardware fingerprinting',
                'IP geolocation tracking',
                'Rate limiting',
                'Audit logging',
                'Suspicious activity detection',
                'Mandatory purpose declaration',
                'Legal warnings',
                'Law enforcement cooperation'
            ]
        }
    
    def _extract_intent(self, message):
        """Extract user intent from message"""
        message_lower = message.lower()
        
        intents = {
            'greeting': ['hello', 'hi', 'hey', 'greetings', 'good morning', 'good afternoon', 'good evening'],
            'security': ['secure', 'security', 'safe', 'protection', 'encrypted', 'encryption'],
            'methods': ['method', 'how', 'process', 'algorithm', 'technique', 'wipe', 'destroy'],
            'compliance': ['compliance', 'certificate', 'standard', 'regulation', 'gdpr', 'hipaa', 'sox'],
            'verification': ['verify', 'verification', 'validate', 'authentic', 'check'],
            'pricing': ['price', 'cost', 'pricing', 'fee', 'charge', 'expensive', 'affordable'],
            'speed': ['fast', 'quick', 'speed', 'time', 'long', 'duration', 'optimize'],
            'support': ['support', 'help', 'assistance', 'problem', 'issue', 'error'],
            'features': ['feature', 'capability', 'function', 'what can', 'anti-misuse'],
            'devices': ['device', 'storage', 'hdd', 'ssd', 'usb', 'disk', 'drive'],
            'legal': ['legal', 'law', 'criminal', 'police', 'evidence', 'court'],
            'thanks': ['thank', 'thanks', 'appreciate']
        }
        
        detected_intents = []
        for intent, keywords in intents.items():
            if any(keyword in message_lower for keyword in keywords):
                detected_intents.append(intent)
        
        return detected_intents if detected_intents else ['general']
    
    def _generate_response_openai(self, message):
        """Generate response using OpenAI GPT"""
        try:
            system_prompt = f"""You are an AI assistant for CRABEX Data Wiping Service. 
            
Your knowledge base:
{json.dumps(self.context, indent=2)}

Respond professionally, accurately, and helpfully. Use emojis appropriately. Format responses clearly.
If asked about features not in the knowledge base, politely explain what CRABEX actually offers."""

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    *[{"role": msg["role"], "content": msg["content"]} 
                      for msg in self.conversation_history[-10:]],
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"OpenAI error: {e}")
            return self._generate_response_advanced(message)
    
    def _generate_response_transformers(self, message):
        """Generate response using Transformers QA model"""
        try:
            # Prepare context from knowledge base
            context_text = json.dumps(self.context)
            
            result = self.qa_pipeline(
                question=message,
                context=context_text
            )
            
            return result['answer']
            
        except Exception as e:
            print(f"Transformers error: {e}")
            return self._generate_response_advanced(message)
    
    def _generate_response_advanced(self, message):
        """Advanced pattern matching with context awareness"""
        intents = self._extract_intent(message)
        message_lower = message.lower()
        
        # Multi-intent response
        if len(intents) > 1:
            responses = []
            for intent in intents[:2]:  # Handle top 2 intents
                responses.append(self._get_intent_response(intent, message_lower))
            return "\n\n".join(responses)
        
        # Single intent response
        intent = intents[0]
        return self._get_intent_response(intent, message_lower)
    
    def _get_intent_response(self, intent, message_lower):
        """Get response for specific intent"""
        
        if intent == 'greeting':
            return ("👋 Hello! I'm your CRABEX Data Wiping Assistant. I can help you with:\n\n"
                   "• **Security** - How we protect your data\n"
                   "• **Methods** - Wiping techniques and standards\n"
                   "• **Compliance** - Certifications (GDPR, HIPAA, etc.)\n"
                   "• **Verification** - Third-party authentication\n"
                   "• **Pricing** - Plans and costs\n"
                   "• **Performance** - Speed and optimization\n\n"
                   "What would you like to know?")
        
        elif intent == 'security':
            sec = self.context['security']
            return (f"🔒 **CRABEX Security Features:**\n\n"
                   f"**Encryption:** {sec['encryption']}\n\n"
                   f"**Standards Compliance:**\n" + 
                   "\n".join(f"• {std}" for std in sec['standards']) + "\n\n"
                   f"**Key Features:**\n" +
                   "\n".join(f"• {feat}" for feat in sec['features'][:5]) + "\n\n"
                   f"Your data is completely destroyed and forensically unrecoverable!")
        
        elif intent == 'methods':
            if 'how' in message_lower and 'work' in message_lower:
                return ("⚙️ **How CRABEX Data Wiping Works:**\n\n"
                       "**Process:**\n"
                       "1. **Authentication** - 2FA via SMS\n"
                       "2. **Target Selection** - Choose file/folder/disk\n"
                       "3. **Method Selection** - Clear, Purge, or Destroy\n"
                       "4. **Verification** - Purpose declaration (mandatory)\n"
                       "5. **Execution** - Multiple overwrite passes\n"
                       "6. **Validation** - Pattern verification\n"
                       "7. **Deletion** - Secure file removal\n"
                       "8. **Certificate** - Digital proof with verification code\n\n"
                       "All operations are logged and monitored for compliance!")
            
            methods = self.context['wiping_methods']
            return ("⚙️ **Available Wiping Methods:**\n\n" +
                   "\n".join(f"**{key.upper()}:** {value}" for key, value in methods.items()) + "\n\n"
                   "All methods include verification and digital certification!")
        
        elif intent == 'compliance':
            comp = self.context['compliance']
            return ("✅ **Compliance & Certifications:**\n\n" +
                   "\n".join(f"**{key.upper()}:** {value}" for key, value in comp.items()) + "\n\n"
                   "Every operation generates a compliance certificate with:\n"
                   "• Digital signature (RSA-2048)\n"
                   "• Timestamp and audit trail\n"
                   "• Third-party verification code\n"
                   "• QR code for instant validation\n\n"
                   "Perfect for regulatory audits and legal requirements!")
        
        elif intent == 'verification':
            ver = self.context['verification']
            return (f"🔍 **Third-Party Verification:**\n\n"
                   f"**Format:** {ver['format']}\n\n"
                   f"**How it Works:**\n"
                   "1. Each certificate gets a unique verification code\n"
                   "2. Anyone can verify at: /verify\n"
                   "3. No login required - truly independent\n"
                   "4. Instant authentication\n\n"
                   f"**Features:**\n" +
                   "\n".join(f"• {feat}" for feat in ver['features']) + "\n\n"
                   "**Who Can Verify:**\n"
                   "• Auditors • Legal teams • Compliance officers\n"
                   "• Clients • Insurance • Regulatory bodies")
        
        elif intent == 'pricing':
            pricing = self.context['pricing']
            return ("💰 **CRABEX Pricing Plans:**\n\n"
                   f"**FREE TIER:**\n{pricing['free']}\n\n"
                   f"**PROFESSIONAL:**\n{pricing['professional']}\n\n"
                   f"**ENTERPRISE:**\n{pricing['enterprise']}\n\n"
                   "**No hidden fees!** All plans include:\n"
                   "• Digital certificates\n"
                   "• Audit trail\n"
                   "• Verification codes\n"
                   "• Compliance documentation")
        
        elif intent == 'speed':
            perf = self.context['performance']
            return (f"⚡ **Performance Optimization:**\n\n"
                   f"**Technical Specs:**\n"
                   f"• Buffer Size: {perf['buffer_size']}\n"
                   f"• Workers: {perf['workers']}\n"
                   f"• I/O Method: {perf['io']}\n"
                   f"• Speed Gain: {perf['speed']}\n\n"
                   "**Typical Times:**\n"
                   "• 1GB file: ~15-20 seconds\n"
                   "• 100 files: ~30-40 seconds\n"
                   "• 1TB drive: ~2-4 hours\n\n"
                   "Speed varies by disk type (SSD faster than HDD) and wiping method!")
        
        elif intent == 'support':
            return ("🆘 **CRABEX Support:**\n\n"
                   "**24/7 Availability:**\n"
                   "• Live Chat (this bot!)\n"
                   "• Email: support@crabex.com\n"
                   "• Phone: +1-800-CRABEX\n"
                   "• Ticket System\n\n"
                   "**Self-Service:**\n"
                   "• Documentation & FAQs\n"
                   "• Video tutorials\n"
                   "• Community forum\n\n"
                   "**Response Times:**\n"
                   "• Critical: < 1 hour\n"
                   "• High: < 4 hours\n"
                   "• Normal: < 24 hours\n\n"
                   "What specific issue can I help with?")
        
        elif intent == 'features':
            features = self.context['anti_misuse']
            return ("🎯 **CRABEX Key Features:**\n\n"
                   "**10-Layer Security System:**\n" +
                   "\n".join(f"{i+1}. {feat}" for i, feat in enumerate(features)) + "\n\n"
                   "**Technical Features:**\n"
                   "• Cross-platform (Windows/Mac/Linux)\n"
                   "• Web + Standalone modes\n"
                   "• Certificate generation\n"
                   "• Third-party verification\n"
                   "• Fast wiping engine\n"
                   "• Real-time audit trail")
        
        elif intent == 'devices':
            return ("💾 **Supported Devices:**\n\n"
                   "✅ **Fully Supported:**\n"
                   "• Hard Drives (HDD)\n"
                   "• Solid State Drives (SSD)\n"
                   "• USB Flash Drives\n"
                   "• External Drives\n"
                   "• Memory Cards (SD, microSD)\n"
                   "• M.2 NVMe Drives\n"
                   "• RAID Arrays\n"
                   "• Network Storage (NAS)\n\n"
                   "**Special Features:**\n"
                   "• ATA Secure Erase for SSDs\n"
                   "• TRIM support\n"
                   "• HPA/DCO detection\n"
                   "• Firmware analysis\n\n"
                   "⚠️ **Not Yet Supported:**\n"
                   "• Mobile devices (use factory reset)\n"
                   "• Cloud storage (use provider tools)")
        
        elif intent == 'legal':
            return ("⚖️ **Legal & Compliance Notice:**\n\n"
                   "⚠️ **IMPORTANT WARNINGS:**\n"
                   "• Destroying evidence is ILLEGAL\n"
                   "• Obstruction of justice is a crime\n"
                   "• All operations are monitored and logged\n"
                   "• We cooperate with law enforcement\n\n"
                   "**We Track:**\n"
                   "• User identity & authentication\n"
                   "• IP addresses & geolocation\n"
                   "• Device fingerprints\n"
                   "• Operation purposes\n"
                   "• Suspicious activity patterns\n\n"
                   "**Legitimate Uses:**\n"
                   "✅ GDPR/privacy compliance\n"
                   "✅ End-of-life device disposal\n"
                   "✅ Pre-resale data removal\n"
                   "✅ Security breach response\n"
                   "✅ Regulatory requirements\n\n"
                   "Logs will be disclosed upon valid legal request.")
        
        elif intent == 'thanks':
            return ("😊 You're very welcome!\n\n"
                   "Is there anything else I can help you with?\n"
                   "• Security questions\n"
                   "• Technical details\n"
                   "• Compliance information\n"
                   "• Pricing inquiries\n\n"
                   "I'm here to help!")
        
        else:  # general
            return ("🤖 I'm here to help with CRABEX Data Wiping Service!\n\n"
                   "**I can answer questions about:**\n"
                   "• **Security** - Encryption and protection\n"
                   "• **Methods** - Wiping techniques\n"
                   "• **Compliance** - Certifications (GDPR, HIPAA, etc.)\n"
                   "• **Verification** - Third-party authentication\n"
                   "• **Pricing** - Plans and costs\n"
                   "• **Speed** - Performance optimization\n"
                   "• **Support** - Getting help\n"
                   "• **Legal** - Compliance and monitoring\n\n"
                   "Try asking: 'How secure is the wiping process?' or 'What methods do you support?'")
    
    def get_response(self, message):
        """Main method to get chatbot response"""
        # Add to conversation history
        self.conversation_history.append({
            'role': 'user',
            'content': message,
            'timestamp': datetime.now().isoformat()
        })
        
        # Generate response based on backend
        if self.backend == 'openai':
            response = self._generate_response_openai(message)
        elif self.backend == 'transformers':
            response = self._generate_response_transformers(message)
        else:
            response = self._generate_response_advanced(message)
        
        # Add response to history
        self.conversation_history.append({
            'role': 'assistant',
            'content': response,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep only last 20 messages
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
        
        return response
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []


# Global chatbot instance
_chatbot_instance = None

def get_chatbot():
    """Get or create chatbot instance"""
    global _chatbot_instance
    if _chatbot_instance is None:
        _chatbot_instance = CRABEXChatbot()
    return _chatbot_instance
