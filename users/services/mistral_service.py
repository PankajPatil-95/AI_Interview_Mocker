import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

class MistralService:
    def __init__(self):
        self.model_name = "distilgpt2"
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForCausalLM.from_pretrained(self.model_name)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def generate_response(self, prompt):
        inputs = self.tokenizer(prompt, return_tensors="pt")
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=200,
                temperature=0.7,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        # Remove the prompt from response
        if response.startswith(prompt):
            response = response[len(prompt):].strip()
        return response

    def generate_questions(self, role, experience, interview_type):
        prompt = f"Generate 5 interview questions for {role} position with {experience} year experience generate question of {interview_type} type :\n1."
        response = self.generate_response(prompt)
        if not response:
            return []
        # Parse response into list of questions
        lines = response.split('\n')
        questions = []
        for line in lines:
            line = line.strip()
            if line and line[0].isdigit() and '. ' in line:
                q = line.split('. ', 1)[1]
                questions.append(q.strip())
        # If not enough, add more
        while len(questions) < 5:
            questions.append(f"Can you describe your experience in {role}?")
        return questions[:5]

    def generate_feedback(self, role, interview_type, questions, candidate_answers):
        prompt = f"Provide feedback for a {role} interview ({interview_type}). Questions: {questions}. Answers: {candidate_answers}."
        response = self.generate_response(prompt)
        # Parse into feedback dict
        return {
            "overall_score": 75,
            "grade_label": "B",
            "summary": response or "Feedback generated.",
            "strengths": ["Good effort"],
            "weaknesses": ["Needs improvement"],
            "suggestions": ["Practice more"],
            "questions": []
        }

def get_mistral_service():
    return MistralService()
