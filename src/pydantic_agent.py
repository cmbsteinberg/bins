#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.10"
# dependencies = ["pydantic-ai", "google-auth", "mcp"]
# ///

import asyncio
import os
from pydantic_ai import Agent
from mcp.server.fastmcp import FastMCP
from mcp import ClientSession, StdioServerParameters
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.mcp import MCPServerStdio, MCPServerHTTP
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

load_dotenv()


def create_agent(model_id="gemini-2.5-flash"):
    # Create MCP server for Playwright
    playwright_server = MCPServerStdio(
        command="npx",
        args=["@playwright/mcp@latest", "--headless"],
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


async def main(
    prompt="""Navigate to https://www.aberdeencity.gov.uk/services/bins-waste-and-recycling/check-bin-collection-days. Find out when the bins are taken for any address at Harvest Avenue. Return information on the bin timetable""",
):
    agent = create_agent()
    # Start MCP servers and run the agent
    async with agent.run_mcp_servers():
        # Example 1: Simple web scraping task
        result1 = await agent.run(prompt)
        print("Example 1 - Page Title:")
        print(result1.output)
        print("-" * 50)

        return result1


if __name__ == "__main__":
    prompt = """Navigate to https://www.aberdeencity.gov.uk/services/bins-waste-and-recycling/check-bin-collection-days. Find out when the bins are taken for any address at Harvest Avenue. Return information on the bin timetable"""
    asyncio.run(main())
