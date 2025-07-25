#!/usr/bin/env python3
"""
Quiz Assistant - Simple clipboard-based LLM helper
Copy quiz question text, then press Enter in this terminal to get AI answers
"""
import asyncio
import httpx
import pyperclip

from datetime import datetime


class QuizAssistant:
    def __init__(self):
        self.openrouter_api_key = (
            "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"
        )
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "mistralai/mistral-small-3.2-24b-instruct:free"
        self.last_clipboard = ""

        print("🤖 Quiz Assistant Started!")
        print("📋 How to use:")
        print("   1. Copy quiz question text (Ctrl+C)")
        print("   2. Press ENTER in this terminal")
        print("   3. Get AI answer instantly!")
        print("   4. Type 'exit' to quit")
        print("-" * 50)

    def create_quiz_prompt(self, question_text: str) -> str:
        """Create a focused prompt for quiz questions"""
        return f"""You are helping with a pub quiz question. Analyze this question and provide the best answer.

Question: {question_text}

Please respond with:
1. Your answer (be specific and concise)
Return nothing else, just the answers"""

    async def query_llm(self, question_text: str) -> str:
        """Query OpenRouter LLM for an answer"""
        try:
            prompt = self.create_quiz_prompt(question_text)

            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {self.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/quiz-assistant",
                    "X-Title": "Quiz Assistant",
                }

                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.1,
                }

                response = await client.post(
                    self.openrouter_url, headers=headers, json=payload, timeout=15.0
                )

                if response.status_code == 200:
                    result = response.json()
                    return result["choices"][0]["message"]["content"].strip()
                else:
                    return f"❌ API Error: {response.status_code} - {response.text}"

        except Exception as e:
            return f"❌ Error: {str(e)}"

    async def process_question(self, question_text: str):
        """Process the text as a quiz question"""
        try:
            if not question_text.strip():
                print("⚠️ No text provided!")
                return

            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"\n[{timestamp}] 📝 Question:")
            print(f"'{question_text[:150]}{'...' if len(question_text) > 150 else ''}")
            print("-" * 50)

            # Get LLM analysis
            print("🤖 Getting LLM analysis...")
            llm_response = await self.query_llm(question_text)

            print("🎯 LLM Response:")
            print(llm_response)
            print("=" * 50)

        except Exception as e:
            print(f"❌ Error processing question: {e}")

    def get_clipboard_content(self):
        """Get current clipboard content"""
        try:
            return pyperclip.paste().strip()
        except Exception as e:
            print(f"⚠️ Clipboard error: {e}")
            return ""

    async def run(self):
        """Main interactive loop"""
        print("\n🎯 Ready! Copy a quiz question and press ENTER...")

        while True:
            try:
                # Wait for user input
                user_input = input(
                    "\n> Press ENTER to analyze clipboard (or type 'exit'): "
                ).strip()

                if user_input.lower() in ["exit", "quit", "q"]:
                    print("👋 Goodbye!")
                    break

                # Check if user typed a question directly
                if user_input:
                    await self.process_question(user_input)
                else:
                    # Get from clipboard
                    clipboard_content = self.get_clipboard_content()
                    if clipboard_content:
                        if clipboard_content != self.last_clipboard:
                            self.last_clipboard = clipboard_content
                            await self.process_question(clipboard_content)
                        else:
                            print("📋 Same content as before. Copy a new question!")
                    else:
                        print("📋 Clipboard is empty. Copy some text first!")

            except KeyboardInterrupt:
                print("\n👋 Quiz Assistant stopped.")
                break
            except Exception as e:
                print(f"❌ Error: {e}")


def main():
    assistant = QuizAssistant()
    asyncio.run(assistant.run())


if __name__ == "__main__":
    main()
