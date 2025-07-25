#!/usr/bin/env python3
"""
Automated Quiz Solver for Joe.ie Friday Pub Quiz
Handles WP Viral Quiz plugin structure
"""
import asyncio
import json
import os
import httpx
from playwright.async_api import async_playwright
from dataclasses import dataclass
from typing import List, Dict, Optional

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv not installed, use system env vars


@dataclass
class QuizQuestion:
    question_id: str
    question_text: str
    image_url: Optional[str]
    answers: List[Dict[str, str]]  # [{"id": "64452", "text": "Richard I"}]


@dataclass
class QuizAnswer:
    question_id: str
    selected_answer_id: str
    confidence: float
    reasoning: str


class JoeQuizSolver:
    def __init__(self, openrouter_api_key: Optional[str] = None):
        self.quiz_url = (
            "https://www.joe.ie/quiz/the-joe-friday-pub-quiz-week-461-849819"
        )
        self.questions: List[QuizQuestion] = []
        self.answers: List[QuizAnswer] = []

        # OpenRouter configuration
        self.openrouter_api_key = (
            openrouter_api_key or os.getenv("OPENROUTER_API_KEY") or "your-api-key-here"
        )
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "qwen/qwen3-235b-a22b-07-25:free"  # Free model from OpenRouter

    async def solve_quiz(self):
        """Main method to solve the entire quiz"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            try:
                print(f"Starting quiz solver for: {self.quiz_url}")

                # Navigate and setup
                await self._navigate_and_setup(page)

                # Extract all questions
                await self._extract_questions(page)

                # Get LLM answers for all questions
                await self._get_llm_answers()

                # Apply answers to the quiz
                await self._apply_answers(page)

                # Submit quiz if needed
                await self._submit_quiz(page)

                print("Quiz completed successfully!")

            except Exception as e:
                print(f"Error solving quiz: {e}")
                await page.screenshot(path="error_screenshot.png")

            finally:
                await browser.close()

    async def _navigate_and_setup(self, page):
        """Navigate to quiz and handle initial setup"""
        print("Navigating to quiz...")
        await page.goto(self.quiz_url, timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        # Handle cookie consent
        try:
            cookie_button = await page.query_selector('button:has-text("I Accept")')
            if cookie_button:
                print("Accepting cookies...")
                await cookie_button.click()
                await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"Cookie handling failed: {e}")

        # Dynamically find the quiz ID
        print("Looking for quiz container...")
        await page.wait_for_timeout(3000)

        # Use JavaScript to find the actual quiz ID
        quiz_id = await page.evaluate(
            """
            () => {
                // Look for any element with ID starting with 'wpvq-quiz'
                const elements = document.querySelectorAll('[id*="wpvq-quiz"]');
                if (elements.length > 0) {
                    return elements[0].id;
                }
                
                // Fallback: look for elements with wpvq class
                const wpvqElements = document.querySelectorAll('.wpvq');
                if (wpvqElements.length > 0) {
                    return wpvqElements[0].id || 'wpvq-found';
                }
                
                return null;
            }
        """
        )

        if quiz_id:
            print(f"Found quiz with ID: {quiz_id}")
            try:
                await page.wait_for_selector(f"#{quiz_id}", timeout=5000)
                print("Quiz container loaded successfully")
            except Exception:
                print("Quiz ID found but element not ready, proceeding anyway...")
        else:
            print("No quiz container found, proceeding anyway...")

        await page.wait_for_timeout(2000)

    async def _extract_questions(self, page):
        """Extract all questions and their possible answers"""
        print("Extracting quiz questions...")

        # Find all question elements
        question_elements = await page.query_selector_all(".wpvq-question")

        for question_elem in question_elements:
            try:
                # Get question ID
                question_id = await question_elem.get_attribute("data-questionid")
                if not question_id:
                    continue

                # Get question text
                question_label = await question_elem.query_selector(
                    ".wpvq-question-label"
                )
                question_text = (
                    await question_label.inner_text() if question_label else ""
                )

                # Get question image if present
                image_elem = await question_elem.query_selector(".wpvq-question-img")
                image_url = (
                    await image_elem.get_attribute("src") if image_elem else None
                )

                # Get all answer options
                answer_elements = await question_elem.query_selector_all(".wpvq-answer")
                answers = []

                for answer_elem in answer_elements:
                    answer_id = await answer_elem.get_attribute("data-wpvq-answer")
                    label_elem = await answer_elem.query_selector("label")
                    answer_text = await label_elem.inner_text() if label_elem else ""

                    if answer_id and answer_text:
                        answers.append({"id": answer_id, "text": answer_text.strip()})

                if question_id and question_text and answers:
                    question = QuizQuestion(
                        question_id=question_id,
                        question_text=question_text.strip(),
                        image_url=image_url,
                        answers=answers,
                    )
                    self.questions.append(question)
                    print(f"  Q{len(self.questions)}: {question_text[:60]}...")

            except Exception as e:
                print(f"Error extracting question: {e}")

        print(f"Extracted {len(self.questions)} questions")

    async def _get_llm_answers(self):
        """Use LLM to answer all questions with rate limiting"""
        print("Getting LLM answers...")

        for i, question in enumerate(self.questions):
            try:
                # Add delay to respect rate limits (8 requests per minute = 7.5 second intervals)
                if i > 0:
                    print("  Waiting 8 seconds for rate limit...")
                    await asyncio.sleep(8)

                # Prepare the prompt
                prompt = self._create_question_prompt(question)

                # Get answer from LLM
                answer = await self._query_llm(prompt, question)

                if answer:
                    self.answers.append(answer)
                    print(
                        f"  Q{i+1}: Selected '{answer.selected_answer_id}' (confidence: {answer.confidence:.2f})"
                    )
                else:
                    print(f"  Q{i+1}: Failed to get answer")

            except Exception as e:
                print(f"Error getting LLM answer for Q{i+1}: {e}")

    def _create_question_prompt(self, question: QuizQuestion) -> str:
        """Create a prompt for the LLM"""
        prompt = f"""You are answering a pub quiz question. Please select the best answer from the given options.

