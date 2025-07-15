from dotenv import load_dotenv

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.mcp import MCPServerStdio, MCPServerHTTP

from mcp.server.fastmcp import FastMCP
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Loads GOOGLE_APPLICATION_CREDENTIALS
load_dotenv()


def create_agent(model_id="gemini-2.5-flash"):
    # Create MCP server for Playwright
    playwright_server = MCPServerStdio(
        command="npx",
        args=[
            "@playwright/mcp@latest",
            "--headless",
            "--save-trace",
            "--output-dir=./traces",
        ],
    )

    provider = GoogleProvider(
        location="europe-west1",
        vertexai=True,
    )

    model = GoogleModel(model_id, provider=provider)

    # Create agent with Vertex AI model and Playwright MCP server
    agent = Agent(
        model,  # Using Vertex AI Gemini model
        mcp_servers=[playwright_server],
    )

    return agent
