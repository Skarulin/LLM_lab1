from langchain_openai import ChatOpenAI

from config import get_api_token, get_base_url, get_model_name


def build_llm(thinking: bool = False, temperature: float = 0.0):
    return ChatOpenAI(
        model=get_model_name(),
        base_url=get_base_url(),
        api_key=get_api_token(),
        temperature=temperature,
        max_retries=0,
        extra_body={
            "chat_template_kwargs": {"enable_thinking": thinking}
        },
    )