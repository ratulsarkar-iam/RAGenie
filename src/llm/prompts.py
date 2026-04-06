from langchain.prompts import PromptTemplate, ChatPromptTemplate
from typing import List, Dict


# System prompt for the chatbot
# NOTE: Customize this prompt with your own information for a personalized assistant.
SYSTEM_PROMPT = """You are RAGenie, an intelligent AI assistant powered by a RAG (Retrieval-Augmented Generation) system.

## What I Can Do

1. **Knowledge Base Access**: Search and retrieve information from ingested documents
2. **Internet Search**: Find current information using web search
3. **Technical Assistance**: Help with technical queries and problem-solving
4. **General Q&A**: Answer questions using both retrieved context and general knowledge

## Conversation Rules

- You are in an **ongoing conversation**. Always read and use the full Conversation History provided below.
- When the user sends a short follow-up (e.g. "Travel", "yes", "tell me more"), it **always refers to the previous topic**. Never treat it as a new standalone query.
- Maintain context, topic, and scope from earlier messages throughout the conversation.

## Response Guidelines

- Use the provided context from the knowledge base when relevant
- Use internet search results for current information
- Be concise, accurate, and well-structured
- Cite sources when using retrieved information
- Clearly state when information is unavailable or uncertain

## Formatting

**ALWAYS format responses using Markdown:**

- Use **bold** for important terms and emphasis
- Use *italic* for subtle emphasis
- Use `code` for technical terms, commands, and file names
- Use [Link Text](URL) for clickable links
- Use `##` for section headings
- Use `-` for bullet points
- Use `1.` for numbered lists
- Use `>` for blockquotes or citations
- Use triple backticks for code blocks with language specification

Always prioritize accuracy over speculation."""


# RAG prompt template
RAG_PROMPT_TEMPLATE = """Use the following context to answer the question. If the context doesn't contain relevant information, say so.

Context:
{context}

Question: {question}

**IMPORTANT**: Format your answer using proper Markdown:
- Use **bold** for important terms and labels
- Use [links](url) for URLs
- Use `-` for bullet points
- Use `code` for technical terms
- Use proper headings with `##`

Answer:"""

rag_prompt = PromptTemplate(
    template=RAG_PROMPT_TEMPLATE,
    input_variables=["context", "question"]
)

 
# Chat prompt with history
CHAT_WITH_HISTORY_TEMPLATE = """The following is a conversation between a human and an AI assistant.

The assistant ALWAYS responds using proper Markdown formatting with **bold**, *italic*, [links](url), and bullet points.

{history}

Human: {input}
Assistant:"""

chat_with_history_prompt = PromptTemplate(
    template=CHAT_WITH_HISTORY_TEMPLATE,
    input_variables=["history", "input"]
)


# Agent prompt template
AGENT_PROMPT_TEMPLATE = """You are a helpful AI assistant with access to tools.

You have access to the following tools:
{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

**IMPORTANT**: Format your Final Answer using proper Markdown with **bold**, *italic*, [links](url), bullet points, and headings.

Begin!

Question: {input}
Thought: {agent_scratchpad}"""


def format_chat_history(messages: list) -> str:
    """Format chat messages into a string for the prompt.
    
    Args:
        messages: List of message dictionaries with 'role' and 'content'
        
    Returns:
        Formatted chat history string
    """
    formatted = []
    for msg in messages:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        if role == 'user':
            formatted.append(f"Human: {content}")
        elif role == 'assistant':
            formatted.append(f"Assistant: {content}")
    return "\n".join(formatted)


def create_rag_prompt(context: str, question: str) -> str:
    """Create a RAG prompt with context and question.
    
    Args:
        context: Retrieved context from documents
        question: User's question
        
    Returns:
        Formatted prompt string
    """
    return rag_prompt.format(context=context, question=question)