Question: {question.question_text}

Options:
"""
        for i, answer in enumerate(question.answers):
            prompt += f"{chr(65+i)}. {answer['text']}\n"

        prompt += """
Please respond with ONLY the letter (A, B, C, etc.) of the correct answer, followed by a confidence score (0.0-1.0) and brief reasoning.

Format: LETTER|CONFIDENCE|REASONING

Example: B|0.85|This is a well-known historical fact about the Battle of Hastings.
"""
        return prompt

    async def _query_llm(
        self, prompt: str, question: QuizQuestion
    ) -> Optional[QuizAnswer]:
        """Query OpenRouter LLM for an answer"""
        try:
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
                    "max_tokens": 150,
                    "temperature": 0.1,  # Low temperature for consistent answers
                }

                response = await client.post(
                    self.openrouter_url, headers=headers, json=payload, timeout=30.0
                )

                if response.status_code == 200:
                    result = response.json()
                    llm_response = result["choices"][0]["message"]["content"].strip()

                    # Parse the response format: LETTER|CONFIDENCE|REASONING
                    return self._parse_llm_response(llm_response, question)
                else:
                    print(
                        f"OpenRouter API error: {response.status_code} - {response.text}"
                    )
                    return None

        except Exception as e:
            print(f"LLM query failed: {e}")
            return None

    def _parse_llm_response(
        self, llm_response: str, question: QuizQuestion
    ) -> Optional[QuizAnswer]:
        """Parse the LLM response in format: LETTER|CONFIDENCE|REASONING"""
        try:
            # Split the response by | delimiter
            parts = llm_response.split("|")
            if len(parts) >= 3:
                letter = parts[0].strip().upper()
                confidence = float(parts[1].strip())
                reasoning = parts[2].strip()

                # Convert letter (A, B, C) to answer index
                answer_index = ord(letter) - ord("A")

                if 0 <= answer_index < len(question.answers):
                    selected_answer = question.answers[answer_index]

                    return QuizAnswer(
                        question_id=question.question_id,
                        selected_answer_id=selected_answer["id"],
                        confidence=min(max(confidence, 0.0), 1.0),  # Clamp between 0-1
                        reasoning=reasoning,
                    )

            # If parsing fails, try to extract just the letter
            first_char = llm_response.strip()[0].upper()
            if "A" <= first_char <= "Z":
                answer_index = ord(first_char) - ord("A")
                if 0 <= answer_index < len(question.answers):
                    selected_answer = question.answers[answer_index]

                    return QuizAnswer(
                        question_id=question.question_id,
                        selected_answer_id=selected_answer["id"],
                        confidence=0.7,  # Default confidence
                        reasoning=f"LLM selected {first_char}: {llm_response[:100]}",
                    )

        except Exception as e:
            print(f"Error parsing LLM response '{llm_response}': {e}")

        # If all parsing fails, return None
        return None

    async def _apply_answers(self, page):
        """Apply the selected answers to the quiz"""
        print("Applying answers to quiz...")

        for i, answer in enumerate(self.answers):
            try:
                print(f"  Q{i+1}: Selecting answer {answer.selected_answer_id}")

                # Use JavaScript to click the element directly
                result = await page.evaluate(
                    f"""
                    () => {{
                        const element = document.querySelector('input[data-wpvq-answer="{answer.selected_answer_id}"]');
                        if (element) {{
                            element.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                            element.checked = true;
                            element.click();
                            
                            // Also trigger change event to ensure the quiz registers the selection
                            const event = new Event('change', {{ bubbles: true }});
                            element.dispatchEvent(event);
                            
                            return {{ success: true, found: true }};
                        }} else {{
                            return {{ success: false, found: false }};
                        }}
                    }}
                """
                )

                if result.get("found"):
                    if result.get("success"):
                        print(f"    Successfully selected Q{i+1}")
                    else:
                        print(f"    Found but failed to click Q{i+1}")
                else:
                    print(
                        f"  Q{i+1}: Could not find radio button for answer {answer.selected_answer_id}"
                    )

                await page.wait_for_timeout(1000)  # Human-like delay

            except Exception as e:
                print(f"Error applying answer for Q{i+1}: {e}")
                # Take a screenshot for debugging
                await page.screenshot(path=f"error_q{i+1}.png")

    async def _submit_quiz(self, page):
        """Submit the quiz if there's a submit button"""
        print("Looking for submit button...")

        submit_selectors = [
            'button:has-text("Submit")',
            'input[type="submit"]',
            'button:has-text("Finish")',
            'button:has-text("Complete")',
            ".wpvq-submit",
            "#wpvq-submit",
        ]

        for selector in submit_selectors:
            try:
                submit_button = await page.query_selector(selector)
                if submit_button:
                    print(f"Found submit button: {selector}")
                    await submit_button.click()
                    await page.wait_for_timeout(3000)

                    # Take final screenshot
                    await page.screenshot(path="quiz_completed.png")
                    print("Final screenshot saved as quiz_completed.png")
                    return
            except Exception as e:
                print(f"Error with submit button {selector}: {e}")

        print("No submit button found - quiz may auto-submit")
        await page.screenshot(path="quiz_final_state.png")

    def save_results(self):
        """Save quiz results to JSON file"""
        results = {
            "quiz_url": self.quiz_url,
            "questions": [
                {
                    "question_id": q.question_id,
                    "question_text": q.question_text,
                    "image_url": q.image_url,
                    "answers": q.answers,
                }
                for q in self.questions
            ],
            "selected_answers": [
                {
                    "question_id": a.question_id,
                    "selected_answer_id": a.selected_answer_id,
                    "confidence": a.confidence,
                    "reasoning": a.reasoning,
                }
                for a in self.answers
            ],
        }

        with open("quiz_results.json", "w") as f:
            json.dump(results, f, indent=2)

        print("Results saved to quiz_results.json")


async def main():
    # Initialize solver
    solver = JoeQuizSolver()

    # Solve the quiz
    await solver.solve_quiz()

    # Save results
    solver.save_results()


if __name__ == "__main__":
    asyncio.run(main())
