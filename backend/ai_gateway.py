import os
import logging
import json
from typing import Optional, Type
from datetime import datetime

from google.cloud import aiplatform
from google.oauth2.service_account import Credentials
import vertexai
from vertexai.preview.language_models import TextGenerationModel

from langchain.callbacks import get_openai_callback

from openai import OpenAI as Upstage

# from langchain.llms import OpenAI, VertexAI
from langchain.llms import OpenAI
from langchain_google_vertexai import VertexAI
from langchain.chains import LLMChain
from langchain.chains.conversation.memory import ConversationBufferMemory
from langchain.chat_models import ChatOpenAI
from langchain.chat_models.vertexai import ChatVertexAI
from langchain.agents import AgentType
from langchain.agents import initialize_agent, Tool
from langchain.tools import BaseTool, format_tool_to_openai_function
from langchain.prompts import PromptTemplate
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    AIMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain.pydantic_v1 import BaseModel
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from langchain.schema import (
    HumanMessage,
    AIMessage,
    ChatMessage,
    FunctionMessage,
)
from langchain.utilities import WikipediaAPIWrapper, GoogleSearchAPIWrapper
from langchain.tools import DuckDuckGoSearchRun
from langchain.agents import Tool

from app.core.config import config
from app.db import schemas
from app.libs.place import place_utils
from app.libs.ai import ai_prompt

logger = logging.getLogger(__name__)



def _docent_common_chat_prompt_prefix():
    return """- Your name is DocentPro.
- As a world-best tour/local guide, you're exploring with a tourist, offering insights along the way.
- The tourist may inquire or pose spontaneous questions about your shared narratives about the place.
- Answer thoughtfully and informatively, ensuring the dialogue complements the walking tour's ambiance.
- Focus solely on travel-related inquiries, ensuring relevance to the tourist's journey and surrounding environment.
- Should a query arise that isn't travel-centric, gently remind the tourist to focus on travel-related questions
- Provide clear, concise responses strictly in {language}, valuing the tourist's interest and overall experience
- If you get a question that is vague, you can ask questions to clarify the question.
- You MUST NOT biased with langauge so that you provide correct information to the tourist. For instance, if you get a question about the place in Korean but the place is in the USA, you should research the place in English and provide the answer in Korean.
- Today is {today}.
"""


def _docent_common_chat_prompt_with_place_prefix():
    return """
The closest tourist attraction around you at the moment is: {compacted_place_dict}. 
"""


def chat(
    user_message,
    place=None,
    prev_msgs=[],
    extensive=False,
    language="English",
    ai_platform="vertexai",
):
    compacted_place_dict = {}
    place_info = ""
    if place:
        compacted_place_dict = _compact_place_dict(place)
        location = place_utils.extract_location_str(place)
        place_info = f"{place.name} in {location}"

    # Limit prev_msgs length to 100 to prevent excessive token usage
    prev_msgs = prev_msgs[-100:]

    docent_chat_prompt = _docent_chat_prompt(with_place=bool(place))

    prompt = docent_chat_prompt.format_prompt(
        place_info=place_info,
        language=language,
        compacted_place_dict=compacted_place_dict,
        today=_format_today_str(),
        prev_messages_json=prev_msgs,
        user_message=user_message,
    )

    logger.debug("=" * 100)
    logger.debug(prompt)
    logger.debug(ai_platform)
    logger.debug("=" * 100)

    return call_ai_chat_model(
        prompt.to_messages(),
        extensive=extensive,
        temperature=0.3,
        ai_platform=ai_platform,
    )



def call_ai_chat_model(
    messages, extensive=False, temperature=0, ai_platform="vertexai"
):
    ret = ""

    if ai_platform == "openai":
        with get_openai_callback() as cb:
            chat = ChatOpenAI(
                model_name="gpt-3.5-turbo",
                temperature=temperature,
                organization=config.OPENAI_ORGANIZATION_ID,
                openai_api_key=config.OPENAI_API_KEY,
            )
            ret = chat(messages).content

            logger.debug("=" * 100)
            logger.debug(messages.__class__.__name__)
            logger.debug(messages)
            logger.debug("=" * 100)
            logger.debug(cb)
            logger.debug("=" * 100)
    elif ai_platform == "vertexai":
        chat = ChatVertexAI(
            model_name="chat-bison-32k",
            project=config.GOOGLE_CLOUD_PROJECT_ID,
            location="us-central1",
            max_output_tokens=DEFAULT_CHAT_MAX_OUTPUT_TOKENS,
            temperature=temperature,
            top_k=30,
            top_p=0.8,
        )

        if extensive:
            tools = generate_tools()
            agent_with_tools = initialize_agent(
                tools=tools,
                llm=chat,
                verbose=False,
                max_iterations=2,
                early_stopping_method="generate",
                agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            )
            ret = agent_with_tools.run(messages)
        else:
            ret = chat(messages).content

        return ret
    elif ai_platform == "upstage":
        client = Upstage(
            api_key="hack-with-upstage-solar-0420",
            base_url="https://api.upstage.ai/v1/solar",
        )

        msg_dicts = []

        for m in messages:
            if m.type == "human":
                role = "user"
            else:
                role = "system"

            msg_dicts.append(
                {
                    "role": role,
                    "content": m.content,
                }
            )

        response = client.chat.completions.create(
            model="solar-1-mini-chat", messages=msg_dicts
        )
        return response.choices[0].message.content
    else:
        raise Exception("Invalid ai platform", ai_platform)

    return ret

