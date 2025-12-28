import os

from litellm import acompletion
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional

load_dotenv()


async def llm_call_with_struct_output(
    prompt: str,
    response_schema: Optional[BaseModel],
    model_id: str = "vertex_ai/gemini-3-flash-preview",
    reasoning_effort: Optional[str] = "low",
    **kwargs,
):
    response = await acompletion(
        model=model_id,
        vertex_location="global",
        messages=[
            {"content": prompt, "role": "user"},
        ],
        response_schema=response_schema,
        reasoning_effort=reasoning_effort,
        **kwargs,
    )
    content = response.choices[0].message.content
    if response_schema:
        return response_schema.model_validate_json(content)

    return content
