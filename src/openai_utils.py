import os
from openai import OpenAI


def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Set it before running AI generation."
        )

    return OpenAI(api_key=api_key)


def generate_text(prompt: str, model: str = "gpt-4o-mini") -> str:
    client = get_openai_client()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a practical trucking business content assistant. "
                    "Write clear, useful, driver-friendly content for small trucking companies. "
                    "Avoid corporate fluff. Keep the tone professional, direct, and usable."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.7,
    )

    return response.choices[0].message.content.strip()
